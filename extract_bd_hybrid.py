#!/usr/bin/env python3
"""
Extractor híbrido BD Report:
- Datos demográficos y clínicos: XML embebido en DICOM
- FRAX Major value: OCR de imagen JPEG (pixel extraction)
- Guardado automático en PostgreSQL (reports.bd)
"""

import subprocess
import re
from pathlib import Path
import pydicom
import os
import psycopg2
from datetime import datetime
import uuid

def find_femoral_dcm_file(patient_id):
    """Encuentra archivo DICOM Femoral usando tag BodyPartExamined"""
    dicom_base = Path("/home/ubuntu/DICOMReceiver/dicom_storage")
    patient_path = dicom_base / patient_id
    
    if not patient_path.exists():
        return None, None
    
    study_dirs = list(patient_path.iterdir())
    if not study_dirs:
        return None, None
    
    study_path = study_dirs[0]
    
    for dcm_file in study_path.iterdir():
        if dcm_file.is_file():
            try:
                ds = pydicom.dcmread(dcm_file, stop_before_pixels=True, force=True)
                if hasattr(ds, 'BodyPartExamined') and ds.BodyPartExamined == 'HIP':
                    # Encontrar JPEG correspondiente
                    filename = dcm_file.name
                    parts = filename.split('_')
                    if len(parts) >= 3:
                        timestamp = f"{parts[1]}_{parts[2]}"
                        
                        bd_pixel_path = Path("/home/ubuntu/DICOMReceiver/pixel_extraction/BD") / patient_id
                        if bd_pixel_path.exists():
                            for jpeg in bd_pixel_path.glob(f"BD_{timestamp}*.jpg"):
                                return dcm_file, jpeg
            except:
                pass
    
    return None, None

def extract_xml_from_dicom(dcm_file):
    """Extrae XML embebido del DICOM"""
    try:
        ds = pydicom.dcmread(dcm_file, force=True)
        if (0x0019, 0x1000) in ds:
            xml_data = ds[0x0019, 0x1000].value
            if isinstance(xml_data, bytes):
                return xml_data.decode('utf-8', errors='ignore')
            return str(xml_data)
    except:
        pass
    return None

def extract_from_xml(xml_text):
    """Extrae datos del XML embebido"""
    data = {
        # Demográficos
        'patient_name': None,
        'patient_id': None,
        'age': None,
        'sex': None,
        'height': None,
        'weight': None,
        'dob': None,
        'physician': None,
        
        # Escaneo
        'scan_date': None,
        'scan_mode': None,
        'protocol': None,
        'institution': None,
        
        # Clínicos
        'femoral_bmd': None,
        'femoral_tscore': None,
        'femoral_zscore': None,
        'lumbar_bmd': None,
        'lumbar_tscore': None,
        'lumbar_zscore': None,
        'hip_fracture_risk': None,
        'who_classification': None,
    }
    
    # Extraer demográficos
    patterns = {
        'patient_name': r'PatientName\s*=\s*"([^"]+)"',
        'patient_id': r'PatientID\s*=\s*"([^"]+)"',
        'age': r'Age\s*=\s*"([^"]+)"',
        'sex': r'PatientSex\s*=\s*"([^"]+)"',
        'height': r'Height\s*=\s*"([^"]+)"',
        'weight': r'Weight\s*=\s*"([^"]+)"',
        'dob': r'DOB\s*=\s*"([^"]+)"',
        'physician': r'ReferringPhysician\s*=\s*"([^"]+)"',
        'scan_date': r'Scan\s*=\s*"([^"]+)"',
        'scan_mode': r'ScanMode\s*=\s*"([^"]+)"',
        'protocol': r'AnalProtocol\s*=\s*"([^"]+)"',
        'institution': r'Institution\s*=\s*"([^"]+)"',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, xml_text, re.IGNORECASE)
        if match:
            data[key] = match.group(1).strip()
    
    # Extraer valores clínicos de ResultsTable
    # ResultsTable1[fila][columna] = valor
    # Fila 1: Neck (Femoral), Fila 2: Total (Lumbar)
    # Columna 3: BMD, Columna 4: T-score, Columna 6: Z-score
    
    # Buscar patrones tipo: ResultsTable1[ 1][ 3] = "0.691";
    result_patterns = [
        (r'ResultsTable1\[\s*1\]\[\s*3\]\s*=\s*"([^"]+)"', 'femoral_bmd'),
        (r'ResultsTable1\[\s*1\]\[\s*4\]\s*=\s*"([^"]+)"', 'femoral_tscore'),
        (r'ResultsTable1\[\s*1\]\[\s*6\]\s*=\s*"([^"]+)"', 'femoral_zscore'),
        (r'ResultsTable1\[\s*2\]\[\s*3\]\s*=\s*"([^"]+)"', 'lumbar_bmd'),
        (r'ResultsTable1\[\s*2\]\[\s*4\]\s*=\s*"([^"]+)"', 'lumbar_tscore'),
        (r'ResultsTable1\[\s*2\]\[\s*6\]\s*=\s*"([^"]+)"', 'lumbar_zscore'),
        (r'ResultsTable2\[\s*2\]\[\s*2\]\s*=\s*"([^"]+)"', 'hip_fracture_risk'),
    ]
    
    for pattern, key in result_patterns:
        match = re.search(pattern, xml_text)
        if match:
            val = match.group(1).strip()
            # Limpiar caracteres HTML
            val = re.sub(r'<[^>]+>', '', val)
            data[key] = val
    
    # WHO Classification
    match = re.search(r'WHO Classification:\s*([^"<;]+)', xml_text)
    if match:
        data['who_classification'] = match.group(1).strip()
    
    return data

def extract_major_frax_from_ocr(image_path):
    """Extrae SOLO el valor Major FRAX del OCR de imagen"""
    result = subprocess.run(['/usr/bin/tesseract', str(image_path), 'stdout'], 
                           capture_output=True, text=True)
    text = result.stdout
    
    # Buscar patrón: Major Osteoporotic Fracture 29
    match = re.search(r'Major\s+Osteoporotic\s+Fracture\s+([\d.]+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None

def generate_report(data):
    """Genera reporte médico con datos híbridos"""
    
    # Normalizar Z-score si necesario
    lumbar_zscore = data.get('lumbar_zscore', '')
    if lumbar_zscore and not lumbar_zscore.startswith('-'):
        lumbar_zscore = '-' + lumbar_zscore
    
    femoral_zscore = data.get('femoral_zscore', '')
    
    report = f"""EXAM: BONE DENSITOMETRY

History: Evaluate for osteoporosis. 
Technique: Bone density study was performed to evaluate the lumbar spine and the left hip.
Comparison: [None available].

FINDINGS:

LUMBAR SPINE: 
  The bone mineral density in the lumbar spine (L1-L4) is {data.get('lumbar_bmd', '')} g/cm² 
  with a T-score of {data.get('lumbar_tscore', '')} 
  and a Z-score of {lumbar_zscore}.

LEFT HIP (FEMORAL NECK):
  The bone mineral density in the left femoral neck is {data.get('femoral_bmd', '')} g/cm² 
  with a T-score of {data.get('femoral_tscore', '')} 
  and a Z-score of {femoral_zscore}.

10-YEAR FRACTURE PROBABILITY (FRAX):
  Major osteoporotic fracture: {data.get('major_fracture_risk', '')}%
  Hip fracture: {data.get('hip_fracture_risk', '')}

WHO CLASSIFICATION: {data.get('who_classification', 'Unknown')}

IMPRESSION:
According to the World Health Organization standards, the patient is classified as {data.get('who_classification', 'Unknown').lower()}.
Follow-up bone mineral density exam is recommended in 24 months.
"""
    
    return report

def insert_into_database(data, report_text):
    """Inserta datos extraídos en PostgreSQL reports.bd"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            user="facundo",
            password="qii123",
            database="qii"
        )
        
        cursor = conn.cursor()
        
        # Generar GUID único
        guid = str(uuid.uuid4())
        mrn = data.get('patient_id', '')
        acc = data.get('scan_date', '').split('-')[1] if data.get('scan_date') else ''
        
        # Función para limpiar y convertir valores
        def to_float(val):
            if not val:
                return None
            # Remover símbolos como % y espacios
            val_str = str(val).replace('%', '').strip()
            try:
                return float(val_str)
            except:
                return None
        
        # Convertir valores numéricos
        femoral_bmd = to_float(data.get('femoral_bmd'))
        femoral_tscore = to_float(data.get('femoral_tscore'))
        femoral_zscore = to_float(data.get('femoral_zscore'))
        lumbar_bmd = to_float(data.get('lumbar_bmd'))
        lumbar_tscore = to_float(data.get('lumbar_tscore'))
        lumbar_zscore = to_float(data.get('lumbar_zscore'))
        hip_fracture_risk = to_float(data.get('hip_fracture_risk'))
        major_fracture_risk = to_float(data.get('major_fracture_risk'))
        
        # INSERT (guid, mrn, acc ahora son VARCHAR, no ARRAY)
        cursor.execute("""
            INSERT INTO reports.bd (
                guid, mrn, acc, pat_name, bd_report,
                femoral_bmd, femoral_tscore, femoral_zscore,
                lumbar_bmd, lumbar_tscore, lumbar_zscore,
                "hip_fracture_risk│", "WHO_Classification",
                major_fracture_risk, receivedon, studydate
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s
            )
        """, (
            guid, mrn, acc, data.get('patient_name'), report_text,
            femoral_bmd, femoral_tscore, femoral_zscore,
            lumbar_bmd, lumbar_tscore, lumbar_zscore,
            hip_fracture_risk, data.get('who_classification'),
            major_fracture_risk, datetime.now(), datetime.now()
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"\n✅ Datos insertados en PostgreSQL")
        print(f"   └─ GUID: {guid}")
        print(f"   └─ MRN: {mrn}")
        print(f"   └─ Tabla: reports.bd")
        
        return True
        
    except psycopg2.Error as e:
        print(f"\n❌ Error en base de datos: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    # Check if specific patient_id provided as argument
    if len(sys.argv) > 1:
        # Process only the specified patient
        patient_dirs = [sys.argv[1]]
        print(f"Processing single patient: {patient_dirs[0]}\n")
    else:
        # Get all patient IDs
        bd_base = Path("/home/ubuntu/DICOMReceiver/pixel_extraction/BD")
        patient_dirs = sorted([d.name for d in bd_base.iterdir() if d.is_dir()])
        
        if not patient_dirs:
            print("No patient directories found")
            exit(1)
        
        print(f"Found {len(patient_dirs)} patient(s): {patient_dirs}\n")
    
    # Process each patient
    for patient_id in patient_dirs:
        print(f"Processing patient: {patient_id}")
        
        # Find DICOM and JPEG
        dcm_file, jpeg_file = find_femoral_dcm_file(patient_id)
        
        if not dcm_file:
            print(f"  ✗ No Femoral DICOM file found")
            continue
        
        print(f"  ✓ DICOM: {dcm_file.name}")
        print(f"  ✓ JPEG: {jpeg_file.name}")
        
        # Extract XML from DICOM
        xml_text = extract_xml_from_dicom(dcm_file)
        if not xml_text:
            print(f"  ✗ No XML found in DICOM")
            continue
        
        # Parse XML data
        data = extract_from_xml(xml_text)
        print(f"  ✓ Extracted from XML: {len([v for v in data.values() if v])} fields")
        
        # Extract Major FRAX from OCR
        major_frax = extract_major_frax_from_ocr(jpeg_file)
        if major_frax:
            data['major_fracture_risk'] = major_frax
            print(f"  ✓ Extracted from OCR: Major FRAX = {major_frax}%")
        else:
            print(f"  ⚠️ Could not extract Major FRAX from OCR")
        
        # Generate report
        print("\nEXTRACTED VALUES:")
        print("="*60)
        for key, val in data.items():
            if val:
                print(f"{key:30}: {val}")
        
        print("\n\nREPORT:")
        print("="*60)
        report = generate_report(data)
        print(report)
        
        # Save report to file
        output_file = Path("/home/ubuntu/DICOMReceiver/reports") / f"bd_report_{patient_id}.txt"
        output_file.write_text(report)
        print(f"✅ Report saved to: {output_file}")
        
        # Insert into PostgreSQL
        print("\n📊 Guardando en PostgreSQL...")
        if insert_into_database(data, report):
            print(f"✅ Datos guardados en reports.bd")
        else:
            print(f"⚠️ Error guardando en BD (pero reporte guardado localmente)")


