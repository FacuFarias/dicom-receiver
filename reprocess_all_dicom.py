#!/usr/bin/env python3
"""
Script para reprocesar todos los estudios DICOM almacenados.
Extrae XML de los DICOM y ejecuta bd_extract_hologic.py
"""

import os
import sys
import subprocess
import pydicom
from pathlib import Path

def extract_xml_from_dicom(dicom_path, output_dir):
    """Extrae XML embedded del DICOM y lo guarda"""
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True, force=True)
        
        # Verificar si tiene XML en tag (0x0019, 0x1000)
        if (0x0019, 0x1000) not in ds:
            return None
        
        # Extraer XML
        xml_data = ds[0x0019, 0x1000].value
        if isinstance(xml_data, bytes):
            xml_text = xml_data.decode('utf-8', errors='ignore')
        else:
            xml_text = str(xml_data)
        
        # Guardar XML
        xml_filename = f"HOLOGIC_{ds.SOPInstanceUID}.xml"
        xml_path = os.path.join(output_dir, xml_filename)
        
        with open(xml_path, 'w', encoding='utf-8') as f:
            f.write(xml_text)
        
        return xml_path
    except Exception as e:
        pass
    
    return None

def process_patient_folder(patient_folder):
    """Procesa una carpeta de paciente"""
    mrn = os.path.basename(patient_folder)
    
    # Buscar archivos DICOM
    dicom_files = []
    for root, dirs, files in os.walk(patient_folder):
        for f in files:
            if not f.endswith('.xml') and not f.endswith('.jpg') and not f.endswith('.jpeg'):
                dicom_files.append(os.path.join(root, f))
    
    if not dicom_files:
        return False
    
    # Extraer XMLs
    xml_extracted = False
    for dicom_file in dicom_files:
        xml_path = extract_xml_from_dicom(dicom_file, patient_folder)
        if xml_path:
            xml_extracted = True
    
    if not xml_extracted:
        return False
    
    # Ejecutar bd_extract_hologic.py
    try:
        script_path = "/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_hologic.py"
        result = subprocess.run(
            ['python3', script_path, patient_folder],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"✓ {mrn}")
            return True
        else:
            print(f"✗ {mrn}: {result.stderr[:50]}")
            return False
    except Exception as e:
        print(f"✗ {mrn}: {str(e)[:50]}")
        return False

def main():
    dicom_storage = "/home/ubuntu/DICOMReceiver/dicom_storage"
    
    patients = sorted([d for d in os.listdir(dicom_storage) 
                      if os.path.isdir(os.path.join(dicom_storage, d))])
    
    print(f"Reprocesando {len(patients)} pacientes con Z-scores corregidos...\n")
    
    success = 0
    for mrn in patients:
        patient_folder = os.path.join(dicom_storage, mrn)
        if process_patient_folder(patient_folder):
            success += 1
    
    print(f"\n✅ Completado: {success}/{len(patients)} pacientes procesados")

if __name__ == "__main__":
    main()
