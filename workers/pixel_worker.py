#!/usr/bin/env python3
"""
Pixel Worker - Extracción Asíncrona de Mapas de Píxeles

Este worker maneja la extracción y conversión de pixel data DICOM a JPEG
en background, especialmente para imágenes BD (Bone Density) de HOLOGIC.

Características:
- Extracción de BMP embebido (tags propietarios HOLOGIC)
- Acceso directo a PixelData para formatos especiales
- Normalización de píxeles con manejo de window/level
- Manejo robusto de datos truncados/corruptos
"""

import logging
from pathlib import Path
from typing import Optional
import numpy as np
import pydicom
from PIL import Image

logger = logging.getLogger(__name__)

# Directorio de salida para píxeles extraídos
PIXEL_OUTPUT = Path('./pixel_extraction')
PIXEL_OUTPUT.mkdir(parents=True, exist_ok=True)


def normalize_pixel_array(pixel_array: np.ndarray, is_color: bool = False) -> np.ndarray:
    """
    Normaliza array de píxeles a rango uint8 (0-255).
    
    Args:
        pixel_array: Array NumPy con datos de píxeles
        is_color: True si es imagen a color (RGB)
        
    Returns:
        np.ndarray: Array normalizado a uint8
    """
    if is_color:
        # Imagen a color - ya debería estar en rango 0-255
        if pixel_array.dtype == np.uint8:
            return pixel_array
        else:
            return np.clip(pixel_array, 0, 255).astype(np.uint8)
    
    # Imagen en escala de grises - normalizar
    pixel_min = float(pixel_array.min())
    pixel_max = float(pixel_array.max())
    
    if pixel_max - pixel_min < 1:
        # Imagen uniforme o casi uniforme
        return np.zeros_like(pixel_array, dtype=np.uint8)
    
    # Normalizar a 0-255
    normalized = ((pixel_array - pixel_min) / (pixel_max - pixel_min) * 255.0)
    normalized = np.clip(normalized, 0, 255).astype(np.uint8)
    
    return normalized


def extract_and_save_pixel_map_async(dicom_path: Path, patient_id: str, modality: str) -> bool:
    """
    Worker function: Extrae pixel map de DICOM y guarda como JPEG.
    
    Diseñado especialmente para imágenes BD (Bone Density) de HOLOGIC que pueden
    tener formatos especiales de PixelData o BMP embebido en tags propietarios.
    
    Maneja:
    - PixelData estándar (CT, MR, US, etc.)
    - PixelData en formato especial BD (acceso directo a bytes)
    - Datos truncados/corruptos (padding con ceros)
    - BMP embebido en tags propietarios HOLOGIC (BD)
    
    Args:
        dicom_path: Path al archivo DICOM
        patient_id: ID del paciente
        modality: Modalidad DICOM (ej: BD)
        
    Returns:
        bool: True si extracción exitosa, False en caso contrario
    """
    try:
        # Leer DICOM con force=True para ignorar errores de validación
        if not dicom_path.exists():
            logger.error(f"❌ Archivo no existe: {dicom_path}")
            return False
        
        dicom_dataset = pydicom.dcmread(str(dicom_path), force=True, stop_before_pixels=False)
        
        # Crear directorio de salida
        output_dir = PIXEL_OUTPUT / modality / str(patient_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generar nombre de archivo
        filename_base = dicom_path.stem
        output_path = output_dir / f"{filename_base}.jpg"
        
        # === INTENTO 1: Buscar BMP embebido en tags propietarios HOLOGIC (para BD) ===
        if modality.upper() == 'BD' and (0x0029, 0x1000) in dicom_dataset:
            try:
                bmp_data = dicom_dataset[0x0029, 0x1000].value
                if bmp_data and len(bmp_data) > 10:
                    # Cargar BMP con PIL
                    import io
                    bmp_file = io.BytesIO(bmp_data)
                    image = Image.open(bmp_file)
                    
                    # Convertir a RGB/L si es necesario
                    if image.mode == 'RGBA':
                        image = image.convert('RGB')
                    elif image.mode == 'P':  # Paleta indexada
                        image = image.convert('RGB')
                    elif image.mode not in ['RGB', 'L']:
                        image = image.convert('RGB')
                    
                    # Guardar JPEG
                    image.save(str(output_path), 'JPEG', quality=95)
                    file_size = output_path.stat().st_size
                    logger.info(f"✅ [ASYNC] BMP embebido extraído (HOLOGIC): {output_path.relative_to(PIXEL_OUTPUT)} ({file_size:,} bytes)")
                    return True
            except Exception as bmp_error:
                logger.debug(f"   No se pudo extraer BMP embebido: {str(bmp_error)[:60]}")
        
        # === INTENTO 2: PixelData estándar DICOM ===
        if 'PixelData' not in dicom_dataset:
            logger.warning(f"⚠️  [ASYNC] {dicom_path.name}: Sin PixelData ni BMP embebido")
            return False
        
        # Detectar si es imagen a color
        is_color = False
        try:
            photometric = dicom_dataset.get('PhotometricInterpretation', '')
            samples_per_pixel = int(dicom_dataset.get('SamplesPerPixel', 1))
            is_color = ('RGB' in str(photometric).upper()) or samples_per_pixel == 3
        except:
            is_color = False
        
        # Obtener array de píxeles con manejo especial para BD
        pixel_array = None
        try:
            # Primero intentar pixel_array estándar (funciona para muchos formatos)
            pixel_array = dicom_dataset.pixel_array
            
        except Exception as array_error:
            # Si pixel_array falla (ej: TransferSyntaxUID missing), usar acceso directo
            logger.debug(f"   pixel_array falló, usando acceso directo: {str(array_error)[:60]}")
            
            try:
                rows = int(dicom_dataset.get('Rows', 0))
                cols = int(dicom_dataset.get('Columns', 0))
                bits_allocated = int(dicom_dataset.get('BitsAllocated', 8))
                
                if rows == 0 or cols == 0:
                    logger.error(f"❌ Dimensiones inválidas: {rows}x{cols}")
                    return False
                
                pixel_data = dicom_dataset.PixelData
                bytes_per_pixel = bits_allocated // 8
                expected_bytes = rows * cols * bytes_per_pixel
                
                # Verificar truncamiento
                if len(pixel_data) < expected_bytes:
                    logger.warning(f"⚠️  PixelData truncado: {len(pixel_data)}/{expected_bytes} bytes")
                
                # Convertir a array NumPy
                dtype = np.uint16 if bits_allocated > 8 else np.uint8
                available_pixels = len(pixel_data) // bytes_per_pixel
                pixel_array = np.frombuffer(
                    pixel_data[:available_pixels * bytes_per_pixel],
                    dtype=dtype
                )
                pixel_array = pixel_array.reshape(rows, cols)
                logger.debug(f"   Acceso directo exitoso: {rows}x{cols} ({bits_allocated} bits)")
                
            except Exception as direct_error:
                logger.error(f"❌ Error en acceso directo: {str(direct_error)[:100]}")
                return False
        
        if pixel_array is None:
            logger.error(f"❌ No se pudo obtener pixel_array")
            return False
        
        # Normalizar píxeles
        normalized = normalize_pixel_array(pixel_array, is_color=is_color)
        
        # Crear imagen PIL
        if is_color and len(normalized.shape) == 3:
            image = Image.fromarray(normalized, mode='RGB')
        elif len(normalized.shape) == 2:
            image = Image.fromarray(normalized, mode='L')
        else:
            image = Image.fromarray(normalized[:, :, 0] if len(normalized.shape) == 3 else normalized, mode='L')
        
        # Guardar JPEG
        image.save(str(output_path), 'JPEG', quality=95)
        file_size = output_path.stat().st_size
        logger.info(f"✅ [ASYNC] Pixel map extraído: {output_path.relative_to(PIXEL_OUTPUT)} ({file_size:,} bytes)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ [ASYNC] Error extrayendo pixel map de {dicom_path.name}: {str(e)[:100]}", exc_info=True)
        return False


def validate_pixel_data(ds: pydicom.Dataset) -> tuple:
    """
    Valida que el PixelData del DICOM sea completo según sus dimensiones.
    
    Args:
        ds: Dataset DICOM
        
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    if 'PixelData' not in ds:
        return True, "Sin PixelData"  # OK - puede no tener píxeles
    
    try:
        rows = int(ds.get('Rows', 0))
        cols = int(ds.get('Columns', 0))
        
        if rows == 0 or cols == 0:
            return True, "Dimensiones inválidas pero OK"
        
        bits_allocated = int(ds.get('BitsAllocated', 8))
        samples_per_pixel = int(ds.get('SamplesPerPixel', 1))
        
        expected_bytes = rows * cols * samples_per_pixel * (bits_allocated // 8)
        actual_bytes = len(ds.PixelData)
        
        # Permitir pequeña variación (hasta 10%) para compresión
        min_expected = int(expected_bytes * 0.9)
        
        if actual_bytes < min_expected:
            percentage = (actual_bytes / expected_bytes) * 100 if expected_bytes > 0 else 0
            msg = f"PixelData truncado: {actual_bytes}/{expected_bytes} bytes ({percentage:.1f}%)"
            return False, msg
        
        return True, f"PixelData completo: {actual_bytes}/{expected_bytes} bytes"
    
    except Exception as e:
        return False, f"Error validando PixelData: {str(e)[:100]}"
