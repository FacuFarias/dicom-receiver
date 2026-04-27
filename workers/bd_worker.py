#!/usr/bin/env python3
"""
BD Worker - Procesamiento Asíncrono de Estudios de Densitometría Ósea

Este worker maneja el procesamiento de estudios BD (Bone Density) en background,
incluyendo extracción de XML y ejecución de scripts de análisis con inserción a BD.

Características:
- Detección automática de fabricante (HOLOGIC vs GE Lunar)
- Procesamiento de imágenes BD y Structured Reports (SR)
- Timeout configurable para scripts de extracción
- Logging detallado de pasos de procesamiento
"""

import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import pydicom

logger = logging.getLogger(__name__)

# Directorios de logs
LOGS_DIR = Path('./logs')
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def log_bd_processing(patient_id: str, step: str, status: str, details: str):
    """
    Registra paso de procesamiento BD en archivo dedicado.
    
    Args:
        patient_id: ID del paciente
        step: Paso del procesamiento (ej: "RECEPCION", "DETECCION", "BD_INSERT ")
        status: Estado (ej: "SUCCESS", "ERROR", "WARNING", "INFO")
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


def detect_bd_manufacturer(ds: pydicom.Dataset) -> Tuple[Optional[str], str, str]:
    """
    Detecta fabricante y modelo de equipo BD.
    
    Args:
        ds: Dataset DICOM
        
    Returns:
        tuple: (extraction_script_path, manufacturer, model)
               extraction_script_path es None si no se reconoce el fabricante
    """
    manufacturer = getattr(ds, 'Manufacturer', 'UNKNOWN').strip().upper()
    model = getattr(ds, 'ManufacturerModelName', 'UNKNOWN').strip()
    
    # Detectar HOLOGIC
    if 'HOLOGIC' in manufacturer:
        extraction_script = '/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_hologic.py'
        logger.debug(f"   Equipo HOLOGIC detectado - Modelo: {model}")
        return extraction_script, manufacturer, model
    
    # Detectar GE Lunar
    elif 'GE' in manufacturer or 'LUNAR' in manufacturer or 'LUNAR' in model.upper():
        extraction_script = '/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_ge.py'
        logger.debug(f"   Equipo GE Lunar detectado - Modelo: {model}")
        return extraction_script, manufacturer, model
    
    else:
        logger.debug(f"   Fabricante no reconocido - Manufacturer: {manufacturer}, Model: {model}")
        return None, manufacturer, model


def process_bd_study_async(dicom_file_path: Path, patient_id: str, ds: Optional[pydicom.Dataset] = None) -> bool:
    """
    Worker function: Procesa estudio BD (imagen o SR) en background.
    
    Ejecuta scripts de extracción (bd_extract_hologic.py o bd_extract_ge.py)
    que parsean XML embebido y realizan INSERT/UPDATE a PostgreSQL.
    
    Args:
        dicom_file_path: Path al archivo DICOM
        patient_id: Patient ID
        ds: Dataset DICOM (opcional, se lee del archivo si no se provee)
        
    Returns:
        bool: True si procesamiento exitoso, False en caso contrario
    """
    try:
        # Leer archivo DICOM si no se proveyó dataset
        if ds is None:
            if not dicom_file_path.exists():
                logger.error(f"❌ Archivo no existe: {dicom_file_path}")
                log_bd_processing(patient_id, "ERROR", "ERROR", f"Archivo no existe: {dicom_file_path}")
                return False
            
            ds = pydicom.dcmread(str(dicom_file_path), force=True)
        
        modality = getattr(ds, 'Modality', 'UNKNOWN').strip().upper()
        file_size_mb = dicom_file_path.stat().st_size / (1024 * 1024)
        
        # Registrar recepción
        log_bd_processing(patient_id, "RECEPCION", "SUCCESS",
                         f"Archivo BD recibido - Modalidad: {modality}, Tamaño: {file_size_mb:.2f} MB")
        
        extraction_script = None
        manufacturer = "UNKNOWN"
        model = "UNKNOWN"
        
        # === Caso 1: Imagen BD (modality BD) ===
        if modality == 'BD':
            logger.info(f"📊 [ASYNC] Procesando imagen BD para paciente {patient_id}")
            
            # Detectar fabricante
            extraction_script, manufacturer, model = detect_bd_manufacturer(ds)
            
            if extraction_script:
                log_bd_processing(patient_id, "DETECCION", "INFO",
                                f"Equipo {manufacturer} detectado - Modelo: {model}")
            else:
                log_bd_processing(patient_id, "DETECCION", "WARNING",
                                f"Fabricante no reconocido - Manufacturer: {manufacturer}, Model: {model}")
        
        # === Caso 2: Structured Report (SR) de GE Lunar ===
        elif modality == 'SR':
            logger.info(f"📊 [ASYNC] Procesando SR para paciente {patient_id}")
            
            manufacturer = getattr(ds, 'Manufacturer', 'UNKNOWN').strip().upper()
            model = getattr(ds, 'ManufacturerModelName', 'UNKNOWN').strip()
            
            # Verificar si es GE Lunar
            if 'GE' in manufacturer or 'LUNAR' in manufacturer or 'LUNAR' in model.upper():
                logger.info(f"   SR de GE Lunar detectado")
                log_bd_processing(patient_id, "RECEPCION", "SUCCESS",
                                f"SR recibido - Fabricante: {manufacturer}, Modelo: {model}, "
                                f"Series: {getattr(ds, 'SeriesDescription', 'N/A')}, Tamaño: {file_size_mb:.2f} MB")
                log_bd_processing(patient_id, "DETECCION", "INFO",
                                f"Equipo GE Lunar detectado - Modelo: {model}")
                
                extraction_script = '/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_ge.py'
            else:
                logger.debug(f"   SR de fabricante no reconocido: {manufacturer}")
                log_bd_processing(patient_id, "DETECCION", "INFO",
                                f"SR de fabricante no procesable: {manufacturer}")
        
        # === Ejecutar script de extracción ===
        if extraction_script:
            log_bd_processing(patient_id, "ANALISIS", "SUCCESS",
                            f"Iniciando procesamiento con: {extraction_script}")
            
            try:
                logger.info(f"   Ejecutando: python3 {extraction_script} {patient_id}")
                
                result = subprocess.run(
                    ['python3', extraction_script, str(patient_id)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    log_bd_processing(patient_id, "BD_INSERT", "SUCCESS",
                                    f"Reporte BD generado e insertado correctamente ({manufacturer})")
                    logger.info(f"✅ BD procesado exitosamente para paciente {patient_id} ({manufacturer})")
                    return True
                else:
                    stderr_preview = result.stderr[:2000] if result.stderr else "Sin stderr"
                    stdout_preview = result.stdout[:2000] if result.stdout else "Sin stdout"
                    log_bd_processing(patient_id, "BD_INSERT", "ERROR",
                                    f"Error ejecutando {extraction_script}:\nSTDERR: {stderr_preview}\nSTDOUT: {stdout_preview}")
                    logger.error(f"❌ Error procesando BD para paciente {patient_id}: {result.stderr[:200]}")
                    return False
                    
            except subprocess.TimeoutExpired:
                log_bd_processing(patient_id, "BD_INSERT", "ERROR",
                                f"Timeout ejecutando {extraction_script} (>30 segundos)")
                logger.error(f"❌ Timeout procesando BD para paciente {patient_id}")
                return False
                
            except Exception as bd_error:
                log_bd_processing(patient_id, "BD_INSERT", "ERROR",
                                f"Excepción ejecutando {extraction_script}: {str(bd_error)}")
                logger.error(f"❌ Excepción procesando BD para paciente {patient_id}: {bd_error}", exc_info=True)
                return False
        else:
            logger.debug(f"   No hay script de extracción para este estudio BD")
            log_bd_processing(patient_id, "PROCESAMIENTO", "INFO",
                            "No se requiere procesamiento para este tipo de estudio")
            return True  # No es error, simplemente no hay procesamiento
        
    except Exception as e:
        logger.error(f"❌ Error en process_bd_study_async: {str(e)[:200]}", exc_info=True)
        log_bd_processing(patient_id, "ERROR", "ERROR", f"Excepción general: {str(e)[:200]}")
        return False


def extract_xml_from_dicom(dicom_path: Path) -> Optional[str]:
    """
    Extrae XML embebido del tag (0x0019, 0x1000) de DICOM.
    
    Args:
        dicom_path: Path al archivo DICOM
        
    Returns:
        str: XML extraído o None si no se encuentra
    """
    try:
        ds = pydicom.dcmread(str(dicom_path), stop_before_pixels=True, force=True)
        
        # Verificar si tiene XML en tag (0x0019, 0x1000)
        if (0x0019, 0x1000) not in ds:
            logger.debug(f"No se encontró XML en tag (0x0019, 0x1000)")
            return None
        
        # Extraer XML
        xml_data = ds[0x0019, 0x1000].value
        if isinstance(xml_data, bytes):
            xml_text = xml_data.decode('utf-8', errors='ignore')
        else:
            xml_text = str(xml_data)
        
        logger.debug(f"XML extraído exitosamente ({len(xml_text)} caracteres)")
        return xml_text
        
    except Exception as e:
        logger.error(f"Error extrayendo XML de DICOM: {e}")
        return None
