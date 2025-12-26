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
        
        # Si es Bone Density, extraer el pixel map
        if modality.upper() == 'BD':
            extract_and_save_pixel_map(filepath, patient_id, modality)
        
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

