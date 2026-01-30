#!/usr/bin/env python3
"""
DICOM C-STORE Server using pynetdicom 2.1.0

This service receives DICOM files via C-STORE protocol on port 5665 and stores them
in an organized directory structure (PatientID/StudyInstanceUID/).

Supported modalities:
  - CT, MR, Ultrasound, X-Ray, Computed Radiography, Digital X-Ray, Secondary Capture
  - BD (Bone Density) - with automatic pixel map extraction to JPEG
  - Transfer syntaxes: Explicit VR Little Endian, Implicit VR Little Endian, JPEG 2000 Lossless

Server: pynetdicom 2.1.0 (DICOM network protocol)
Storage: ./dicom_storage/ directory structure
Port: 5665
AE Title: DICOM_RECEIVER
"""

import logging
import sys
import subprocess
from pathlib import Path
from datetime import datetime

import pydicom
import numpy as np
from PIL import Image

from pynetdicom import AE, events
from pynetdicom.sop_class import (
    CTImageStorage,
    MRImageStorage,
    UltrasoundImageStorage,
    XRayAngiographicImageStorage,
    ComputedRadiographyImageStorage,
    DigitalXRayImageStorageForPresentation,
    DigitalXRayImageStorageForProcessing,
    SecondaryCaptureImageStorage,
    Verification,
)
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    JPEG2000Lossless,
    JPEG2000,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Storage directory
STORAGE = Path("./dicom_storage")
STORAGE.mkdir(exist_ok=True, parents=True)

# Pixel output directory for BD images
PIXEL_OUTPUT = Path("./pixel_extraction")
PIXEL_OUTPUT.mkdir(exist_ok=True, parents=True)

# XML extraction directory for BD XML data
XML_OUTPUT = Path("./xml_extraction")
XML_OUTPUT.mkdir(exist_ok=True, parents=True)

# Logs directory for BD processing
LOGS_DIR = Path("./logs")
LOGS_DIR.mkdir(exist_ok=True, parents=True)


def log_bd_processing(patient_id, step, status, details=""):
    """
    Registra cada paso del procesamiento BD en un archivo de log centralizado.
    
    Args:
        patient_id: ID del paciente
        step: Paso del proceso (RECEPCION, ANALISIS, PIXEL_MAP, REPORTE, BD_INSERT)
        status: Estado (SUCCESS, ERROR, WARNING)
        details: Detalles adicionales
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file = LOGS_DIR / "bd_processing.log"
        
        log_entry = f"[{timestamp}] [Patient: {patient_id}] [{step}] [{status}] {details}\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Error escribiendo log BD: {e}")


def extract_and_save_xml(dicom_path, patient_id, modality):
    """
    Extrae el XML embebido del tag (0x0019, 0x1000) de DICOM y lo guarda en archivo.
    Estructura de carpetas: xml_extraction/{modality}/{patient_id}/
    
    Args:
        dicom_path: Ruta del archivo DICOM
        patient_id: ID del paciente
        modality: Modalidad DICOM (ej: BD)
        
    Returns:
        bool: True si se extrajo exitosamente, False en caso contrario
    """
    try:
        # Leer DICOM
        ds = pydicom.dcmread(str(dicom_path), stop_before_pixels=True, force=True)
        
        # Verificar si tiene XML en tag (0x0019, 0x1000)
        if (0x0019, 0x1000) not in ds:
            logger.debug(f"No se encontró XML en tag (0x0019, 0x1000) para {dicom_path}")
            return False
        
        # Extraer XML
        xml_data = ds[0x0019, 0x1000].value
        if isinstance(xml_data, bytes):
            xml_text = xml_data.decode('utf-8', errors='ignore')
        else:
            xml_text = str(xml_data)
        
        # Crear directorio de salida
        output_dir = XML_OUTPUT / modality / str(patient_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generar nombre de archivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        sop_instance_uid = getattr(ds, 'SOPInstanceUID', 'unknown')
        output_filename = f"BD_{timestamp}_{sop_instance_uid}.xml"
        output_path = output_dir / output_filename
        
        # Guardar XML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_text)
        
        logger.debug(f"XML guardado: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error extrayendo XML de {dicom_path}: {e}")
        return False


def normalize_pixel_array(pixel_array, is_color=False):
    """
    Normaliza el array de píxeles a valores entre 0-255 para JPEG
    
    Args:
        pixel_array: Array de píxeles (2D para escala de grises, 3D para color)
        is_color: Si es True, trata como imagen RGB y normaliza cada canal por separado
    """
    # Si ya está en rango 0-255 (uint8), retornar tal cual
    if pixel_array.dtype == np.uint8 and pixel_array.min() >= 0 and pixel_array.max() <= 255:
        return pixel_array
    
    # Convertir a float para cálculos
    pixel_array = pixel_array.astype(np.float32)
    
    if is_color and len(pixel_array.shape) == 3:
        # Normalizar cada canal por separado
        normalized = np.zeros_like(pixel_array)
        for channel in range(pixel_array.shape[2]):
            channel_data = pixel_array[:, :, channel]
            min_val = np.min(channel_data)
            max_val = np.max(channel_data)
            
            if max_val == min_val:
                normalized[:, :, channel] = 0
            else:
                normalized[:, :, channel] = ((channel_data - min_val) / (max_val - min_val)) * 255
    else:
        # Normalizar toda la imagen (escala de grises o general)
        min_val = np.min(pixel_array)
        max_val = np.max(pixel_array)
        
        if max_val == min_val:
            normalized = np.zeros_like(pixel_array)
        else:
            normalized = ((pixel_array - min_val) / (max_val - min_val)) * 255
    
    return normalized.astype(np.uint8)


def extract_and_save_pixel_map(dicom_path, patient_id, modality):
    """
    Extrae el pixel map de un archivo DICOM y lo guarda como JPEG
    Especialmente diseñado para imágenes BD (Bone Density) de HOLOGIC
    
    NOTA: Archivos BD de HOLOGIC pueden tener PixelData en formato especial
    que requiere acceso directo a los bytes en lugar de usar pixel_array.
    
    Maneja:
    - PixelData estándar (CT, MR, US, etc.)
    - PixelData en formato especial BD (acceso directo a bytes)
    - Datos truncados/corruptos (padding con ceros)
    - BMP embebido en tags propietarios HOLOGIC (BD) si existe
    
    Args:
        dicom_path: Ruta del archivo DICOM
        patient_id: ID del paciente
        modality: Modalidad DICOM (ej: BD)
        
    Returns:
        bool: True si se extrajo exitosamente, False en caso contrario
    """
    try:
        # Leer DICOM con force=True para ignorar errores de validación
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
                    logger.info(f"  ✓ BMP embebido extraído (HOLOGIC): {output_path.relative_to(PIXEL_OUTPUT)}")
                    return True
            except Exception as bmp_error:
                logger.debug(f"  ℹ No se pudo extraer BMP embebido: {str(bmp_error)[:60]}")
        
        # === INTENTO 2: PixelData estándar DICOM ===
        if 'PixelData' not in dicom_dataset:
            logger.warning(f"  ⚠ {dicom_path.name}: Sin PixelData ni BMP embebido")
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
            logger.debug(f"  ℹ pixel_array falló, usando acceso directo: {str(array_error)[:60]}")
            
            try:
                rows = int(dicom_dataset.get('Rows', 0))
                cols = int(dicom_dataset.get('Columns', 0))
                bits_allocated = int(dicom_dataset.get('BitsAllocated', 8))
                
                if rows == 0 or cols == 0:
                    logger.error(f"  ✗ Dimensiones inválidas: {rows}x{cols}")
                    return False
                
                pixel_data = dicom_dataset.PixelData
                bytes_per_pixel = bits_allocated // 8
                expected_bytes = rows * cols * bytes_per_pixel
                
                # Verificar truncamiento
                if len(pixel_data) < expected_bytes:
                    logger.warning(f"  ⚠ PixelData truncado: {len(pixel_data)}/{expected_bytes} bytes")
                
                # Convertir a array NumPy
                dtype = np.uint16 if bits_allocated > 8 else np.uint8
                available_pixels = len(pixel_data) // bytes_per_pixel
                pixel_array = np.frombuffer(
                    pixel_data[:available_pixels * bytes_per_pixel],
                    dtype=dtype
                )
                pixel_array = pixel_array.reshape(rows, cols)
                logger.debug(f"  ✓ Acceso directo exitoso: {rows}x{cols} ({bits_allocated} bits)")
                
            except Exception as direct_error:
                logger.error(f"  ✗ Error en acceso directo: {str(direct_error)[:100]}")
                return False
        
        if pixel_array is None:
            logger.error(f"  ✗ No se pudo obtener pixel_array")
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
        logger.info(f"  ✓ Pixel map extraído: {output_path.relative_to(PIXEL_OUTPUT)} ({file_size:,} bytes)")
        
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Error extrayendo pixel map de {dicom_path.name}: {str(e)[:100]}")
        return False


def validate_pixel_data(ds):
    """
    Valida que el PixelData del DICOM sea completo según sus dimensiones.
    
    Returns:
        (bool, str): (is_valid, message)
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
        return True, f"No se pudo validar: {str(e)[:50]}"


def handle_store(event):
    """
    Handle C-STORE request.
    
    Receives DICOM dataset and saves it in structured directory:
    ./dicom_storage/{PatientID}/{StudyInstanceUID}/{raw_bytes_no_extension}
    
    Para archivos BD (Bone Density), también extrae el pixel map como JPEG
    
    Args:
        event: C-STORE event with dataset
        
    Returns:
        0x0000 for success, 0x0110 for failure
    """
    try:
        ds = event.dataset
        patient_id = getattr(ds, 'PatientID', 'UNKNOWN')
        study_uid = getattr(ds, 'StudyInstanceUID', 'UNKNOWN')
        modality = getattr(ds, 'Modality', 'UNKNOWN')
        sop_uid = getattr(ds, 'SOPInstanceUID', 'UNKNOWN')
        
        # Log connection details from OnePACS
        remote = getattr(event.assoc, 'remote', None)
        context = getattr(event.context, 'transfer_syntax', 'Unknown')
        
        logger.info(f"📥 C-STORE Request: {modality} from {remote}")
        logger.info(f"   Transfer Syntax: {str(context)[:50]}")
        
        # Validar integridad del DICOM
        is_valid, validation_msg = validate_pixel_data(ds)
        
        # NO RECHAZAR - aceptar incluso truncados para poder recuperarlos
        if not is_valid:
            logger.warning(f"⚠ {validation_msg} - ACEPTANDO IGUAL (posible truncado de transmisión)")
            logger.warning(f"   Paciente: {patient_id}, Modalidad: {modality}")
        
        # Create directory structure
        patient_dir = STORAGE / str(patient_id)
        study_dir = patient_dir / str(study_uid)
        study_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename (no extension - raw bytes)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{modality}_{timestamp}_{sop_uid}"
        filepath = study_dir / filename
        
        # Save DICOM file - preserve dataset exactly as received without re-encoding
        # write_like_original=True is critical to preserve JPEG2000 compression
        # and avoid decompression issues with small PDU fragments
        try:
            ds.save_as(str(filepath), write_like_original=True)
        except Exception as save_err:
            # Fallback if write_like_original fails
            logger.warning(f"⚠ write_like_original falló, usando fallback: {str(save_err)[:60]}")
            ds.save_as(str(filepath))
        
        # Get actual file size on disk
        file_size_bytes = filepath.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        logger.info(f"✓ DICOM guardado: {patient_id}/{study_uid}/{filename}")
        logger.info(f"   └─ Tamaño: {file_size_bytes:,} bytes ({file_size_mb:.2f} MB)")
        logger.info(f"   └─ {validation_msg}")
        
        # Si es Bone Density, procesar según fabricante del equipo
        if modality.upper() == 'BD':
            # Detectar fabricante del equipo
            manufacturer = getattr(ds, 'Manufacturer', 'UNKNOWN').strip().upper()
            model = getattr(ds, 'ManufacturerModelName', 'UNKNOWN').strip()
            body_part = getattr(ds, 'BodyPartExamined', 'UNKNOWN')
            series_description = getattr(ds, 'SeriesDescription', 'UNKNOWN')
            
            # Log paso 1: Recepción de BD con información de equipo
            log_bd_processing(patient_id, "RECEPCION", "SUCCESS", 
                            f"BD recibido - Fabricante: {manufacturer}, Modelo: {model}, BodyPart: {body_part}, Series: {series_description}, Tamaño: {file_size_mb:.2f} MB")
            
            # Determinar script de procesamiento según fabricante
            extraction_script = None
            
            if 'HOLOGIC' in manufacturer:
                # Equipos HOLOGIC: usan XML estructurado en tag (0x0019, 0x1000)
                extraction_script = '/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_hologic.py'
                log_bd_processing(patient_id, "DETECCION", "INFO", 
                                f"Equipo HOLOGIC detectado - Modelo: {model}")
                
                # Extraer y guardar XML siempre (para HOLOGIC BD)
                xml_extracted = extract_and_save_xml(filepath, patient_id, modality)
                if xml_extracted:
                    log_bd_processing(patient_id, "XML_EXTRACTION", "SUCCESS", 
                                    "XML extraído y guardado exitosamente")
                else:
                    log_bd_processing(patient_id, "XML_EXTRACTION", "WARNING", 
                                    "No se pudo extraer XML del DICOM")
                
                # Para HOLOGIC, detectar si es HIP antes de procesar
                is_hip = body_part == 'HIP'
                needs_pixel_extraction = False
                
                # Si no es HIP según el tag, buscar en el XML
                if not is_hip and (0x0019, 0x1000) in ds:
                    try:
                        xml_data = ds[0x0019, 0x1000].value
                        if isinstance(xml_data, bytes):
                            xml_text = xml_data.decode('utf-8', errors='ignore')
                        else:
                            xml_text = str(xml_data)
                        
                        # Buscar ScanMode con "Hip"
                        import re
                        scan_mode_match = re.search(r'ScanMode\s*=\s*"([^"]*[Hh]ip[^"]*)"', xml_text)
                        if scan_mode_match:
                            is_hip = True
                            scan_mode = scan_mode_match.group(1)
                            log_bd_processing(patient_id, "DETECCION", "INFO", 
                                            f"HIP detectado en ScanMode XML: '{scan_mode}' (BodyPartExamined: '{body_part}')")
                    except Exception as xml_err:
                        logger.debug(f"Error buscando Hip en XML: {xml_err}")
                
                # Si es HIP, verificar si necesita extracción de píxeles para FRAX
                if is_hip and (0x0019, 0x1000) in ds:
                    try:
                        xml_data = ds[0x0019, 0x1000].value
                        if isinstance(xml_data, bytes):
                            xml_text = xml_data.decode('utf-8', errors='ignore')
                        else:
                            xml_text = str(xml_data)
                        
                        # Buscar FRAX Major en XML (puede estar en ResultsTable2 o ResultsTable3)
                        import re
                        # Intentar ResultsTable2[1][2], ResultsTable2[1][1], o ResultsTable3[1][1]
                        frax_match = re.search(r'ResultsTable2\[\s*1\]\[\s*2\]\s*=', xml_text)
                        if not frax_match:
                            frax_match = re.search(r'ResultsTable2\[\s*1\]\[\s*1\]\s*=', xml_text)
                        if not frax_match:
                            frax_match = re.search(r'ResultsTable3\[\s*1\]\[\s*1\]\s*=', xml_text)
                        
                        if frax_match:
                            log_bd_processing(patient_id, "PIXEL_MAP", "INFO", 
                                            "FRAX encontrado en XML - pixel extraction no necesaria")
                            needs_pixel_extraction = False
                        else:
                            log_bd_processing(patient_id, "PIXEL_MAP", "INFO", 
                                            "FRAX no encontrado en XML - se requiere pixel extraction para OCR")
                            needs_pixel_extraction = True
                    except Exception as xml_err:
                        logger.debug(f"Error verificando FRAX en XML: {xml_err}")
                        # Si hay error leyendo XML, extraer píxeles por seguridad
                        needs_pixel_extraction = True
                
                # Extraer píxeles solo si es necesario
                if needs_pixel_extraction:
                    extraction_ok = extract_and_save_pixel_map(filepath, patient_id, modality)
                    if extraction_ok:
                        log_bd_processing(patient_id, "PIXEL_MAP", "SUCCESS", 
                                        "Pixel map extraído para OCR de FRAX")
                    else:
                        log_bd_processing(patient_id, "PIXEL_MAP", "WARNING", 
                                        "No se pudo extraer pixel map - FRAX podría no estar disponible")
                
                # HOLOGIC: procesar todos los archivos (HIP, LSPINE, FOREARM)
                # El script de extracción consolidará los datos en el mismo registro por ACC
                log_bd_processing(patient_id, "ANALISIS", "INFO", 
                                f"HOLOGIC BD {body_part} recibido - será procesado y consolidado por ACC")
                
            elif 'GE' in manufacturer and 'LUNAR' in model.upper():
                # Equipos GE Lunar: son reportes encapsulados (DXA Reports)
                extraction_script = '/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_ge.py'
                log_bd_processing(patient_id, "DETECCION", "INFO", 
                                f"Equipo GE Lunar detectado - Modelo: {model} - Series: {series_description}")
                log_bd_processing(patient_id, "DETECCION", "WARNING", 
                                f"GE Lunar usa reportes encapsulados - requiere OCR (pendiente implementación)")
                # Por ahora, no procesar GE Lunar (pendiente OCR)
                extraction_script = None
                
            else:
                # Fabricante desconocido o no soportado
                log_bd_processing(patient_id, "DETECCION", "WARNING", 
                                f"Fabricante no reconocido o no soportado - Manufacturer: {manufacturer}, Model: {model}")
                extraction_script = None
            
            # Ejecutar script de extracción si se determinó uno
            if extraction_script:
                log_bd_processing(patient_id, "ANALISIS", "SUCCESS", 
                                f"Iniciando procesamiento con: {extraction_script}")
                
                try:
                    result = subprocess.run(
                        ['python3', extraction_script, str(patient_id)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        log_bd_processing(patient_id, "BD_INSERT", "SUCCESS", 
                                        f"Reporte BD generado e insertado correctamente ({manufacturer})")
                        logger.info(f"✓ BD procesado exitosamente para paciente {patient_id} ({manufacturer})")
                    else:
                        stderr_preview = result.stderr[:2000] if result.stderr else "Sin stderr"
                        stdout_preview = result.stdout[:2000] if result.stdout else "Sin stdout"
                        log_bd_processing(patient_id, "BD_INSERT", "ERROR", 
                                        f"Error ejecutando {extraction_script}:\nSTDERR: {stderr_preview}\nSTDOUT: {stdout_preview}")
                        logger.error(f"✗ Error procesando BD para paciente {patient_id}: {result.stderr[:200]}")
                        
                except subprocess.TimeoutExpired:
                    log_bd_processing(patient_id, "BD_INSERT", "ERROR", 
                                    f"Timeout ejecutando {extraction_script} (>30 segundos)")
                    logger.error(f"✗ Timeout procesando BD para paciente {patient_id}")
                except Exception as bd_error:
                    log_bd_processing(patient_id, "BD_INSERT", "ERROR", 
                                    f"Excepción ejecutando {extraction_script}: {str(bd_error)}")
                    logger.error(f"✗ Excepción procesando BD para paciente {patient_id}: {bd_error}")
        
        return 0x0000  # Success
    
    except Exception as e:
        logger.error(f"✗ Error guardando DICOM: {e}")
        return 0x0110  # Failure


def handle_release(event):
    """Handle association release - log when client disconnects."""
    logger.info(f"Association released")


def handle_assoc_accept(event):
    """Log after association is accepted."""
    # Este handler no se usa - usar EVT_REQUESTED en su lugar
    pass


def handle_requested(event):
    """
    Handle association request - accept all proposed presentation contexts.
    
    Simple implementation to work with PACS exactly as before.
    """
    remote_addr = getattr(event.assoc, 'remote', 'Unknown')
    assoc = event.assoc
    
    # Log association details
    logger.info(f"🔗 Association requested from {remote_addr}")
    logger.info(f"   Peer Max PDU Size: {assoc.peer_max_pdu_size:,} bytes ({assoc.peer_max_pdu_size/1024:.1f} KB)")
    
    # Log proposed contexts
    proposed_contexts = len(assoc.requested_contexts) if hasattr(assoc, 'requested_contexts') else 0
    if proposed_contexts > 0:
        logger.info(f"   Proposed Contexts: {proposed_contexts}")
    
    # Wait a moment and log after contexts are negotiated
    import time
    time.sleep(0.1)
    logger.info(f"✓ Accepting Association")
    logger.info(f"   Our Max PDU Size: {assoc.local_max_pdu_size:,} bytes ({assoc.local_max_pdu_size/1024:.1f} KB)")
    logger.info(f"   Peer Max PDU Size: {assoc.peer_max_pdu_size:,} bytes ({assoc.peer_max_pdu_size/1024:.1f} KB)")
    logger.info(f"   Negotiated PDU Size: {assoc.maximum_pdu_size:,} bytes ({assoc.maximum_pdu_size/1024:.1f} KB)")





def main():
    """
    Start the DICOM Receiver server.
    
    Listens on 0.0.0.0:5665 for incoming DICOM C-STORE associations.
    Supports multiple SOP classes and transfer syntaxes including JPEG 2000 Lossless.
    """
    logger.info("=" * 70)
    logger.info("DICOM Receiver Service")
    logger.info("=" * 70)
    
    # Create Application Entity
    ae = AE(ae_title="DICOM_RECEIVER")
    
    # Configure PDU and timeouts for better compatibility with PACS gateways
    # IMPORTANTE: Ser flexible en negociación de PDU - aceptar lo que el cliente proponga
    ae.maximum_pdu_size = 65536  # 64 KB - Flexible, acepta negociación del cliente
    ae.network_timeout = 600  # 10 minutos para operaciones de red
    ae.acse_timeout = 120  # 2 minutos para establecer asociación
    ae.dimse_timeout = 600  # 10 minutos para operaciones DIMSE (C-STORE)
    
    # Define supported transfer syntaxes
    # NOTE: Only uncompressed for now due to JPEG2000 issues with small PDU fragments
    # Will add compressed back after fixing negotiation
    transfer_syntaxes = [
        ImplicitVRLittleEndian,
        ExplicitVRLittleEndian,
    ]
    
    # Register supported SOP classes with their transfer syntaxes
    ae.add_supported_context(CTImageStorage, transfer_syntaxes)
    ae.add_supported_context(MRImageStorage, transfer_syntaxes)
    ae.add_supported_context(UltrasoundImageStorage, transfer_syntaxes)
    ae.add_supported_context(XRayAngiographicImageStorage, transfer_syntaxes)
    ae.add_supported_context(ComputedRadiographyImageStorage, transfer_syntaxes)
    ae.add_supported_context(DigitalXRayImageStorageForPresentation, transfer_syntaxes)
    ae.add_supported_context(DigitalXRayImageStorageForProcessing, transfer_syntaxes)
    ae.add_supported_context(SecondaryCaptureImageStorage, transfer_syntaxes)
    ae.add_supported_context(Verification)  # C-ECHO support
    
    # Event handlers
    handlers = [
        (events.EVT_REQUESTED, handle_requested),     # Log association request and negotiation
        (events.EVT_C_STORE, handle_store),           # Store DICOM files
        (events.EVT_RELEASED, handle_release),        # Log disconnections
    ]
    
    # Log configuration
    logger.info(f"Storage Directory: {STORAGE.absolute()}")
    logger.info(f"Pixel Output Directory: {PIXEL_OUTPUT.absolute()}")
    logger.info(f"Server Address: 0.0.0.0:5665")
    logger.info(f"AE Title: DICOM_RECEIVER")
    logger.info(f"Supported SOP Classes: {len(ae.supported_contexts)}")
    logger.info(f"Maximum PDU Size: {ae.maximum_pdu_size:,} bytes ({ae.maximum_pdu_size/1024:.1f} KB)")
    logger.info(f"Network Timeout: {ae.network_timeout} seconds")
    logger.info(f"DIMSE Timeout: {ae.dimse_timeout} seconds")
    logger.info(f"ACSE Timeout: {ae.acse_timeout} seconds")
    logger.info("=" * 70)
    logger.info("Starting server...")
    
    try:
        ae.start_server(("0.0.0.0", 5665), block=True, evt_handlers=handlers)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")


if __name__ == "__main__":
    main()

