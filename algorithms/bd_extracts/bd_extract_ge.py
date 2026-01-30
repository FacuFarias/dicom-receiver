#!/usr/bin/env python3
"""
BD Extraction for GE Healthcare Lunar Equipment

GE Lunar equipment sends bone density reports as JPEG images embedded in DICOM.
Due to extremely low image quality, automated OCR extraction is not reliable.

This script logs the study and skips processing.

Author: System
Date: 2026-01-22
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
log_file = Path("/home/ubuntu/DICOMReceiver/logs/bd_processing.log")
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main(patient_id):
    """
    Log that GE Lunar studies cannot be automatically processed.
    
    Args:
        patient_id: Patient MRN/ID
    """
    logger.info("=" * 80)
    logger.info("BD EXTRACTION - GE Healthcare Lunar")
    logger.info("=" * 80)
    logger.info(f"Patient ID: {patient_id}")
    logger.warning("⚠️  GE Lunar studies cannot be automatically processed")
    logger.warning("    Reason: Image-based reports with insufficient OCR quality")
    logger.warning("    Action: Study skipped - requires manual review")
    logger.info("=" * 80)
    
    print("\n" + "=" * 80)
    print("⚠️  ESTUDIO GE LUNAR - NO PROCESABLE AUTOMÁTICAMENTE")
    print("=" * 80)
    print(f"Paciente: {patient_id}")
    print("\nMotivo: Los equipos GE Lunar envían reportes como imágenes JPEG de baja")
    print("        calidad que no pueden ser procesadas mediante OCR automático.")
    print("\nAcción: El estudio ha sido registrado pero requiere revisión manual.")
    print("=" * 80)
    
    return False  # Indicate processing was not completed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bd_extract_ge.py <patient_id>")
        sys.exit(1)
    
    patient_id = sys.argv[1]
    success = main(patient_id)
    
    sys.exit(0 if success else 1)
