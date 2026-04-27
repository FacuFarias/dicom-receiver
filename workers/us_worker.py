#!/usr/bin/env python3
"""
US Worker - Procesamiento Asíncrono de Reenvío de Imágenes Ultrasound

Este worker maneja el reenvío de imágenes US a servidor AI externo en background,
liberando el handler C-STORE para responder inmediatamente al gateway.

Características:
- Reintentos automáticos (configurable)
- Logging detallado de éxitos/fallos
- Timeout configurable por intento
- Manejo de errores sin afectar el gateway
"""

import logging
import time
from pathlib import Path
from typing import Optional
import pydicom
from pynetdicom import AE, StoragePresentationContexts
from pydicom.uid import ExplicitVRLittleEndian

logger = logging.getLogger(__name__)

# Arch <br/>ivo de log dedicado para fallos de reenvío
FAILED_FORWARDING_LOG = Path('./logs/us_forwarding_failed.log')


def setup_failed_log():
    """Configura logger dedicado para fallos de reenvío."""
    FAILED_FORWARDING_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    failed_logger = logging.getLogger('us_forwarding_failed')
    failed_logger.setLevel(logging.ERROR)
    
    if not failed_logger.handlers:
        handler = logging.FileHandler(FAILED_FORWARDING_LOG)
        formatter = logging.Formatter('%(asctime)s - %(message)s')
        handler.setFormatter(formatter)
        failed_logger.addHandler(handler)
    
    return failed_logger


failed_log = setup_failed_log()


def forward_us_image_async(dicom_file_path: Path, patient_id: str, study_uid: str, 
                          config: dict, ds: Optional[pydicom.Dataset] = None) -> bool:
    """
    Worker function: Reenvía imagen US a servidor DICOM externo.
    
    Esta función se ejecuta en un thread de background pool. No debe bloquear
    el handler C-STORE principal.
    
    Args:
        dicom_file_path: Path al archivo DICOM a reenviar
        patient_id: Patient ID para logging
        study_uid: Study Instance UID para logging
        config: Diccionario US_FORWARDING con configuración
        ds: Dataset DICOM (opcional, se lee del archivo si no se provee)
        
    Returns:
        bool: True si reenvío exitoso, False en caso contrario
    """
    if not config.get('enabled', False):
        logger.debug("Reenvío US deshabilitado en configuración")
        return False
    
    try:
        # Leer archivo DICOM si no se proveyó dataset
        if ds is None:
            if not dicom_file_path.exists():
                logger.error(f"❌ Archivo no existe: {dicom_file_path}")
                failed_log.error(f"MISSING_FILE | {patient_id} | {study_uid} | {dicom_file_path}")
                return False
            
            ds = pydicom.dcmread(str(dicom_file_path), force=True)
        
        # Asegurar que tiene Transfer Syntax UID en file_meta (necesario para C-STORE)
        if not hasattr(ds, 'file_meta'):
            ds.file_meta = pydicom.dataset.FileMetaDataset()
        
        # Si no tiene Transfer Syntax, usar Explicit VR Little Endian por defecto
        if not hasattr(ds.file_meta, 'TransferSyntaxUID'):
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            logger.debug("   Transfer Syntax agregado: Explicit VR Little Endian")
        
        # Extraer configuración
        dest_host = config['host']
        dest_port = config['port']
        dest_aet = config['aet']
        calling_aet = config.get('calling_aet', 'DICOM_RECEIVER')
        timeout = config.get('timeout', 30)
        retry_attempts = config.get('retry_attempts', 3)
        
        logger.info(f"🔄 [ASYNC] Reenviando imagen US a {dest_aet}@{dest_host}:{dest_port}")
        logger.info(f"   Paciente: {patient_id}, Estudio: {study_uid}")
        
        # Crear Application Entity para envío
        ae = AE(ae_title=calling_aet)
        ae.requested_contexts = StoragePresentationContexts
        ae.network_timeout = timeout
        ae.acse_timeout = timeout
        ae.dimse_timeout = timeout
        
        # Intentar enviar con reintentos
        for attempt in range(1, retry_attempts + 1):
            try:
                # Establecer asociación
                assoc = ae.associate(dest_host, dest_port, ae_title=dest_aet)
                
                if assoc.is_established:
                    # Enviar C-STORE request
                    status = assoc.send_c_store(ds)
                    
                    # Liberar asociación
                    assoc.release()
                    
                    # Verificar status
                    if status and status.Status == 0x0000:
                        logger.info(f"✅ Imagen US reenviada exitosamente (intento {attempt}/{retry_attempts})")
                        logger.info(f"   Destino: {dest_aet}@{dest_host}:{dest_port}")
                        return True
                    else:
                        status_code = status.Status if status else 'Unknown'
                        logger.warning(f"⚠️  C-STORE falló con status: 0x{status_code:04X} (intento {attempt}/{retry_attempts})")
                else:
                    logger.warning(f"⚠️  Asociación rechazada por {dest_aet} (intento {attempt}/{retry_attempts})")
                    
            except Exception as send_error:
                logger.warning(f"⚠️  Error enviando a {dest_aet} (intento {attempt}/{retry_attempts}): {str(send_error)[:100]}")
                
                # Esperar antes de reintentar (excepto en último intento)
                if attempt < retry_attempts:
                    time.sleep(2)
        
        # Todos los intentos fallaron
        logger.error(f"❌ Falló reenvío de imagen US después de {retry_attempts} intentos")
        logger.error(f"   Paciente: {patient_id}, Archivo: {dicom_file_path.name}")
        
        # Registrar en log de fallos para revisión manual
        failed_log.error(f"FAILED_AFTER_RETRIES | {patient_id} | {study_uid} | {dicom_file_path} | {retry_attempts} intentos")
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Error en forward_us_image_async: {str(e)[:200]}", exc_info=True)
        failed_log.error(f"EXCEPTION | {patient_id} | {study_uid} | {dicom_file_path} | {str(e)[:200]}")
        return False


def check_forwarding_criteria(ds: pydicom.Dataset, criteria: dict) -> bool:
    """
    Verifica si una imagen US cumple criterios para reenvío.
    
    Args:
        ds: Dataset DICOM
        criteria: Diccionario con criterios de filtrado (study_description_contains, etc.)
        
    Returns:
        bool: True si cumple algún criterio (OR logic), False en caso contrario
    """
    # Extraer términos de búsqueda de cada campo
    study_desc_terms = criteria.get('study_description_contains', [])
    body_part_terms = criteria.get('body_part_contains', [])
    series_desc_terms = criteria.get('series_description_contains', [])
    
    # Obtener valores del DICOM (case-insensitive)
    study_description = str(getattr(ds, 'StudyDescription', '')).upper()
    body_part = str(getattr(ds, 'BodyPartExamined', '')).upper()
    series_description = str(getattr(ds, 'SeriesDescription', '')).upper()
    
    # Verificar StudyDescription
    for term in study_desc_terms:
        if term.upper() in study_description:
            logger.debug(f"✓ Criterio cumplido: StudyDescription contiene '{term}'")
            return True
    
    # Verificar BodyPartExamined
    for term in body_part_terms:
        if term.upper() in body_part:
            logger.debug(f"✓ Criterio cumplido: BodyPartExamined contiene '{term}'")
            return True
    
    # Verificar SeriesDescription
    for term in series_desc_terms:
        if term.upper() in series_description:
            logger.debug(f"✓ Criterio cumplido: SeriesDescription contiene '{term}'")
            return True
    
    logger.debug("✗ No cumple criterios de reenvío")
    return False
