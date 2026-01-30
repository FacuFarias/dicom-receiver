#!/usr/bin/env python3
import pydicom
from pathlib import Path

# Encontrar un archivo DICOM
base_path = Path("/home/ubuntu/DICOMReceiver/dicom_storage")
dicom_files = []

for patient_dir in base_path.iterdir():
    if not patient_dir.is_dir():
        continue
    for study_dir in patient_dir.iterdir():
        if not study_dir.is_dir():
            continue
        for file in study_dir.iterdir():
            if file.suffix.lower() not in ['.jpg', '.jpeg', '.png']:
                dicom_files.append(file)
                if len(dicom_files) >= 3:
                    break
        if len(dicom_files) >= 3:
            break
    if len(dicom_files) >= 3:
        break

print(f"Analizando {len(dicom_files)} archivos de muestra:\n")

for dicom_file in dicom_files:
    try:
        ds = pydicom.dcmread(str(dicom_file), force=True)
        print(f"Archivo: {dicom_file.name[:50]}...")
        print(f"  Modality: {getattr(ds, 'Modality', 'N/A')}")
        print(f"  Manufacturer: {getattr(ds, 'Manufacturer', 'N/A')}")
        print(f"  Model: {getattr(ds, 'ManufacturerModelName', 'N/A')}")
        print(f"  SOP Class: {getattr(ds, 'SOPClassUID', 'N/A')}")
        print()
    except Exception as e:
        print(f"Error en {dicom_file}: {e}\n")
