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
import gc
from pathlib import Path
from datetime import datetime

import pydicom
import numpy as np
from PIL import Image

from pynetdicom import AE, events, StoragePresentationContexts
from pynetdicom.sop_class import (
    CTImageStorage,
    MRImageStorage,
    UltrasoundImageStorage,
    UltrasoundMultiFrameImageStorage,
    XRayAngiographicImageStorage,
    ComputedRadiographyImageStorage,
    DigitalXRayImageStorageForPresentation,
    DigitalXRayImageStorageForProcessing,
    SecondaryCaptureImageStorage,
    BasicTextSRStorage,
    EnhancedSRStorage,
    ComprehensiveSRStorage,
    Verification,
)
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    JPEGLossless,
    JPEG2000Lossless,
    JPEG2000,
)

# Import configuration
try:
    from config import US_FORWARDING, ASYNC_PROCESSING, PERFORMANCE
except ImportError:
    # Default configuration if config.py doesn't exist
    US_FORWARDING = {
        'enabled': False,
        'host': '192.168.1.100',
        'port': 104,
        'aet': 'US_PROCESSOR',
        'calling_aet': 'DICOM_RECEIVER',
        'timeout': 30,
        'retry_attempts': 3,
    }
    ASYNC_PROCESSING = {
        'enabled': False,
        'us_workers': 2,
        'bd_workers': 4,
        'pixel_workers': 2,
        'queue_monitor_interval': 60,
        'max_queue_size': 1000,
    }
    PERFORMANCE = {
        'immediate_response_mode': True,
        'log_per_instance': False,
    }

# Import queue manager and workers
from queue_manager import initialize_queue_manager, get_queue_manager
from workers.us_worker import forward_us_image_async, check_forwarding_criteria
from workers.bd_worker import process_bd_study_async
from workers.pixel_worker import extract_and_save_pixel_map_async

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


def log_us_reception(patient_id, study_uid, details=""):
    """
    Registra la recepción de estudios US (Ultrasound) en un archivo de log centralizado.
    
    Args:
        patient_id: ID del paciente
        study_uid: Study Instance UID
        details: Detalles adicionales (ej: número de archivo, tamaño, manufacturer)
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file = LOGS_DIR / "us_reception.log"
        
        log_entry = f"[{timestamp}] [Patient: {patient_id}] [Study: {study_uid}] {details}\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Error escribiendo log US: {e}")


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


def should_forward_us(ds):
    """
    Determina si un estudio US debe ser reenviado basándose en los criterios configurados.
    
    Verifica criterios como:
    - StudyDescription contiene términos específicos (ej: 'Thyroid')
    - BodyPartExamined contiene términos específicos
    - SeriesDescription contiene términos específicos
    
    Args:
        ds: Dataset DICOM (pydicom)
        
    Returns:
        tuple: (bool, str) - (should_forward, reason)
    """
    if not US_FORWARDING.get('enabled', False):
        return False, "US forwarding disabled in config"
    
    criteria = US_FORWARDING.get('criteria', {})
    
    # Verificar StudyDescription
    study_desc_terms = criteria.get('study_description_contains', [])
    if study_desc_terms:
        study_description = getattr(ds, 'StudyDescription', '').strip()
        for term in study_desc_terms:
            if term.lower() in study_description.lower():
                return True, f"StudyDescription contiene '{term}': '{study_description}'"
    
    # Verificar BodyPartExamined
    body_part_terms = criteria.get('body_part_contains', [])
    if body_part_terms:
        body_part = getattr(ds, 'BodyPartExamined', '').strip()
        for term in body_part_terms:
            if term.lower() in body_part.lower():
                return True, f"BodyPartExamined contiene '{term}': '{body_part}'"
    
    # Verificar SeriesDescription
    series_desc_terms = criteria.get('series_description_contains', [])
    if series_desc_terms:
        series_description = getattr(ds, 'SeriesDescription', '').strip()
        for term in series_desc_terms:
            if term.lower() in series_description.lower():
                return True, f"SeriesDescription contiene '{term}': '{series_description}'"
    
    return False, "No cumple criterios de forwarding"


def forward_us_image(dicom_file_path, patient_id, study_uid, ds=None):
    """
    Forward US (Ultrasound) DICOM images to another DICOM system for processing.
    
    This function sends DICOM files to a remote DICOM server using C-STORE protocol.
    It supports automatic retry on failure and comprehensive logging.
    
    Args:
        dicom_file_path: Path object pointing to the DICOM file to forward
        patient_id: Patient ID for logging purposes
        study_uid: Study Instance UID for logging purposes
        ds: Dataset DICOM (opcional, se lee del archivo si no se provee)
        
    Returns:
        bool: True if forwarding was successful, False otherwise
    """
    if not US_FORWARDING.get('enabled', False):
        logger.debug("US forwarding is disabled in configuration")
        return False
    
    try:
        # Read the DICOM file if not provided
        if ds is None:
            ds = pydicom.dcmread(str(dicom_file_path), force=True)
        
        # Asegurar que tiene Transfer Syntax UID en file_meta (necesario para C-STORE)
        if not hasattr(ds, 'file_meta'):
            ds.file_meta = pydicom.dataset.FileMetaDataset()
        
        # Si no tiene Transfer Syntax, usar Explicit VR Little Endian por defecto
        if not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            from pydicom.uid import ExplicitVRLittleEndian
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            logger.debug("   Added Transfer Syntax UID: Explicit VR Little Endian")
        
        # Extract configuration
        dest_host = US_FORWARDING['host']
        dest_port = US_FORWARDING['port']
        dest_aet = US_FORWARDING['aet']
        calling_aet = US_FORWARDING.get('calling_aet', 'DICOM_RECEIVER')
        timeout = US_FORWARDING.get('timeout', 30)
        retry_attempts = US_FORWARDING.get('retry_attempts', 3)
        
        logger.info(f"🔄 Forwarding US image to {dest_aet}@{dest_host}:{dest_port}")
        logger.info(f"   Patient: {patient_id}, Study: {study_uid}")
        
        # Create Application Entity for sending
        ae = AE(ae_title=calling_aet)
        ae.requested_contexts = StoragePresentationContexts
        ae.network_timeout = timeout
        ae.acse_timeout = timeout
        ae.dimse_timeout = timeout
        
        # Attempt to send with retries
        for attempt in range(1, retry_attempts + 1):
            try:
                # Establish association
                assoc = ae.associate(dest_host, dest_port, ae_title=dest_aet)
                
                if assoc.is_established:
                    # Send C-STORE request
                    status = assoc.send_c_store(ds)
                    
                    # Release association
                    assoc.release()
                    
                    # Check status
                    if status and status.Status == 0x0000:
                        logger.info(f"✓ US image forwarded successfully (attempt {attempt}/{retry_attempts})")
                        logger.info(f"   Destination: {dest_aet}@{dest_host}:{dest_port}")
                        return True
                    else:
                        status_code = status.Status if status else 'Unknown'
                        logger.warning(f"⚠ C-STORE failed with status: 0x{status_code:04X} (attempt {attempt}/{retry_attempts})")
                else:
                    logger.warning(f"⚠ Association rejected by {dest_aet} (attempt {attempt}/{retry_attempts})")
                    
            except Exception as send_error:
                logger.warning(f"⚠ Error sending to {dest_aet} (attempt {attempt}/{retry_attempts}): {str(send_error)[:100]}")
                
                # Wait before retry (except on last attempt)
                if attempt < retry_attempts:
                    import time
                    time.sleep(2)
        
        # All attempts failed
        logger.error(f"✗ Failed to forward US image after {retry_attempts} attempts")
        logger.error(f"   Patient: {patient_id}, File: {dicom_file_path.name}")
        return False
        
    except Exception as e:
        logger.error(f"✗ Error in forward_us_image: {str(e)[:200]}")
        logger.error(f"   Patient: {patient_id}, File: {dicom_file_path}")
        return False


def handle_store(event):
    """
    Handle C-STORE request.
    
    Receives DICOM dataset and saves it in structured directory:
    ./dicom_storage/{PatientID}/{StudyInstanceUID}/{raw_bytes_no_extension}
    
    Para archivos BD (Bone Density), también extrae el pixel map como JPEG.
    Soporta modo ASYNC (respuesta inmediata) y modo SYNC (legacy bloqueante).
    
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
        
        # Create directory structure
        patient_dir = STORAGE / str(patient_id)
        study_dir = patient_dir / str(study_uid)
        study_dir.mkdir(parents=True, exist_ok=True)
        
        # ===================================================================
        # DETECCION DE DUPLICADOS - Verificar PRIMERO antes de procesar píxeles
        # ===================================================================
        # Buscar archivos existentes con el mismo SOPInstanceUID
        existing_files = list(study_dir.glob(f"*_{sop_uid}"))
        
        if existing_files:
            # Archivo duplicado detectado - NO procesar, responder inmediatamente
            existing_file = existing_files[0]
            file_size_bytes = existing_file.stat().st_size
            file_size_mb = file_size_bytes / (1024 * 1024)
            
            # Log reducido para duplicados (nivel DEBUG para evitar spam)
            logger.debug(f"⚠️ DUPLICADO: {patient_id}/{sop_uid[:16]}... ({file_size_mb:.1f}MB)")
            
            # Registrar en log de US si es ultrasound
            if modality.upper() == 'US':
                log_us_reception(patient_id, study_uid, 
                               f"DUPLICADO - {sop_uid[:16]}...")
            
            # Liberar memoria del dataset inmediatamente
            del ds
            gc.collect()
            
            # IMPORTANTE: Responder con éxito (0x0000) para que el equipo sepa que ya lo tenemos
            return 0x0000
        
        # ===================================================================
        # NO ES DUPLICADO - Proceder con validación y guardado
        # ===================================================================
        
        # Log connection details from OnePACS
        remote = getattr(event.assoc, 'remote', None)
        context = getattr(event.context, 'transfer_syntax', 'Unknown')
        
        log_level = logging.INFO if PERFORMANCE.get('log_per_instance', False) else logging.DEBUG
        logger.log(log_level, f"📥 C-STORE Request: {modality} from {remote}")
        logger.log(log_level, f"   Transfer Syntax: {str(context)[:50]}")
        
        # Validar integridad del DICOM
        is_valid, validation_msg = validate_pixel_data(ds)
        
        # NO RECHAZAR - aceptar incluso truncados para poder recuperarlos
        if not is_valid:
            logger.warning(f"⚠ {validation_msg} - ACEPTANDO IGUAL (posible truncado de transmisión)")
            logger.warning(f"   Paciente: {patient_id}, Modalidad: {modality}")
        
        # ===================================================================
        # GUARDADO - No es duplicado, proceder con guardado normal
        # ===================================================================
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
        logger.log(log_level, f"   └─ Tamaño: {file_size_bytes:,} bytes ({file_size_mb:.2f} MB)")
        logger.log(log_level, f"   └─ {validation_msg}")
        
        # ===================================================================
        # ASYNC MODE: Return C-STORE-RSP immediately, process in background
        # ===================================================================
        async_enabled = ASYNC_PROCESSING.get('enabled', False)
        immediate_response = PERFORMANCE.get('immediate_response_mode', True)
        defer_processing = ASYNC_PROCESSING.get('defer_processing', False)
        
        if async_enabled and immediate_response:
            # Get queue manager
            queue_mgr = get_queue_manager()
            
            # BACKPRESSURE CHECK: Degrade to sync if queues saturated
            if queue_mgr and queue_mgr.is_saturated():
                logger.warning(f"⚠️  BACKPRESSURE DETECTED - Queues saturated, processing {modality} SYNCHRONOUSLY this time")
                # Fall through to sync processing below (don't return early)
            else:
                # =========================================================================
                # MODO DEFER: Prioridad en recepción - diferir procesamiento hasta que termine
                # =========================================================================
                if defer_processing and queue_mgr:
                    if modality.upper() == 'BD':
                        # Diferir procesamiento BD hasta que el estudio esté completo
                        queue_mgr.defer_study_job(study_uid, 'bd', process_bd_study_async, filepath, patient_id)
                        queue_mgr.defer_study_job(study_uid, 'pixel', extract_and_save_pixel_map_async, filepath, patient_id, modality)
                        logger.debug(f"   [DEFER] BD + Pixel diferidos hasta completar recepción")
                    
                    elif modality.upper() == 'SR':
                        # Diferir procesamiento SR hasta que el estudio esté completo
                        queue_mgr.defer_study_job(study_uid, 'bd', process_bd_study_async, filepath, patient_id)
                        logger.debug(f"   [DEFER] SR diferido hasta completar recepción")
                    
                    elif modality.upper() == 'US':
                        # Create US directory copy
                        us_storage = STORAGE / "US" / str(patient_id) / str(study_uid)
                        us_storage.mkdir(parents=True, exist_ok=True)
                        us_filepath = us_storage / filename
                        try:
                            import os
                            os.link(str(filepath), str(us_filepath))
                        except:
                            import shutil
                            shutil.copy2(str(filepath), str(us_filepath))
                        
                        # Log reception
                        log_us_reception(patient_id, study_uid, f"Recibido - Tamaño: {file_size_mb:.2f} MB")
                        
                        # Check forwarding criteria
                        criteria = US_FORWARDING.get('criteria', {})
                        if check_forwarding_criteria(ds, criteria) and US_FORWARDING.get('enabled', False):
                            # Diferir reenvío US hasta que el estudio esté completo
                            queue_mgr.defer_study_job(study_uid, 'us', forward_us_image_async, filepath, patient_id, study_uid, US_FORWARDING)
                            logger.debug(f"   [DEFER] US forwarding diferido hasta completar recepción")
                            log_us_reception(patient_id, study_uid, "FORWARD_DEFERRED - Cumple criterios")
                        else:
                            logger.debug(f"   US no cumple criterios o forwarding deshabilitado")
                    
                    # Return SUCCESS immediately - processing happens AFTER study completion
                    return 0x0000
                
                # =========================================================================
                # MODO IMMEDIATO (anterior): Procesar mientras se recibe
                # =========================================================================
                else:
                    # Normal async processing - submit to queues and return immediately
                    if modality.upper() == 'BD':
                        # Queue BD processing (subprocess + DB insert)
                        if queue_mgr:
                            queue_mgr.submit_bd_job(process_bd_study_async, filepath, patient_id)
                            logger.debug(f"   [ASYNC] BD processing queued")
                            
                            # Queue pixel extraction if needed (low priority)
                            queue_mgr.submit_pixel_job(extract_and_save_pixel_map_async, filepath, patient_id, modality)
                            logger.debug(f"   [ASYNC] Pixel extraction queued")
                    
                    elif modality.upper() == 'SR':
                        # Queue SR processing (GE Lunar BD reports)
                        if queue_mgr:
                            queue_mgr.submit_bd_job(process_bd_study_async, filepath, patient_id)
                            logger.debug(f"   [ASYNC] SR processing queued")
                    
                    elif modality.upper() == 'US':
                        # Create US directory copy
                        us_storage = STORAGE / "US" / str(patient_id) / str(study_uid)
                        us_storage.mkdir(parents=True, exist_ok=True)
                        us_filepath = us_storage / filename
                        try:
                            import os
                            os.link(str(filepath), str(us_filepath))
                        except:
                            import shutil
                            shutil.copy2(str(filepath), str(us_filepath))
                        
                        # Log reception
                        log_us_reception(patient_id, study_uid, f"Recibido - Tamaño: {file_size_mb:.2f} MB")
                        
                        # Check forwarding criteria
                        criteria = US_FORWARDING.get('criteria', {})
                        if check_forwarding_criteria(ds, criteria) and US_FORWARDING.get('enabled', False):
                            # Queue US forwarding
                            if queue_mgr:
                                queue_mgr.submit_us_job(forward_us_image_async, filepath, patient_id, study_uid, US_FORWARDING)
                                logger.debug(f"   [ASYNC] US forwarding queued")
                                log_us_reception(patient_id, study_uid, "FORWARD_QUEUED - Cumple criterios")
                        else:
                            logger.debug(f"   US no cumple criterios o forwarding deshabilitado")
                    
                    # Return SUCCESS immediately - processing happens in background
                    return 0x0000
        
        # ===================================================================
        # SYNC MODE (Legacy): Process everything before returning
        # ===================================================================
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
                # Detectar si es Desert o Memorial para usar el script correcto
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
                
                # DETECTAR DESERT vs MEMORIAL basado en presencia de ScanMode2
                is_memorial = False
                if (0x0019, 0x1000) in ds:
                    try:
                        xml_data = ds[0x0019, 0x1000].value
                        if isinstance(xml_data, bytes):
                            xml_text = xml_data.decode('utf-8', errors='ignore')
                        else:
                            xml_text = str(xml_data)
                        
                        # Si tiene ScanMode2 → Memorial (dual-hip)
                        # Si NO tiene ScanMode2 → Desert (single-hip)
                        import re
                        is_memorial = bool(re.search(r'ScanMode2\s*=\s*"([^"]+)"', xml_text))
                    except Exception as xml_err:
                        logger.debug(f"Error detectando formato HOLOGIC: {xml_err}")
                        is_memorial = False  # Por defecto asumir Desert
                
                # Asignar script correcto según detección
                if is_memorial:
                    extraction_script = '/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_hologic_memorial.py'
                    log_bd_processing(patient_id, "DETECCION", "INFO", 
                                    "Formato MEMORIAL detectado (dual-hip) - usando bd_extract_hologic_memorial.py")
                else:
                    extraction_script = '/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_hologic_desert.py'
                    log_bd_processing(patient_id, "DETECCION", "INFO", 
                                    "Formato DESERT detectado (single-hip) - usando bd_extract_hologic_desert.py")
                
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
                            # extraction_ok = extract_and_save_pixel_map(filepath, patient_id, modality)
                            # if extraction_ok:
                            #     log_bd_processing(patient_id, "PIXEL_MAP", "SUCCESS", 
                            #                     "Pixel map extraído para OCR de FRAX")
                            # else:
                            #     log_bd_processing(patient_id, "PIXEL_MAP", "WARNING", 
                            #                     "No se pudo extraer pixel map - FRAX podría no estar disponible")
                            log_bd_processing(patient_id, "PIXEL_MAP", "INFO",
                                            "no se obtuvieron los valores de FRAX adecuadamente. Se utilizaría pixel extraction pero no está disponible actualmente.")
                
                # HOLOGIC: procesar todos los archivos (HIP, LSPINE, FOREARM)
                # El script de extracción consolidará los datos en el mismo registro por ACC
                log_bd_processing(patient_id, "ANALISIS", "INFO", 
                                f"HOLOGIC BD {body_part} recibido - será procesado y consolidado por ACC")
                
            elif 'GE' in manufacturer or 'LUNAR' in manufacturer.upper() or 'LUNAR' in model.upper():
                # Equipos GE Lunar: envían archivos BD (imágenes) Y SR (datos estructurados) por separado
                # NO procesar aquí - esperar a que lleguen los archivos SR
                log_bd_processing(patient_id, "DETECCION", "INFO", 
                                f"Equipo GE Lunar detectado - Modelo: {model}")
                log_bd_processing(patient_id, "DETECCION", "INFO", 
                                f"Archivo BD recibido - esperando archivos SR para procesar")
                log_bd_processing(patient_id, "ANALISIS", "INFO", 
                                f"GE Lunar: Archivo de imagen guardado - procesamiento ocurrirá cuando lleguen los SR")
                
                # NO ejecutar extraction_script aquí - se ejecutará cuando lleguen los SR
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
        
        # Si es Structured Report (SR) de GE Lunar, procesar BD
        elif modality.upper() == 'SR':
            # Detectar si es de GE Lunar
            manufacturer = getattr(ds, 'Manufacturer', 'UNKNOWN').strip().upper()
            model = getattr(ds, 'ManufacturerModelName', 'UNKNOWN').strip()
            
            if 'GE' in manufacturer or 'LUNAR' in manufacturer or 'LUNAR' in model.upper():
                logger.info(f"📊 SR de GE Lunar detectado - procesando BD")
                log_bd_processing(patient_id, "RECEPCION", "SUCCESS", 
                                f"SR recibido - Fabricante: {manufacturer}, Modelo: {model}, Series: {getattr(ds, 'SeriesDescription', 'N/A')}, Tamaño: {file_size_mb:.2f} MB")
                log_bd_processing(patient_id, "DETECCION", "INFO", 
                                f"Equipo GE Lunar detectado - Modelo: {model}")
                log_bd_processing(patient_id, "DETECCION", "INFO", 
                                f"SR recibido - iniciando procesamiento con bd_extract_ge.py")
                
                # Ejecutar extracción GE
                extraction_script = '/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_ge.py'
                try:
                    result = subprocess.run(
                        ['python3', extraction_script, str(patient_id)],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        log_bd_processing(patient_id, "BD_INSERT", "SUCCESS", 
                                        f"Reporte BD generado e insertado correctamente (GE LUNAR SR)")
                        logger.info(f"✓ BD procesado exitosamente desde SR para paciente {patient_id}")
                    else:
                        stderr_preview = result.stderr[:2000] if result.stderr else "Sin stderr"
                        stdout_preview = result.stdout[:2000] if result.stdout else "Sin stdout"
                        log_bd_processing(patient_id, "BD_INSERT", "ERROR", 
                                        f"Error ejecutando {extraction_script}:\nSTDERR: {stderr_preview}\nSTDOUT: {stdout_preview}")
                        logger.error(f"✗ Error procesando SR para paciente {patient_id}: {result.stderr[:200]}")
                        
                except subprocess.TimeoutExpired:
                    log_bd_processing(patient_id, "BD_INSERT", "ERROR", 
                                    f"Timeout ejecutando {extraction_script} (>30 segundos)")
                    logger.error(f"✗ Timeout procesando SR para paciente {patient_id}")
                except Exception as bd_error:
                    log_bd_processing(patient_id, "BD_INSERT", "ERROR", 
                                    f"Excepción ejecutando {extraction_script}: {str(bd_error)}")
                    logger.error(f"✗ Excepción procesando SR para paciente {patient_id}: {bd_error}")
            else:
                logger.info(f"📄 SR de otro fabricante ({manufacturer}) - solo guardando")
        
        # Si es Ultrasound, guardar en dicom_storage/US y registrar en log
        elif modality.upper() == 'US':
            logger.info(f"🔍 US (Ultrasound) detectado")
            
            # Crear directorio US organizado por paciente y estudio
            us_storage = STORAGE / "US" / str(patient_id) / str(study_uid)
            us_storage.mkdir(parents=True, exist_ok=True)
            
            # Crear copia/enlace simbólico en directorio US
            us_filepath = us_storage / filename
            try:
                # Intentar crear enlace duro (más eficiente, mismo inode)
                import os
                os.link(str(filepath), str(us_filepath))
                logger.info(f"✓ US guardado en directorio US: US/{patient_id}/{study_uid}/{filename}")
            except Exception as link_error:
                # Si falla enlace duro, copiar archivo
                import shutil
                shutil.copy2(str(filepath), str(us_filepath))
                logger.info(f"✓ US copiado a directorio US: US/{patient_id}/{study_uid}/{filename}")
            
            # Extraer información adicional para el log
            manufacturer = getattr(ds, 'Manufacturer', 'UNKNOWN').strip()
            model = getattr(ds, 'ManufacturerModelName', 'UNKNOWN').strip()
            body_part = getattr(ds, 'BodyPartExamined', 'UNKNOWN')
            series_description = getattr(ds, 'SeriesDescription', 'UNKNOWN')
            
            # Registrar en log de recepción US
            log_details = f"Recibido - Fabricante: {manufacturer}, Modelo: {model}, BodyPart: {body_part}, Series: {series_description}, Tamaño: {file_size_mb:.2f} MB, Archivo: {filename}"
            log_us_reception(patient_id, study_uid, log_details)
            logger.info(f"✓ Recepción US registrada en log")
            
            # Verificar si debe ser reenviado según criterios configurados
            should_forward, reason = should_forward_us(ds)
            
            if should_forward:
                logger.info(f"🎯 US cumple criterios de forwarding: {reason}")
                study_description = getattr(ds, 'StudyDescription', 'N/A')
                logger.info(f"   StudyDescription: {study_description}")
                
                # Reenviar al sistema de procesamiento US
                forward_success = forward_us_image(filepath, patient_id, study_uid, ds=ds)
                
                if forward_success:
                    logger.info(f"✓ US study forwarded successfully")
                    logger.info(f"   Patient: {patient_id}, Study: {study_uid}")
                    # Registrar forward exitoso en log
                    dest_info = f"{US_FORWARDING.get('host')}:{US_FORWARDING.get('port')} ({US_FORWARDING.get('aet')})"
                    log_us_reception(patient_id, study_uid, f"FORWARD_SUCCESS - Enviado a {dest_info} - {reason}")
                else:
                    logger.warning(f"⚠ US study forwarding failed (check logs above)")
                    logger.warning(f"   Patient: {patient_id}, Study: {study_uid}")
                    logger.warning(f"   File saved locally: {filepath}")
                    log_us_reception(patient_id, study_uid, f"FORWARD_FAILED - {reason}")
            else:
                logger.info(f"ℹ️  US no cumple criterios de forwarding: {reason}")
                study_description = getattr(ds, 'StudyDescription', 'N/A')
                logger.info(f"   StudyDescription: {study_description}")
                logger.info(f"   File saved locally only")
        
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
    
    # Log association details
    logger.info(f"🔗 Association requested from {remote_addr}")
    logger.info(f"✓ Accepting Association")





def main():
    """
    Start the DICOM Receiver server.
    
    Listens on 0.0.0.0:5665 for incoming DICOM C-STORE associations.
    Supports multiple SOP classes and transfer syntaxes including JPEG 2000 Lossless.
    """
    logger.info("=" * 70)
    logger.info("DICOM Receiver Service")
    logger.info("=" * 70)
    
    # Initialize queue manager for async processing
    queue_mgr = initialize_queue_manager(ASYNC_PROCESSING)
    if ASYNC_PROCESSING.get('enabled', False):
        logger.info(f"✅ Modo ASÍNCRONO habilitado - respuesta inmediata C-STORE-RSP")
        logger.info(f"   US workers: {ASYNC_PROCESSING.get('us_workers', 2)}")
        logger.info(f"   BD workers: {ASYNC_PROCESSING.get('bd_workers', 4)}")
        logger.info(f"   Pixel workers: {ASYNC_PROCESSING.get('pixel_workers', 2)}")
    else:
        logger.info(f"⚠️  Modo SÍNCRONO (legacy) - procesamiento bloqueante")
    
    # Create Application Entity
    ae = AE(ae_title="DICOM_RECEIVER")
    
    # Configure PDU and timeouts for better compatibility with PACS gateways
    # IMPORTANTE: Ser flexible en negociación de PDU - aceptar lo que el cliente proponga
    ae.maximum_pdu_size = 65536  # 64 KB - Flexible, acepta negociación del cliente
    ae.network_timeout = 600  # 10 minutos para operaciones de red
    ae.acse_timeout = 120  # 2 minutos para establecer asociación
    ae.dimse_timeout = 600  # 10 minutos para operaciones DIMSE (C-STORE)
    
    # Define supported transfer syntaxes
    # NOTE: JPEG2000 commented due to PDU fragmentation issues with dcm4chee 2
    # See TRANSFER_SYNTAX_README.md for details
    transfer_syntaxes = [
        ImplicitVRLittleEndian,
        ExplicitVRLittleEndian,
        JPEGLossless,  # Added for BD/US support
        # JPEG2000Lossless,  # Commented: PDU fragmentation issues
        # JPEG2000,  # Commented: PDU fragmentation issues
    ]
    
    # Register supported SOP classes with their transfer syntaxes
    ae.add_supported_context(CTImageStorage, transfer_syntaxes)
    ae.add_supported_context(MRImageStorage, transfer_syntaxes)
    ae.add_supported_context(UltrasoundImageStorage, transfer_syntaxes)
    ae.add_supported_context(UltrasoundMultiFrameImageStorage, transfer_syntaxes)  # Added
    ae.add_supported_context(XRayAngiographicImageStorage, transfer_syntaxes)
    ae.add_supported_context(ComputedRadiographyImageStorage, transfer_syntaxes)
    ae.add_supported_context(DigitalXRayImageStorageForPresentation, transfer_syntaxes)
    ae.add_supported_context(DigitalXRayImageStorageForProcessing, transfer_syntaxes)
    ae.add_supported_context(SecondaryCaptureImageStorage, transfer_syntaxes)
    
    # DICOM Structured Report support (used by GE Lunar BD equipment)
    ae.add_supported_context(BasicTextSRStorage, transfer_syntaxes)
    ae.add_supported_context(EnhancedSRStorage, transfer_syntaxes)
    ae.add_supported_context(ComprehensiveSRStorage, transfer_syntaxes)
    
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
        # Graceful shutdown of queue manager
        queue_mgr = get_queue_manager()
        if queue_mgr:
            queue_mgr.shutdown(timeout=30)
    except Exception as e:
        logger.error(f"Server error: {e}")
        # Graceful shutdown of queue manager
        queue_mgr = get_queue_manager()
        if queue_mgr:
            queue_mgr.shutdown(timeout=30)


if __name__ == "__main__":
    main()

