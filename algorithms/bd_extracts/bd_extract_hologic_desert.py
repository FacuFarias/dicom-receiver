#!/usr/bin/env python3
"""
Extractor BD Report para estudios DESERT (single-hip):
- Datos demográficos y clínicos: XML embebido en DICOM
- FRAX Major value: OCR de imagen JPEG (pixel extraction)
- Guardado automático en PostgreSQL (reports.bd)
- NO extrae valores FRAX "with prior fracture"
"""

import subprocess
import re
from pathlib import Path
import pydicom
import os
import psycopg2
from datetime import datetime
import uuid

# Variable global para preservar lumbar_vertebrae_range entre archivos del mismo paciente
_lumbar_vertebrae_cache = {}

def is_pediatric_patient(xml_text, age):
    """
    Determina si un paciente es pediátrico basado en edad.
    Retorna True si es pediátrico (menor de 18 años)
    """
    if not age:
        return False
    try:
        age_num = int(age)
        return age_num < 18
    except:
        return False

def find_dicom_files(patient_id):
    """
    Encuentra archivos DICOM (Femoral y Forearm) usando tags BodyPartExamined o ScanMode en XML.
    Retorna: (femoral_dcm, femoral_jpeg, forearm_dcm, forearm_jpeg, hip_side, all_left_hip_files)
    hip_side puede ser 'left' o 'right'
    all_left_hip_files: lista de todos los archivos left hip si hay más de uno (para caso especial de 2 imágenes left hip)
    """
    dicom_base = Path("/home/ubuntu/DICOMReceiver/dicom_storage")
    patient_path = dicom_base / patient_id
    
    if not patient_path.exists():
        return None, None, None, None, None, []
    
    study_dirs = list(patient_path.iterdir())
    if not study_dirs:
        return None, None, None, None, None, []
    
    femoral_candidates = []  # (dcm_file, jpeg_file, has_frax, has_femoral, hip_side)
    forearm_candidates = []  # (dcm_file, jpeg_file, is_left, is_right)
    
    # Buscar en todos los estudios
    for study_path in study_dirs:
        for dcm_file in study_path.iterdir():
            if dcm_file.is_file():
                try:
                    ds = pydicom.dcmread(dcm_file, stop_before_pixels=True, force=True)
                    
                    # Verificar BodyPartExamined
                    body_part = getattr(ds, 'BodyPartExamined', '').upper()
                    is_hip = body_part == 'HIP'
                    is_forearm = 'FOREARM' in body_part or 'ARM' in body_part
                    
                    has_frax = False
                    has_femoral = False
                    has_forearm_data = False
                    is_left = False
                    is_right = False
                    hip_side = None  # Para detectar left/right hip
                    
                    # Buscar en XML
                    if (0x0019, 0x1000) in ds:
                        try:
                            xml_data = ds[0x0019, 0x1000].value
                            if isinstance(xml_data, bytes):
                                xml_text = xml_data.decode('utf-8', errors='ignore')
                            else:
                                xml_text = str(xml_data)
                            
                            # Buscar ScanMode con "Hip" (SIEMPRE, no solo si no es hip)
                            scan_mode_match = re.search(r'ScanMode\s*=\s*"([^"]*[Hh]ip[^"]*)"', xml_text)
                            if scan_mode_match:
                                is_hip = True
                                scan_mode_val = scan_mode_match.group(1).upper()
                                # Detectar si es left o right hip
                                if 'LEFT' in scan_mode_val:
                                    hip_side = 'left'
                                elif 'RIGHT' in scan_mode_val:
                                    hip_side = 'right'
                            
                            # Si ya era hip por BodyPartExamined, verificar lateralidad
                            if is_hip and not hip_side:
                                # Buscar en ImageLaterality o ScanMode
                                laterality_match = re.search(r'ImageLaterality\s*=\s*"([^"]*)"', xml_text)
                                if laterality_match:
                                    lat_val = laterality_match.group(1).upper()
                                    if 'L' in lat_val or 'LEFT' in lat_val:
                                        hip_side = 'left'
                                    elif 'R' in lat_val or 'RIGHT' in lat_val:
                                        hip_side = 'right'
                                
                                # Buscar en ScanMode si aún no encontramos
                                if not hip_side:
                                    scan_mode_match = re.search(r'ScanMode\s*=\s*"([^"]*)"', xml_text)
                                    if scan_mode_match:
                                        scan_val = scan_mode_match.group(1).upper()
                                        if 'LEFT' in scan_val:
                                            hip_side = 'left'
                                        elif 'RIGHT' in scan_val:
                                            hip_side = 'right'
                            
                            # Default a left si no se pudo determinar
                            if is_hip and not hip_side:
                                hip_side = 'left'
                            
                            # Buscar ScanMode con "Forearm"
                            if not is_forearm:
                                forearm_match = re.search(r'ScanMode\s*=\s*"([^"]*[Ff]orearm[^"]*)"', xml_text)
                                if forearm_match:
                                    is_forearm = True
                                    scan_mode_val = forearm_match.group(1).upper()
                                    is_left = 'LEFT' in scan_mode_val
                                    is_right = 'RIGHT' in scan_mode_val
                            
                            # Verificar si tiene FRAX
                            has_frax = bool(re.search(r'ResultsTable2\[\s*1\]\[\s*2\]\s*=', xml_text))
                            
                            # Verificar si tiene datos femoral (ResultsTable1 fila 1) CON VALOR
                            femoral_bmd_match = re.search(r'ResultsTable1\[\s*1\]\[\s*3\]\s*=\s*"([^"]*)"', xml_text)
                            if femoral_bmd_match:
                                val = re.sub(r'<[^>]+>', '', femoral_bmd_match.group(1).strip())
                                has_femoral = len(val) > 0  # Solo True si tiene valor no vacío
                            else:
                                has_femoral = False
                            
                            # Verificar si tiene datos forearm (ResultsTable1 fila 3 o 4)
                            has_forearm_data = bool(re.search(r'ResultsTable1\[\s*[34]\]\[\s*3\]\s*=', xml_text))
                            
                        except:
                            pass
                    
                    # Encontrar JPEG correspondiente
                    jpeg_file = None
                    filename = dcm_file.name
                    parts = filename.split('_')
                    if len(parts) >= 3:
                        timestamp = f"{parts[1]}_{parts[2]}"
                        
                        bd_pixel_path = Path("/home/ubuntu/DICOMReceiver/pixel_extraction/BD") / patient_id
                        if bd_pixel_path.exists():
                            for jpeg in bd_pixel_path.glob(f"BD_{timestamp}*.jpg"):
                                jpeg_file = jpeg
                                break
                    
                    # Clasificar como Hip/Femoral o Forearm
                    if is_hip or has_frax or has_femoral:
                        if jpeg_file:
                            femoral_candidates.append((dcm_file, jpeg_file, has_frax, has_femoral, hip_side))
                    
                    if is_forearm or has_forearm_data:
                        if jpeg_file:
                            forearm_candidates.append((dcm_file, jpeg_file, is_left, is_right))
                    
                except:
                    pass
    
    # Seleccionar mejor femoral
    femoral_dcm, femoral_jpeg, hip_side = None, None, None
    if femoral_candidates:
        # Priorizar archivos con datos Y con hip_side definido
        femoral_candidates.sort(key=lambda x: (
            x[3],  # has_femoral (prioritario)
            x[4] is not None,  # tiene hip_side
            x[2] and x[3],  # has_frax and has_femoral
            x[2]  # has_frax
        ), reverse=True)
        femoral_dcm, femoral_jpeg, has_frax, has_femoral, hip_side = femoral_candidates[0]
        
        # Si el archivo seleccionado NO tiene hip_side, buscar en otros candidatos
        if not hip_side:
            for dcm, jpg, frax, femoral, side in femoral_candidates:
                if side:  # Encontrar archivo con hip_side
                    hip_side = side  # Usar el hip_side de ese archivo
                    break
        
        # Si el archivo seleccionado tiene hip_side pero no tiene datos femoral,
        # buscar un archivo con datos y usar su información combinando con el hip_side
        if hip_side and not has_femoral:
            for dcm, jpg, frax, femoral, side in femoral_candidates:
                if femoral:  # Encontrar archivo con datos
                    femoral_dcm = dcm
                    femoral_jpeg = jpg
                    # Mantener el hip_side del primero
                    break
    
    # Seleccionar forearm (priorizar left sobre right si hay ambos)
    forearm_dcm, forearm_jpeg = None, None
    if forearm_candidates:
        # Priorizar left, luego right
        forearm_candidates.sort(key=lambda x: (x[2], x[3]), reverse=True)
        forearm_dcm, forearm_jpeg = forearm_candidates[0][0], forearm_candidates[0][1]
    
    # Obtener TODOS los archivos de left hip (para caso especial de 2 imágenes)
    all_left_hip_files = []
    if hip_side == 'left':
        all_left_hip_files = [dcm for dcm, jpg, frax, femoral, side in femoral_candidates if side == 'left']
    
    return femoral_dcm, femoral_jpeg, forearm_dcm, forearm_jpeg, hip_side, all_left_hip_files

def extract_and_save_xml(dcm_file, patient_id):
    """
    Extrae el XML embebido del DICOM y lo guarda en archivo.
    Estructura: xml_extraction/BD/{patient_id}/
    
    Returns:
        tuple: (xml_text, accession_number, xml_file_path)
    """
    try:
        ds = pydicom.dcmread(dcm_file, force=True)
        
        # Extraer AccessionNumber del tag estándar DICOM
        accession_number = getattr(ds, 'AccessionNumber', None)
        
        xml_text = None
        if (0x0019, 0x1000) in ds:
            xml_data = ds[0x0019, 0x1000].value
            if isinstance(xml_data, bytes):
                xml_text = xml_data.decode('utf-8', errors='ignore')
            else:
                xml_text = str(xml_data)
            
            # Guardar XML en archivo
            if xml_text:
                xml_output_dir = Path("/home/ubuntu/DICOMReceiver/xml_extraction/BD") / str(patient_id)
                xml_output_dir.mkdir(parents=True, exist_ok=True)
                
                # Generar nombre de archivo
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                sop_instance_uid = getattr(ds, 'SOPInstanceUID', 'unknown')
                output_filename = f"BD_{timestamp}_{sop_instance_uid}.xml"
                xml_file_path = xml_output_dir / output_filename
                
                # Guardar XML
                with open(xml_file_path, 'w', encoding='utf-8') as f:
                    f.write(xml_text)
                
                print(f"  ✓ XML saved: {xml_file_path.name}")
                return xml_text, accession_number, xml_file_path
        
        return xml_text, accession_number, None
    except Exception as e:
        print(f"  ⚠️  Error extracting/saving XML: {e}")
        pass
    return None, None, None

def extract_xml_from_dicom(dcm_file):
    """Extrae XML embebido del DICOM y también AccessionNumber del tag estándar"""
    try:
        ds = pydicom.dcmread(dcm_file, force=True)
        
        # Extraer AccessionNumber del tag estándar DICOM
        accession_number = getattr(ds, 'AccessionNumber', None)
        
        xml_text = None
        if (0x0019, 0x1000) in ds:
            xml_data = ds[0x0019, 0x1000].value
            if isinstance(xml_data, bytes):
                xml_text = xml_data.decode('utf-8', errors='ignore')
            else:
                xml_text = str(xml_data)
        
        return xml_text, accession_number
    except:
        pass
    return None, None

def extract_from_xml(xml_text):
    """
    Extrae datos del XML embebido.
    
    Args:
        xml_text: XML principal del DICOM
    """
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
        'hip_side': None,  # left o right
        
        # Clínicos Femoral/Lumbar
        'femoral_bmd': None,
        'femoral_tscore': None,
        'femoral_zscore': None,
        'lumbar_bmd': None,
        'lumbar_tscore': None,
        'lumbar_zscore': None,
        'lumbar_vertebrae_range': None,  # Ej: "L1-L4", "L2-L4", "L1-L3"
        'major_fracture_risk': None,
        'hip_fracture_risk': None,
        'who_classification': None,
        
        # Forearm
        'forearm_bmd': None,
        'forearm_tscore': None,
        'forearm_zscore': None,
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
    
    # ═════════════════════════════════════════════════════════════════════════════
    # DETECCIÓN DE FORMATO: MEMORIAL vs DESERT
    # ═════════════════════════════════════════════════════════════════════════════
    # Memorial: Envía AMBOS hips en un solo archivo con:
    #   - ScanMode = "a Right Hip" y ScanMode2 = "a Left Hip"
    #   - ResultsTable1 con filas "Left" y "Right"
    # Desert: Envía CADA hip en archivos separados con:
    #   - ScanMode = "a Left Hip" (O "a Right Hip")
    #   - ResultsTable1 con fila "Neck"
    # ═════════════════════════════════════════════════════════════════════════════
    
    # DESERT: No procesar formato Memorial dual-hip
    # Este script es específico para Desert (single-hip)
    is_memorial_format = bool(re.search(r'ScanMode2\s*=\s*"([^"]+)"', xml_text))
    
    if is_memorial_format:
        print("    📋 Formato MEMORIAL detectado (dual-hip en un archivo)")
        
        # MEMORIAL: Extraer AMBOS hips (Left y Right) del mismo archivo
        # IMPORTANTE: Hay 2 secciones de LEFT/RIGHT (una para Neck, otra para Total)
        # Solo queremos los valores de Neck (primera aparición)
        for row in range(15):
            region_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*0\]\s*=\s*"([^"]+)"', xml_text)
            if region_match:
                region_name = region_match.group(1).strip().upper()
                
                # Buscar filas "LEFT" y "RIGHT" (en Memorial, los datos de Neck están ahí)
                if region_name in ['LEFT', 'RIGHT']:
                    hip_side = region_name.lower()
                    
                    # Solo procesar si este lado NO ha sido extraído aún
                    # Esto asegura que tomamos Neck (rows 2-3) y NO Total (rows 7-8)
                    if not data.get(f'{hip_side}_hip_bmd'):
                        # Extraer BMD, T-score, Z-score de esta fila
                        bmd_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*3\]\s*=\s*"([^"]+)"', xml_text)
                        tscore_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*4\]\s*=\s*"([^"]+)"', xml_text)
                        zscore_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*6\]\s*=\s*"([^"]+)"', xml_text)
                        
                        if bmd_match:
                            data[f'{hip_side}_hip_bmd'] = re.sub(r'<[^>]+>', '', bmd_match.group(1).strip())
                            print(f"    ✓ {hip_side.capitalize()} Hip BMD: {data[f'{hip_side}_hip_bmd']}")
                        if tscore_match:
                            data[f'{hip_side}_hip_tscore'] = re.sub(r'<[^>]+>', '', tscore_match.group(1).strip())
                            print(f"    ✓ {hip_side.capitalize()} Hip T-score: {data[f'{hip_side}_hip_tscore']}")
                        if zscore_match:
                            data[f'{hip_side}_hip_zscore'] = re.sub(r'<[^>]+>', '', zscore_match.group(1).strip())
                        
                        # Para Memorial, marcar que tenemos el lado correspondiente
                        if not data.get('hip_side'):
                            data['hip_side'] = hip_side
        
        # Para Memorial, marcar que los valores de FRAX vienen del archivo dual-hip autorizado
        # Esto permite dar prioridad a estos valores en la combinación de datos
        data['_is_memorial_frax'] = True
        
    else:
        print("    📋 Formato DESERT detectado (single-hip por archivo)")
        
        # DESERT: Extraer UN SOLO hip basado en "Neck" y ScanMode
        for row in range(10):
            region_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*0\]\s*=\s*"([^"]+)"', xml_text)
            if region_match:
                region_name = region_match.group(1).strip().upper()
                if 'NECK' in region_name and 'FEMORAL' not in region_name:  # Es "Neck" solo
                    # Extraer BMD, T-score, Z-score de esta fila
                    bmd_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*3\]\s*=\s*"([^"]+)"', xml_text)
                    tscore_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*4\]\s*=\s*"([^"]+)"', xml_text)
                    zscore_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*6\]\s*=\s*"([^"]+)"', xml_text)
                    
                    # Determinar lateralidad del hip basado en ScanMode
                    hip_side = 'left'  # Por defecto
                    scan_mode_hip = re.search(r'ScanMode\s*=\s*"([^"]+)"', xml_text)
                    if scan_mode_hip:
                        scan_mode_val = scan_mode_hip.group(1).upper()
                        if 'RIGHT' in scan_mode_val:
                            hip_side = 'right'
                        elif 'LEFT' in scan_mode_val:
                            hip_side = 'left'
                    
                    # Guardar en la columna correspondiente (left_hip_* o right_hip_*)
                    if bmd_match:
                        data[f'{hip_side}_hip_bmd'] = re.sub(r'<[^>]+>', '', bmd_match.group(1).strip())
                    if tscore_match:
                        data[f'{hip_side}_hip_tscore'] = re.sub(r'<[^>]+>', '', tscore_match.group(1).strip())
                    if zscore_match:
                        data[f'{hip_side}_hip_zscore'] = re.sub(r'<[^>]+>', '', zscore_match.group(1).strip())
                    data['hip_side'] = hip_side
                    
                    # Extraer datos de comparación histórica para HIP de ResultsTable2 si existen
                    # NUEVA REGLA: Para datos históricos de Neck, usar SIEMPRE xml_text (que puede ser ReportType=9)
                    # NO usar second_left/right_hip_xml (ReportType=1) porque no tiene fila de Neck separada
                    xml_to_use_for_history = xml_text
                    
                    # Buscar la fila que corresponde a "Neck" en ResultsTable2
                    history_row = None
                    has_region_column = False
                    
                    # Primero verificar si ResultsTable2 tiene columna de región (columna 0)
                    first_region_match = re.search(r'ResultsTable2\[\s*1\]\[\s*0\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                    if first_region_match and first_region_match.group(1).strip() and '/' not in first_region_match.group(1):
                        has_region_column = True
                    
                    if has_region_column:
                        # Buscar la fila correspondiente a "Neck" o "Total"
                        for hist_row in range(1, 20):
                            region_name_match = re.search(rf'ResultsTable2\[\s*{hist_row}\]\[\s*0\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                            if region_name_match:
                                hist_region_name = region_name_match.group(1).strip().upper()
                                if hist_region_name == 'NECK':
                                    history_row = hist_row
                                    break
                                elif hist_region_name == 'TOTAL' and history_row is None:
                                    # Guardar Total como fallback si Neck no está disponible
                                    history_row = hist_row
                        
                        # Si encontramos Total pero no Neck, verificar si Total tiene datos válidos
                        if history_row is not None:
                            test_change = re.search(rf'ResultsTable2\[\s*{history_row}\]\[\s*5\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                            if not test_change or not test_change.group(1).strip() or test_change.group(1).strip() == ' ':
                                # No hay datos históricos válidos en esta fila
                                history_row = None
                    else:
                        # Formato simple sin columna de región - usar directamente fila 1
                        history_row = 1
                    
                    # Si no se encontró ninguna fila válida, usar 1 por defecto
                    if history_row is None:
                        history_row = 1
                    
                    # Extraer cambio vs Previous
                    # Intentar columna 6 primero (formato con región), luego columna 5 (formato simple)
                    change_match = re.search(rf'ResultsTable2\[\s*{history_row}\]\[\s*6\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                    if not change_match or not change_match.group(1).strip() or change_match.group(1).strip() == ' ':
                        change_match = re.search(rf'ResultsTable2\[\s*{history_row}\]\[\s*5\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                    
                    # Extraer fecha previa - priorizar columna 1 (en formato simple) sobre columna 0
                    prev_date_match = re.search(rf'ResultsTable2\[\s*{history_row + 1}\]\[\s*1\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                    # Validar que sea una fecha (contiene /)
                    if not prev_date_match or not prev_date_match.group(1).strip() or '/' not in prev_date_match.group(1):
                        prev_date_match = re.search(rf'ResultsTable2\[\s*{history_row + 1}\]\[\s*0\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                    
                    # Extraer BMD previo - puede estar en columna 2 o 3
                    prev_bmd_match = re.search(rf'ResultsTable2\[\s*{history_row + 1}\]\[\s*2\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                    if not prev_bmd_match or not prev_bmd_match.group(1).strip():
                        prev_bmd_match = re.search(rf'ResultsTable2\[\s*{history_row + 1}\]\[\s*3\]\s*=\s*"([^"]+)"', xml_to_use_for_history)
                    
                    if change_match and prev_date_match:
                        change_val = change_match.group(1).strip()
                        if change_val and change_val != ' ' and '%' in change_val:
                            data[f'{hip_side}_hip_change_percent'] = change_val
                            data[f'{hip_side}_hip_prev_date'] = prev_date_match.group(1).strip()
                            if prev_bmd_match:
                                data[f'{hip_side}_hip_prev_bmd'] = prev_bmd_match.group(1).strip()
                    
                    break
    
    # Buscar LUMBAR SPINE (buscar fila con "Total" que NO sea de HIP)
    for row in range(10):
        region_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*0\]\s*=\s*"([^"]+)"', xml_text)
        if region_match:
            region_name = region_match.group(1).strip().upper()
            if region_name == 'TOTAL':
                # Verificar que es lumbar spine verificando el ScanMode
                scan_mode = re.search(r'ScanMode\s*=\s*"([^"]+)"', xml_text)
                if scan_mode and 'SPINE' in scan_mode.group(1).upper():
                    # Es Total de Lumbar Spine
                    bmd_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*3\]\s*=\s*"([^"]+)"', xml_text)
                    tscore_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*4\]\s*=\s*"([^"]+)"', xml_text)
                    zscore_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*6\]\s*=\s*"([^"]+)"', xml_text)
                    
                    if bmd_match:
                        data['lumbar_bmd'] = re.sub(r'<[^>]+>', '', bmd_match.group(1).strip())
                    if tscore_match:
                        data['lumbar_tscore'] = re.sub(r'<[^>]+>', '', tscore_match.group(1).strip())
                    if zscore_match:
                        data['lumbar_zscore'] = re.sub(r'<[^>]+>', '', zscore_match.group(1).strip())
                    
                    # Detectar qué vértebras están incluidas (L1, L2, L3, L4)
                    vertebrae = []
                    for vrow in range(1, row):  # Buscar filas antes de Total
                        vert_match = re.search(rf'ResultsTable1\[\s*{vrow}\]\[\s*0\]\s*=\s*"([^"]+)"', xml_text)
                        if vert_match:
                            vert_name = vert_match.group(1).strip().upper()
                            if vert_name in ['L1', 'L2', 'L3', 'L4']:
                                vertebrae.append(vert_name)
                    
                    # Generar rango (ej: "L1-L4", "L2-L4", "L1-L3")
                    if len(vertebrae) >= 2:
                        data['lumbar_vertebrae_range'] = f"{vertebrae[0]}-{vertebrae[-1]}"
                    elif len(vertebrae) == 1:
                        data['lumbar_vertebrae_range'] = vertebrae[0]
                    else:
                        data['lumbar_vertebrae_range'] = "L1-L4"  # Default
                    
                    # Guardar en caché global para preservar entre archivos
                    patient_id_key = data.get('patient_id')
                    if patient_id_key:
                        _lumbar_vertebrae_cache[patient_id_key] = data['lumbar_vertebrae_range']
                    
                    # Extraer datos de comparación histórica de ResultsTable2 si existen
                    # Fila [1] = estudio actual, Columna [5] = BMD Change vs Previous (no vs Baseline)
                    change_match = re.search(r'ResultsTable2\[\s*1\]\[\s*5\]\s*=\s*"([^"]+)"', xml_text)
                    prev_date_match = re.search(r'ResultsTable2\[\s*2\]\[\s*0\]\s*=\s*"([^"]+)"', xml_text)
                    prev_bmd_match = re.search(r'ResultsTable2\[\s*2\]\[\s*2\]\s*=\s*"([^"]+)"', xml_text)
                    
                    if change_match and prev_date_match:
                        change_val = change_match.group(1).strip()
                        if change_val and change_val != ' ' and '%' in change_val:
                            data['lumbar_change_percent'] = change_val
                            data['lumbar_prev_date'] = prev_date_match.group(1).strip()
                            if prev_bmd_match:
                                data['lumbar_prev_bmd'] = prev_bmd_match.group(1).strip()
                    
                    break
    
    # Buscar FOREARM (regiones como "UD", "MID", "TOTAL", "1/3" en estudios de Forearm)
    scan_mode = data.get('scan_mode', '')
    if scan_mode and 'FOREARM' in scan_mode.upper():
        # Determinar lateralidad del forearm basado en ScanMode
        forearm_side = 'left'  # Por defecto
        scan_mode_upper = scan_mode.upper()
        if 'RIGHT' in scan_mode_upper or 'R.' in scan_mode or ' R ' in scan_mode:
            forearm_side = 'right'
        elif 'LEFT' in scan_mode_upper or 'L.' in scan_mode or ' L ' in scan_mode:
            forearm_side = 'left'
        
        # Buscar TODAS las regiones y seleccionar la que tenga el T-score más alto (menos negativo)
        forearm_regions = []
        for row in range(10):
            region_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*0\]\s*=\s*"([^"]+)"', xml_text)
            if region_match:
                region_name = region_match.group(1).strip().upper()
                # Buscar cualquier región de forearm (1/3, MID, UD, TOTAL)
                if region_name in ['1/3', 'MID', 'UD', 'TOTAL']:
                    bmd_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*3\]\s*=\s*"([^"]+)"', xml_text)
                    tscore_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*4\]\s*=\s*"([^"]+)"', xml_text)
                    zscore_match = re.search(rf'ResultsTable1\[\s*{row}\]\[\s*6\]\s*=\s*"([^"]+)"', xml_text)
                    
                    if bmd_match and tscore_match:
                        try:
                            tscore_val = float(re.sub(r'<[^>]+>', '', tscore_match.group(1).strip()))
                            bmd_val = re.sub(r'<[^>]+>', '', bmd_match.group(1).strip())
                            zscore_val = re.sub(r'<[^>]+>', '', zscore_match.group(1).strip()) if zscore_match else None
                            
                            forearm_regions.append({
                                'region': region_name,
                                'tscore': tscore_val,
                                'bmd': bmd_val,
                                'zscore': zscore_val
                            })
                        except:
                            pass
        
        # Seleccionar la región con el T-score más negativo (valor más bajo)
        if forearm_regions:
            best_region = min(forearm_regions, key=lambda x: x['tscore'])
            data[f'{forearm_side}_forearm_bmd'] = best_region['bmd']
            data[f'{forearm_side}_forearm_tscore'] = str(best_region['tscore'])
            if best_region['zscore']:
                data[f'{forearm_side}_forearm_zscore'] = best_region['zscore']
            
            # Extraer datos de comparación histórica de ResultsTable2 para forearm
            # ResultsTable2 para forearm tiene la misma estructura que lumbar spine
            # Fila [1] = estudio actual, Columna [5] = BMD Change vs Previous
            change_match = re.search(r'ResultsTable2\[\s*1\]\[\s*5\]\s*=\s*"([^"]+)"', xml_text)
            prev_date_match = re.search(r'ResultsTable2\[\s*2\]\[\s*0\]\s*=\s*"([^"]+)"', xml_text)
            # Validate that it's a date (contains /)
            if not prev_date_match or not prev_date_match.group(1).strip() or '/' not in prev_date_match.group(1):
                prev_date_match = re.search(r'ResultsTable2\[\s*2\]\[\s*1\]\s*=\s*"([^"]+)"', xml_text)
            prev_bmd_match = re.search(r'ResultsTable2\[\s*2\]\[\s*2\]\s*=\s*"([^"]+)"', xml_text)
            
            if change_match and prev_date_match:
                change_val = change_match.group(1).strip()
                if change_val and change_val != ' ' and '%' in change_val:
                    # Extract percentage only if value contains parentheses
                    if '(' in change_val and ')' in change_val:
                        pct_match = re.search(r'\(([^)]+)\)', change_val)
                        if pct_match:
                            change_val = pct_match.group(1)
                    
                    data[f'{forearm_side}_forearm_change_percent'] = change_val
                    data[f'{forearm_side}_forearm_prev_date'] = prev_date_match.group(1).strip()
                    if prev_bmd_match:
                        data[f'{forearm_side}_forearm_prev_bmd'] = prev_bmd_match.group(1).strip()
    
    # Extraer FRAX - SOLO si es estudio HIP (los estudios LSPINE no tienen FRAX real)
    # HOLOGIC usa diferentes estructuras de tabla según el tipo de reporte
    # Opción 1: ResultsTable2[1][2] y ResultsTable2[2][2] (formato antiguo)
    # Opción 2: ResultsTable2[1][1] y ResultsTable2[2][1] (formato alternativo)
    # Opción 3: ResultsTable3[1][1] y ResultsTable3[2][1] (formato con historial - PRIORITARIO)
    
    # Verificar si es estudio HIP buscando ScanMode
    is_hip_study = False
    scan_mode = data.get('scan_mode', '')
    if scan_mode and 'HIP' in scan_mode.upper():
        is_hip_study = True
    
    # Solo extraer FRAX si es estudio HIP
    if is_hip_study:
        # IMPORTANTE: Primero verificar si ResultsTable3 contiene FRAX
        # Si es así, ignorar ResultsTable2 (que contiene historial BMD)
        # PERO: si ResultsTable3 dice "not reported", NO extraer valores
        is_frax_table3 = False
        frax_not_available = False
        
        table3_label = re.search(r'ResultsTable3\[\s*1\]\[\s*0\]\s*=\s*"([^"]+)"', xml_text)
        if table3_label:
            label_text = table3_label.group(1).upper()
            # Si dice "not reported", marcar FRAX como no disponible
            if 'NOT REPORTED' in label_text or 'NOT AVAILABLE' in label_text:
                frax_not_available = True
            # Si contiene MAJOR y FRACTURE (pero no "not reported"), es FRAX válido
            elif 'MAJOR' in label_text and 'FRACTURE' in label_text:
                is_frax_table3 = True
        
        # Intentar extraer Major FRAX (sin prior fracture) SOLO si FRAX está disponible
        if not frax_not_available and is_frax_table3:
            # Usar ResultsTable3 (tiene prioridad cuando existe)
            major_match = re.search(r'ResultsTable3\[\s*1\]\[\s*1\]\s*=\s*"([^"]+)"', xml_text)
        elif not frax_not_available:
            # Usar ResultsTable2 - columna [1] es el valor actual, columna [2] es histórico
            # PERO SOLO si FRAX no está marcado como "not available"
            major_match = re.search(r'ResultsTable2\[\s*1\]\[\s*1\]\s*=\s*"([^"]+)"', xml_text)
            if not major_match:
                major_match = re.search(r'ResultsTable2\[\s*1\]\[\s*2\]\s*=\s*"([^"]+)"', xml_text)
        else:
            major_match = None
        
        if major_match:
            val = re.sub(r'<[^>]+>', '', major_match.group(1).strip())
            # Eliminar signo "<" al inicio (ej: "<0.1" -> "0.1")
            val = re.sub(r'^<\s*', '', val)
            # Validar que el valor sea FRAX (número < 50) y no edad o BMD
            try:
                num_val = float(val.replace('%', ''))
                # FRAX típicamente es < 50 (rara vez > 40)
                # Valores >= 50 probablemente son edad (50-100 años)
                if num_val < 50:
                    data['major_fracture_risk'] = val
            except:
                pass
        
        # Intentar extraer Hip FRAX (sin prior fracture) SOLO si FRAX está disponible
        if not frax_not_available and is_frax_table3:
            # Usar ResultsTable3 (tiene prioridad cuando existe)
            hip_match = re.search(r'ResultsTable3\[\s*2\]\[\s*1\]\s*=\s*"([^"]+)"', xml_text)
        elif not frax_not_available:
            # Usar ResultsTable2 - columna [1] es el valor actual, columna [2] es histórico
            # PERO SOLO si FRAX no está marcado como "not available"
            hip_match = re.search(r'ResultsTable2\[\s*2\]\[\s*1\]\s*=\s*"([^"]+)"', xml_text)
            if not hip_match:
                hip_match = re.search(r'ResultsTable2\[\s*2\]\[\s*2\]\s*=\s*"([^"]+)"', xml_text)
        else:
            hip_match = None
        
        if hip_match:
            val = re.sub(r'<[^>]+>', '', hip_match.group(1).strip())
            # Eliminar signo "<" al inicio (ej: "<0.1" -> "0.1")
            val = re.sub(r'^<\s*', '', val)
            # Validar que el valor sea FRAX (número < 50) y no edad o BMD
            try:
                num_val = float(val.replace('%', ''))
                # FRAX típicamente es < 50 (rara vez > 40)
                # Valores >= 50 probablemente son edad (50-100 años)
                if num_val < 50:
                    data['hip_fracture_risk'] = val
            except:
                pass
        
        # DESERT: NO extraer valores FRAX "with prior fracture"
        # La columna 2 en ResultsTable3 es un cálculo estándar del equipo, no específico del paciente
        # Solo Memorial dual-hip debe extraer estos valores
        if False:  # Deshabilitado para Desert
            # Major fracture WITH prior fracture
            major_prior_match = re.search(r'ResultsTable3\[\s*1\]\[\s*2\]\s*=\s*"([^"]+)"', xml_text)
            if major_prior_match:
                val = re.sub(r'<[^>]+>', '', major_prior_match.group(1).strip())
                # Eliminar signo "<" al inicio (ej: "<0.1" -> "0.1")
                val = re.sub(r'^<\s*', '', val)
                # Validar que sea un número válido (< 50) y diferente del without prior
                try:
                    num_val = float(val.replace('%', ''))
                    if num_val < 50 and val != data.get('major_fracture_risk', ''):
                        data['major_fracture_risk_prior'] = val
                except:
                    pass
            
            # Hip fracture WITH prior fracture
            hip_prior_match = re.search(r'ResultsTable3\[\s*2\]\[\s*2\]\s*=\s*"([^"]+)"', xml_text)
            if hip_prior_match:
                val = re.sub(r'<[^>]+>', '', hip_prior_match.group(1).strip())
                # Eliminar signo "<" al inicio (ej: "<0.1" -> "0.1")
                val = re.sub(r'^<\s*', '', val)
                # Validar que sea un número válido (< 50) y diferente del without prior
                try:
                    num_val = float(val.replace('%', ''))
                    if num_val < 50 and val != data.get('hip_fracture_risk', ''):
                        data['hip_fracture_risk_prior'] = val
                except:
                    pass
    
    # WHO Classification
    match = re.search(r'WHO Classification:\s*([^"<;]+)', xml_text)
    if match:
        data['who_classification'] = match.group(1).strip()
    
    return data

def classify_who_by_tscore(tscore):
    """
    Clasifica según WHO basado en T-score:
    - Normal: T-score >= -1.0
    - Osteopenia: -2.5 < T-score < -1.0
    - Osteoporosis: T-score <= -2.5
    """
    if not tscore:
        return None
    
    try:
        t_val = float(tscore)
        if t_val >= -1.0:
            return "Normal"
        elif t_val > -2.5:
            return "Osteopenia"
        else:
            return "Osteoporosis"
    except:
        return None

def generate_who_classification_detailed(data, hip_side):
    """
    Genera clasificación WHO detallada por región anatómica
    """
    classifications = []
    
    # Clasificar Lumbar Spine
    lumbar_tscore = data.get('lumbar_tscore')
    if lumbar_tscore:
        lumbar_class = classify_who_by_tscore(lumbar_tscore)
        if lumbar_class:
            classifications.append(f"  Lumbar spine: {lumbar_class}")
    
    # Clasificar Hip - revisar AMBAS caderas si están disponibles
    left_hip_tscore = data.get('left_hip_tscore')
    if left_hip_tscore:
        left_hip_class = classify_who_by_tscore(left_hip_tscore)
        if left_hip_class:
            classifications.append(f"  Left hip: {left_hip_class}")
    
    right_hip_tscore = data.get('right_hip_tscore')
    if right_hip_tscore:
        right_hip_class = classify_who_by_tscore(right_hip_tscore)
        if right_hip_class:
            classifications.append(f"  Right hip: {right_hip_class}")
    
    # Clasificar Forearm si existe
    left_forearm_tscore = data.get('left_forearm_tscore')
    if left_forearm_tscore:
        forearm_class = classify_who_by_tscore(left_forearm_tscore)
        if forearm_class:
            classifications.append(f"  Left forearm: {forearm_class}")
    
    right_forearm_tscore = data.get('right_forearm_tscore')
    if right_forearm_tscore:
        forearm_class = classify_who_by_tscore(right_forearm_tscore)
        if forearm_class:
            classifications.append(f"  Right forearm: {forearm_class}")
    
    if classifications:
        return "\n".join(classifications)
    else:
        # Fallback al valor XML si existe
        return f"  {data.get('who_classification', 'Unknown')}"

def format_regions_list(regions):
    """
    Formatea una lista de regiones con comas y 'and' apropiadamente.
    Ejemplos:
    - 1 elemento: "the lumbar spine"
    - 2 elementos: "the lumbar spine and both hips"
    - 3+ elementos: "the lumbar spine, both forearms, and both hips"
    """
    if not regions:
        return ""
    elif len(regions) == 1:
        return regions[0]
    elif len(regions) == 2:
        return f"{regions[0]} and {regions[1]}"
    else:
        # 3 o más elementos: usar comas y "and" antes del último
        return ", ".join(regions[:-1]) + f", and {regions[-1]}"

def generate_impression(data, hip_side):
    """
    Genera IMPRESSION detallada basada en clasificación WHO de cada región
    Agrupa regiones por clasificación (Osteoporosis, Osteopenia, Normal)
    """
    impressions = []
    has_osteoporosis = False
    
    # Evaluar todas las regiones y clasificarlas
    left_hip_tscore = data.get('left_hip_tscore')
    right_hip_tscore = data.get('right_hip_tscore')
    lumbar_tscore = data.get('lumbar_tscore')
    left_forearm_tscore = data.get('left_forearm_tscore')
    right_forearm_tscore = data.get('right_forearm_tscore')
    
    left_hip_class = classify_who_by_tscore(left_hip_tscore) if left_hip_tscore else None
    right_hip_class = classify_who_by_tscore(right_hip_tscore) if right_hip_tscore else None
    lumbar_class = classify_who_by_tscore(lumbar_tscore) if lumbar_tscore else None
    left_forearm_class = classify_who_by_tscore(left_forearm_tscore) if left_forearm_tscore else None
    right_forearm_class = classify_who_by_tscore(right_forearm_tscore) if right_forearm_tscore else None
    
    # Agrupar regiones por clasificación
    osteoporosis_regions = []
    osteopenia_regions = []
    normal_regions = []
    
    # ORDEN CORRECTO: 1. Lumbar Spine, 2. Forearms, 3. Hips
    
    # 1. Agregar lumbar spine primero
    if lumbar_class == "Osteoporosis":
        osteoporosis_regions.append("the lumbar spine")
        has_osteoporosis = True
    elif lumbar_class == "Osteopenia":
        osteopenia_regions.append("the lumbar spine")
    elif lumbar_class == "Normal":
        normal_regions.append("the lumbar spine")
    
    # 2. Agregar forearms segundo
    if left_forearm_class and right_forearm_class and left_forearm_class == right_forearm_class:
        # Ambos forearms con la misma clasificación
        if left_forearm_class == "Osteoporosis":
            osteoporosis_regions.append("both forearms")
            has_osteoporosis = True
        elif left_forearm_class == "Osteopenia":
            osteopenia_regions.append("both forearms")
        elif left_forearm_class == "Normal":
            normal_regions.append("both forearms")
    else:
        # Tratar individualmente
        if left_forearm_class == "Osteoporosis":
            osteoporosis_regions.append("the left forearm")
            has_osteoporosis = True
        elif left_forearm_class == "Osteopenia":
            osteopenia_regions.append("the left forearm")
        elif left_forearm_class == "Normal":
            normal_regions.append("the left forearm")
        
        if right_forearm_class == "Osteoporosis":
            osteoporosis_regions.append("the right forearm")
            has_osteoporosis = True
        elif right_forearm_class == "Osteopenia":
            osteopenia_regions.append("the right forearm")
        elif right_forearm_class == "Normal":
            normal_regions.append("the right forearm")
    
    # 3. Agregar hips al final
    if left_hip_class and right_hip_class and left_hip_class == right_hip_class:
        # Ambas caderas con la misma clasificación - agrupar como "both hips"
        if left_hip_class == "Osteoporosis":
            osteoporosis_regions.append("both hips")
            has_osteoporosis = True
        elif left_hip_class == "Osteopenia":
            osteopenia_regions.append("both hips")
        elif left_hip_class == "Normal":
            normal_regions.append("both hips")
    else:
        # Tratar individualmente
        if left_hip_class == "Osteoporosis":
            osteoporosis_regions.append("the left hip")
            has_osteoporosis = True
        elif left_hip_class == "Osteopenia":
            osteopenia_regions.append("the left hip")
        elif left_hip_class == "Normal":
            normal_regions.append("the left hip")
        
        if right_hip_class == "Osteoporosis":
            osteoporosis_regions.append("the right hip")
            has_osteoporosis = True
        elif right_hip_class == "Osteopenia":
            osteopenia_regions.append("the right hip")
        elif right_hip_class == "Normal":
            normal_regions.append("the right hip")
    
    # Generar oraciones agrupadas por clasificación
    is_first = True
    
    # OSTEOPOROSIS (prioridad)
    if osteoporosis_regions:
        regions_text = format_regions_list(osteoporosis_regions)
        
        if is_first:
            impressions.append(f"According to the World Health Organization's standards, bone mineral density in {regions_text} is osteoporotic. Highly increased risk of fracture. Treatment is advised.")
            is_first = False
        else:
            impressions.append(f"Bone mineral density in {regions_text} is osteoporotic. Highly increased risk of fracture. Treatment is advised.")
    
    # OSTEOPENIA
    if osteopenia_regions:
        regions_text = format_regions_list(osteopenia_regions)
        
        if is_first:
            impressions.append(f"According to the World Health Organization's standards, bone mineral density in {regions_text} is osteopenic. Moderately increased risk of fracture. Treatment is advised.")
            is_first = False
        else:
            impressions.append(f"Bone mineral density in {regions_text} is osteopenic. Moderately increased risk of fracture. Treatment is advised.")
    
    # NORMAL
    if normal_regions:
        regions_text = format_regions_list(normal_regions)
        
        if is_first:
            impressions.append(f"According to the World Health Organization's standards, bone mineral density in {regions_text} is within a normal range. Low risk of fracture.")
            is_first = False
        else:
            impressions.append(f"Bone mineral density in {regions_text} is within a normal range. Low risk of fracture.")
    
    # Conclusión general - 12 meses si hay osteoporosis, 24 si solo osteopenia o normal
    follow_up_months = 12 if has_osteoporosis else 24
    impressions.append(f"Follow-up bone mineral density exam is recommended in [{follow_up_months}] months.")
    
    return "\n".join(impressions)

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
    """Genera reporte médico con datos híbridos, soporta ambas caderas"""
    
    # Obtener z-score lumbar directamente de data
    lumbar_zscore = data.get('lumbar_zscore', '')
    
    # Revisar qué regiones están disponibles
    has_left_hip = bool(data.get('left_hip_bmd') or data.get('left_hip_tscore'))
    has_right_hip = bool(data.get('right_hip_bmd') or data.get('right_hip_tscore'))
    has_lumbar = bool(data.get('lumbar_bmd') or data.get('lumbar_tscore'))
    has_left_forearm = bool(data.get('left_forearm_bmd') or data.get('left_forearm_tscore'))
    has_right_forearm = bool(data.get('right_forearm_bmd') or data.get('right_forearm_tscore'))
    
    # Determinar texto de Technique section
    # Orden: Lumbar spine - Right forearm - Left forearm - Right hip - Left hip
    regions = []
    if has_lumbar:
        regions.append('the lumbar spine')
    if has_right_forearm and has_left_forearm:
        regions.append('both forearms')
    elif has_right_forearm:
        regions.append('the right forearm')
    elif has_left_forearm:
        regions.append('the left forearm')
    if has_right_hip and has_left_hip:
        regions.append('both hips')
    elif has_right_hip:
        regions.append('the right hip')
    elif has_left_hip:
        regions.append('the left hip')
    
    if len(regions) > 2:
        technique_text = ', '.join(regions[:-1]) + ', and ' + regions[-1]
    elif len(regions) > 1:
        technique_text = ' and '.join(regions)
    elif len(regions) == 1:
        technique_text = regions[0]
    else:
        technique_text = 'bone mineral density'
    
    # Mantener hip_side para compatibilidad con código antiguo (usará el primero disponible)
    hip_side = None
    if has_left_hip:
        hip_side = 'left'
    elif has_right_hip:
        hip_side = 'right'
    
    # FRAX - mostrar valores "without prior" y "with prior" cuando estén disponibles
    major_frax = data.get('major_fracture_risk')
    hip_frax = data.get('hip_fracture_risk')
    major_frax_prior = data.get('major_fracture_risk_prior')
    hip_frax_prior = data.get('hip_fracture_risk_prior')
    
    # Helper para formatear valores FRAX con %
    def format_frax(value):
        if not value:
            return 'Not available'
        value_str = str(value).strip()
        if '%' in value_str:
            return value_str
        return f"{value_str}%"
    
    if major_frax or hip_frax:
        # Verificar si hay valores "with prior fracture" disponibles
        has_prior_values = major_frax_prior or hip_frax_prior
        
        if has_prior_values:
            # Mostrar ambas columnas (without y with prior fracture)
            frax_section = f"""<strong>10-YEAR FRACTURE PROBABILITY (FRAX):</strong>
  Without prior fracture:
    Major osteoporotic fracture: {format_frax(major_frax)}
    Hip fracture: {format_frax(hip_frax)}
  With prior fracture:
    Major osteoporotic fracture: {format_frax(major_frax_prior)}
    Hip fracture: {format_frax(hip_frax_prior)}

"""
        else:
            # Solo mostrar valores sin "prior" (formato anterior)
            frax_section = f"""<strong>10-YEAR FRACTURE PROBABILITY (FRAX):</strong>
  Major osteoporotic fracture: {format_frax(major_frax)}
  Hip fracture: {format_frax(hip_frax)}

"""
    else:
        # No hay FRAX - no mostrar nada
        frax_section = ""
    
    # Preparar secciones FOREARM individuales
    right_forearm_section = ""
    left_forearm_section = ""
    
    right_forearm_bmd = data.get('right_forearm_bmd')
    left_forearm_bmd = data.get('left_forearm_bmd')
    
    if right_forearm_bmd or data.get('right_forearm_tscore'):
        right_forearm_tscore = data.get('right_forearm_tscore', '')
        right_forearm_zscore = data.get('right_forearm_zscore', '')
        
        # Construir texto de comparación para right forearm si hay datos históricos
        right_forearm_comparison = ""
        right_forearm_prev_date = data.get('right_forearm_prev_date')
        right_forearm_change = data.get('right_forearm_change_percent')
        if right_forearm_prev_date and right_forearm_change:
            year_match = re.match(r'\d{2}/\d{2}/(\d{4})', right_forearm_prev_date)
            if year_match:
                year = year_match.group(1)
                change_val = right_forearm_change.replace('-', '').replace('+', '').replace('#', '').replace('*', '')
                # Si el valor contiene paréntesis, extraer solo el porcentaje
                if '(' in change_val and ')' in change_val:
                    pct_match = re.search(r'\(([^)]+)\)', change_val)
                    if pct_match:
                        change_val = pct_match.group(1)
                # Convertir a float para comparar
                try:
                    change_float = float(change_val.replace('%', ''))
                    if abs(change_float) <= 3:
                        right_forearm_comparison = f" The bone mineral density remained stable since [{year}]."
                    else:
                        change_text = "decreased" if "-" in right_forearm_change else "increased"
                        right_forearm_comparison = f" The bone mineral density {change_text} by {change_val} since [{year}]."
                except ValueError:
                    # Si no se puede convertir, usar lógica antigua
                    change_text = "decreased" if "-" in right_forearm_change else "increased"
                    right_forearm_comparison = f" The bone mineral density {change_text} by {change_val} since [{year}]."
        
        zscore_text = f" and a Z-score of {right_forearm_zscore}" if right_forearm_zscore and str(right_forearm_zscore) != 'None' else ""
        right_forearm_section = f"<strong>RIGHT FOREARM:</strong> The bone mineral density in the right forearm is {right_forearm_bmd or ''} g/cm² with a T-score of {right_forearm_tscore}{zscore_text}.{right_forearm_comparison}\n\n"
    
    if left_forearm_bmd or data.get('left_forearm_tscore'):
        left_forearm_tscore = data.get('left_forearm_tscore', '')
        left_forearm_zscore = data.get('left_forearm_zscore', '')
        
        # Construir texto de comparación para left forearm si hay datos históricos
        left_forearm_comparison = ""
        left_forearm_prev_date = data.get('left_forearm_prev_date')
        left_forearm_change = data.get('left_forearm_change_percent')
        if left_forearm_prev_date and left_forearm_change:
            year_match = re.match(r'\d{2}/\d{2}/(\d{4})', left_forearm_prev_date)
            if year_match:
                year = year_match.group(1)
                change_val = left_forearm_change.replace('-', '').replace('+', '').replace('#', '').replace('*', '')
                # Si el valor contiene paréntesis, extraer solo el porcentaje
                if '(' in change_val and ')' in change_val:
                    pct_match = re.search(r'\(([^)]+)\)', change_val)
                    if pct_match:
                        change_val = pct_match.group(1)
                # Convertir a float para comparar
                try:
                    change_float = float(change_val.replace('%', ''))
                    if abs(change_float) <= 3:
                        left_forearm_comparison = f" The bone mineral density remained stable since [{year}]."
                    else:
                        change_text = "decreased" if "-" in left_forearm_change else "increased"
                        left_forearm_comparison = f" The bone mineral density {change_text} by {change_val} since [{year}]."
                except ValueError:
                    # Si no se puede convertir, usar lógica antigua
                    change_text = "decreased" if "-" in left_forearm_change else "increased"
                    left_forearm_comparison = f" The bone mineral density {change_text} by {change_val} since [{year}]."
        
        zscore_text = f" and a Z-score of {left_forearm_zscore}" if left_forearm_zscore and str(left_forearm_zscore) != 'None' else ""
        left_forearm_section = f"<strong>LEFT FOREARM:</strong> The bone mineral density in the left forearm is {left_forearm_bmd or ''} g/cm² with a T-score of {left_forearm_tscore}{zscore_text}.{left_forearm_comparison}\n\n"
    
    
    # Construir secciones de HIP individuales
    right_hip_section = ""
    left_hip_section = ""
    
    # RIGHT HIP
    if has_right_hip:
        right_hip_bmd = data.get('right_hip_bmd', '')
        right_hip_tscore = data.get('right_hip_tscore', '')
        right_hip_zscore = data.get('right_hip_zscore', '')
        
        # Construir texto de comparación para right hip si hay datos históricos
        right_hip_comparison = ""
        right_hip_prev_date = data.get('right_hip_prev_date')
        right_hip_change = data.get('right_hip_change_percent')
        if right_hip_prev_date and right_hip_change:
            year_match = re.match(r'\d{2}/\d{2}/(\d{4})', right_hip_prev_date)
            if year_match:
                year = year_match.group(1)
                change_val = right_hip_change.replace('-', '').replace('+', '').replace('#', '').replace('*', '')
                # Si el valor contiene paréntesis, extraer solo el porcentaje
                if '(' in change_val and ')' in change_val:
                    pct_match = re.search(r'\(([^)]+)\)', change_val)
                    if pct_match:
                        change_val = pct_match.group(1)
                # Convertir a float para comparar
                try:
                    change_float = float(change_val.replace('%', ''))
                    if abs(change_float) <= 3:
                        right_hip_comparison = f" The bone mineral density in the right femoral neck remained stable since {year}."
                    else:
                        change_text = "decreased" if "-" in right_hip_change else "increased"
                        right_hip_comparison = f" The bone mineral density [{change_text}] by {change_val} since {year}."
                except ValueError:
                    # Si no se puede convertir, usar lógica antigua
                    change_text = "decreased" if "-" in right_hip_change else "increased"
                    right_hip_comparison = f" The bone mineral density [{change_text}] by {change_val} since {year}."
        
        zscore_text = f" and a Z-score of {right_hip_zscore}" if right_hip_zscore and str(right_hip_zscore) != 'None' else ""
        right_hip_section = f"<strong>RIGHT HIP (FEMORAL NECK):</strong> The bone mineral density in the right femoral neck is {right_hip_bmd} g/cm² with a T-score of {right_hip_tscore}{zscore_text}.{right_hip_comparison}\n\n"
    
    # LEFT HIP
    if has_left_hip:
        left_hip_bmd = data.get('left_hip_bmd', '')
        left_hip_tscore = data.get('left_hip_tscore', '')
        left_hip_zscore = data.get('left_hip_zscore', '')
        
        # Construir texto de comparación para left hip si hay datos históricos
        left_hip_comparison = ""
        left_hip_prev_date = data.get('left_hip_prev_date')
        left_hip_change = data.get('left_hip_change_percent')
        if left_hip_prev_date and left_hip_change:
            year_match = re.match(r'\d{2}/\d{2}/(\d{4})', left_hip_prev_date)
            if year_match:
                year = year_match.group(1)
                change_val = left_hip_change.replace('-', '').replace('+', '').replace('#', '').replace('*', '')
                # Si el valor contiene paréntesis, extraer solo el porcentaje
                if '(' in change_val and ')' in change_val:
                    pct_match = re.search(r'\(([^)]+)\)', change_val)
                    if pct_match:
                        change_val = pct_match.group(1)
                # Convertir a float para comparar
                try:
                    change_float = float(change_val.replace('%', ''))
                    if abs(change_float) <= 3:
                        left_hip_comparison = f" The bone mineral density in the left femoral neck remained stable since {year}."
                    else:
                        change_text = "decreased" if "-" in left_hip_change else "increased"
                        left_hip_comparison = f" The bone mineral density [{change_text}] by {change_val} since {year}."
                except ValueError:
                    # Si no se puede convertir, usar lógica antigua
                    change_text = "decreased" if "-" in left_hip_change else "increased"
                    left_hip_comparison = f" The bone mineral density [{change_text}] by {change_val} since {year}."
        
        zscore_text = f" and a Z-score of {left_hip_zscore}" if left_hip_zscore and str(left_hip_zscore) != 'None' else ""
        left_hip_section = f"<strong>LEFT HIP (FEMORAL NECK):</strong> The bone mineral density in the left femoral neck is {left_hip_bmd} g/cm² with a T-score of {left_hip_tscore}{zscore_text}.{left_hip_comparison}\n\n"
    
    # Construir texto de comparación para lumbar si hay datos históricos
    lumbar_comparison = ""
    lumbar_prev_date = data.get('lumbar_prev_date')
    lumbar_change = data.get('lumbar_change_percent')
    if lumbar_prev_date and lumbar_change:
        # Extraer año de la fecha (formato MM/DD/YYYY)
        year_match = re.match(r'\d{2}/\d{2}/(\d{4})', lumbar_prev_date)
        if year_match:
            year = year_match.group(1)
            change_val = lumbar_change.replace('-', '').replace('+', '').replace('#', '').replace('*', '')
            # Si el valor contiene paréntesis, extraer solo el porcentaje
            if '(' in change_val and ')' in change_val:
                pct_match = re.search(r'\(([^)]+)\)', change_val)
                if pct_match:
                    change_val = pct_match.group(1)
            # Convertir a float para comparar
            try:
                change_float = float(change_val.replace('%', ''))
                if abs(change_float) <= 3:
                    lumbar_comparison = f" The bone mineral density in the lumbar spine remained stable since {year}."
                else:
                    # Determinar si es aumento o disminución
                    change_text = "decreased" if "-" in lumbar_change else "increased"
                    lumbar_comparison = f" The bone mineral density in the lumbar spine [{change_text}] by {change_val} since {year}."
            except ValueError:
                # Si no se puede convertir, usar lógica antigua
                change_text = "decreased" if "-" in lumbar_change else "increased"
                lumbar_comparison = f" The bone mineral density in the lumbar spine [{change_text}] by {change_val} since {year}."
    
    # Construir texto de comparación histórica general
    # Si hay distintas fechas por región, mostrarlas todas para evitar ambigüedad
    comparison_sources = [
        ('lumbar spine', data.get('lumbar_prev_date')),
        ('right forearm', data.get('right_forearm_prev_date')),
        ('left forearm', data.get('left_forearm_prev_date')),
        ('right hip', data.get('right_hip_prev_date')),
        ('left hip', data.get('left_hip_prev_date')),
    ]

    comparison_entries = []
    seen_dates = set()
    for region, date_value in comparison_sources:
        if date_value:
            date_clean = str(date_value).strip()
            if date_clean and date_clean not in seen_dates:
                comparison_entries.append((region, date_clean))
                seen_dates.add(date_clean)

    if not comparison_entries:
        comparison_text = "[None available]"
    elif len(comparison_entries) == 1:
        comparison_text = comparison_entries[0][1]
    elif len(comparison_entries) == 2:
        comparison_text = f"{comparison_entries[0][1]}; {comparison_entries[1][1]}"
    else:
        comparison_dates = [date_val for _, date_val in comparison_entries]
        comparison_text = ', '.join(comparison_dates[:-1]) + f", and {comparison_dates[-1]}"
    
    # Construir sección de LUMBAR SPINE solo si tiene datos
    lumbar_section = ""
    if has_lumbar:
        lumbar_bmd = data.get('lumbar_bmd', '')
        lumbar_tscore = data.get('lumbar_tscore', '')
        lumbar_range = data.get('lumbar_vertebrae_range', 'L1-L4')  # Default a L1-L4
        zscore_text = f" and a Z-score of {lumbar_zscore}" if lumbar_zscore and str(lumbar_zscore) != 'None' else ""
        lumbar_section = f"<strong>LUMBAR SPINE:</strong> The bone mineral density in the lumbar spine ({lumbar_range}) is {lumbar_bmd} g/cm² with a T-score of {lumbar_tscore}{zscore_text}.{lumbar_comparison}\n\n"
    
    report = f"""<strong>EXAM: BONE DENSITOMETRY</strong>

<strong>History:</strong> Evaluate for osteoporosis.
Technique: Bone density study was performed to evaluate {technique_text}.
Comparison: {comparison_text}.

<strong>FINDINGS:</strong>
{lumbar_section}{right_forearm_section}{left_forearm_section}{right_hip_section}{left_hip_section}
{frax_section}<strong>IMPRESSION:</strong>
{generate_impression(data, hip_side)}
"""
    
    return report

def save_report_to_file(report_text, mrn, acc):
    """Guarda el reporte BD como archivo de texto"""
    try:
        reports_dir = Path("/home/ubuntu/DICOMReceiver/reports")
        reports_dir.mkdir(exist_ok=True)
        
        # Nombre del archivo: bd_report_MRN_ACC.txt
        filename = f"bd_report_{mrn}_{acc}.txt"
        filepath = reports_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"    ✓ Reporte guardado: {filename}")
        return True
    except Exception as e:
        print(f"    ⚠️  Error guardando reporte: {e}")
        return False

def insert_into_database(data, report_text):
    """
    Inserta o actualiza datos extraídos en PostgreSQL reports.bd
    
    Si ya existe un registro con el mismo MRN y ACC:
    - Combina los datos nuevos con los existentes
    - Regenera el reporte completo
    - Actualiza el registro
    """
    try:
        conn = psycopg2.connect(
            host="localhost",
            user="facundo",
            password="qii123",
            database="qii"
        )
        
        cursor = conn.cursor()
        
        # Extraer MRN y Accession Number
        mrn = data.get('patient_id', '')
        acc = data.get('accession_number', '')
        
        # Verificar si ya existe un registro con este MRN y Accession Number
        cursor.execute("""
            SELECT guid, left_hip_bmd, left_hip_tscore, left_hip_zscore,
                   right_hip_bmd, right_hip_tscore, right_hip_zscore,
                   lumbar_bmd, lumbar_tscore, lumbar_zscore,
                   left_forearm_bmd, left_forearm_tscore, left_forearm_zscore,
                   right_forearm_bmd, right_forearm_tscore, right_forearm_zscore,
                   major_fracture_risk, "hip_fracture_risk│", "WHO_Classification",
                   major_fracture_risk_prior, hip_fracture_risk_prior,
                   lumbar_prev_date, lumbar_prev_bmd, lumbar_change_percent,
                   left_hip_prev_date, left_hip_prev_bmd, left_hip_change_percent,
                   right_hip_prev_date, right_hip_prev_bmd, right_hip_change_percent,
                   left_forearm_prev_date, left_forearm_prev_bmd, left_forearm_change_percent,
                   right_forearm_prev_date, right_forearm_prev_bmd, right_forearm_change_percent
            FROM reports.bd 
            WHERE mrn = %s AND acc = %s
        """, (mrn, acc))
        
        existing = cursor.fetchone()
        
        if existing:
            # Ya existe - ACTUALIZAR combinando datos
            print(f"\n📝 Registro existente encontrado - Actualizando con datos adicionales")
            print(f"   └─ MRN: {mrn}, ACC: {acc}")
            
            existing_guid = existing[0]
            existing_data = {
                'left_hip_bmd': existing[1],
                'left_hip_tscore': existing[2],
                'left_hip_zscore': existing[3],
                'right_hip_bmd': existing[4],
                'right_hip_tscore': existing[5],
                'right_hip_zscore': existing[6],
                'lumbar_bmd': existing[7],
                'lumbar_tscore': existing[8],
                'lumbar_zscore': existing[9],
                'left_forearm_bmd': existing[10],
                'left_forearm_tscore': existing[11],
                'left_forearm_zscore': existing[12],
                'right_forearm_bmd': existing[13],
                'right_forearm_tscore': existing[14],
                'right_forearm_zscore': existing[15],
                'major_fracture_risk': existing[16],
                'hip_fracture_risk': existing[17],
                'who_classification': existing[18],
                'major_fracture_risk_prior': existing[19],
                'hip_fracture_risk_prior': existing[20],
                'lumbar_prev_date': existing[21],
                'lumbar_prev_bmd': existing[22],
                'lumbar_change_percent': existing[23],
                'left_hip_prev_date': existing[24],
                'left_hip_prev_bmd': existing[25],
                'left_hip_change_percent': existing[26],
                'right_hip_prev_date': existing[27],
                'right_hip_prev_bmd': existing[28],
                'right_hip_change_percent': existing[29],
                'left_forearm_prev_date': existing[30],
                'left_forearm_prev_bmd': existing[31],
                'left_forearm_change_percent': existing[32],
                'right_forearm_prev_date': existing[33],
                'right_forearm_prev_bmd': existing[34],
                'right_forearm_change_percent': existing[35],
            }
            
            # Combinar datos: validar calidad de nuevos datos antes de sobrescribir
            # IMPORTANTE: Preservar lumbar_vertebrae_range ANTES de hacer el copy
            existing_lumbar_range = combined_data.get('lumbar_vertebrae_range') if 'combined_data' in locals() else None
            
            combined_data = data.copy()
            
            # Restaurar lumbar_vertebrae_range si exist un valor válido previo y el nuevo es None
            if existing_lumbar_range and not combined_data.get('lumbar_vertebrae_range'):
                combined_data['lumbar_vertebrae_range'] = existing_lumbar_range
            
            for key, value in existing_data.items():
                new_value = combined_data.get(key)
                
                # DESERT: No sobrescribir valores *_prior ya existentes.
                # En estudios mixtos (mismo ACC) Memorial puede poblar estos campos,
                # y un update posterior de Desert no debe borrarlos.
                if key in ['major_fracture_risk_prior', 'hip_fracture_risk_prior']:
                    combined_data[key] = str(value) if value is not None else None
                    continue
                
                # Si nuevo es None/vacío, usar existente
                if new_value is None or new_value == '':
                    combined_data[key] = str(value) if value is not None else None
                # Si es FRAX, validar que sea porcentaje válido (no BMD) y mantener el MAYOR
                elif key in ['major_fracture_risk', 'hip_fracture_risk']:
                    # Validar nuevo valor FRAX
                    new_str = str(new_value).strip()
                    is_valid_frax = False
                    new_frax_num = None
                    if '%' in new_str:
                        is_valid_frax = True
                        try:
                            new_frax_num = float(new_str.replace('%', ''))
                        except:
                            is_valid_frax = False
                    else:
                        # Si no tiene %, debe ser < 20 para ser FRAX (no BMD que es ~0.8-1.2)
                        try:
                            new_frax_num = float(new_str.replace('%', ''))
                            is_valid_frax = new_frax_num < 20
                        except:
                            is_valid_frax = False
                    
                    # Validar valor existente
                    existing_frax_num = None
                    if value is not None:
                        try:
                            existing_frax_num = float(str(value).replace('%', ''))
                        except:
                            pass
                    
                    # Mantener el MAYOR valor de FRAX válido
                    if is_valid_frax and new_frax_num is not None:
                        if existing_frax_num is None or new_frax_num > existing_frax_num:
                            combined_data[key] = new_value
                        else:
                            combined_data[key] = str(value)
                    elif value is not None:
                        combined_data[key] = str(value)
                # Para otros campos, usar nuevo si existe, sino existente
                else:
                    if value is not None and (new_value is None or new_value == ''):
                        combined_data[key] = str(value)
            
            # DESERT: No hay lógica de priorización Memorial
            # Todos los archivos son single-hip con igual prioridad
            
            # Asegurar que patient_id y accession_number estén presentes
            combined_data['patient_id'] = mrn
            combined_data['accession_number'] = acc
            
            # DESERT: No hay flags temporales que limpiar
            
            # Preservar lumbar_vertebrae_range: solo sobrescribir si el nuevo valor NO es None
            # Verificar primero en la caché global, luego en data
            patient_id_key = data.get('patient_id') or mrn
            if patient_id_key in _lumbar_vertebrae_cache:
                combined_data['lumbar_vertebrae_range'] = _lumbar_vertebrae_cache[patient_id_key]
            elif 'lumbar_vertebrae_range' in data and data.get('lumbar_vertebrae_range'):
                combined_data['lumbar_vertebrae_range'] = data['lumbar_vertebrae_range']
                _lumbar_vertebrae_cache[patient_id_key] = data['lumbar_vertebrae_range']
            elif 'lumbar_vertebrae_range' not in combined_data or not combined_data.get('lumbar_vertebrae_range'):
                combined_data['lumbar_vertebrae_range'] = 'L1-L4'  # Default solo si no existe
            # Si combined_data ya tiene un valor válido y data tiene None, no hacer nada (preservar el existente)
            
            # Determinar hip_side basado en qué datos existen
            # Prioridad: si ya está en data, usarlo; sino deducir de los datos combinados
            if 'hip_side' not in combined_data or not combined_data['hip_side']:
                if combined_data.get('left_hip_bmd') or combined_data.get('left_hip_tscore'):
                    combined_data['hip_side'] = 'left'
                elif combined_data.get('right_hip_bmd') or combined_data.get('right_hip_tscore'):
                    combined_data['hip_side'] = 'right'
                else:
                    combined_data['hip_side'] = None
            
            # Regenerar reporte con datos combinados
            combined_report = generate_report(combined_data)
            
            # Guardar reporte como archivo .txt
            save_report_to_file(combined_report, mrn, acc)
            
            # Función para limpiar y convertir valores con 3 decimales de precisión
            def to_float(val):
                if not val:
                    return None
                val_str = str(val).replace('%', '').strip()
                try:
                    return round(float(val_str), 3)
                except:
                    return None
            
            # Convertir valores numéricos
            left_hip_bmd = to_float(combined_data.get('left_hip_bmd'))
            left_hip_tscore = to_float(combined_data.get('left_hip_tscore'))
            left_hip_zscore = to_float(combined_data.get('left_hip_zscore'))
            right_hip_bmd = to_float(combined_data.get('right_hip_bmd'))
            right_hip_tscore = to_float(combined_data.get('right_hip_tscore'))
            right_hip_zscore = to_float(combined_data.get('right_hip_zscore'))
            lumbar_bmd = to_float(combined_data.get('lumbar_bmd'))
            lumbar_tscore = to_float(combined_data.get('lumbar_tscore'))
            lumbar_zscore = to_float(combined_data.get('lumbar_zscore'))
            left_forearm_bmd = to_float(combined_data.get('left_forearm_bmd'))
            left_forearm_tscore = to_float(combined_data.get('left_forearm_tscore'))
            left_forearm_zscore = to_float(combined_data.get('left_forearm_zscore'))
            right_forearm_bmd = to_float(combined_data.get('right_forearm_bmd'))
            right_forearm_tscore = to_float(combined_data.get('right_forearm_tscore'))
            right_forearm_zscore = to_float(combined_data.get('right_forearm_zscore'))
            hip_fracture_risk = to_float(combined_data.get('hip_fracture_risk'))
            major_fracture_risk = to_float(combined_data.get('major_fracture_risk'))
            major_fracture_risk_prior = to_float(combined_data.get('major_fracture_risk_prior'))
            hip_fracture_risk_prior = to_float(combined_data.get('hip_fracture_risk_prior'))
            
            # Datos de comparación histórica (almacenar como texto)
            lumbar_prev_date = combined_data.get('lumbar_prev_date')
            lumbar_prev_bmd = to_float(combined_data.get('lumbar_prev_bmd'))
            lumbar_change_percent = combined_data.get('lumbar_change_percent')
            left_hip_prev_date = combined_data.get('left_hip_prev_date')
            left_hip_prev_bmd = to_float(combined_data.get('left_hip_prev_bmd'))
            left_hip_change_percent = combined_data.get('left_hip_change_percent')
            right_hip_prev_date = combined_data.get('right_hip_prev_date')
            right_hip_prev_bmd = to_float(combined_data.get('right_hip_prev_bmd'))
            right_hip_change_percent = combined_data.get('right_hip_change_percent')
            left_forearm_prev_date = combined_data.get('left_forearm_prev_date')
            left_forearm_prev_bmd = to_float(combined_data.get('left_forearm_prev_bmd'))
            left_forearm_change_percent = combined_data.get('left_forearm_change_percent')
            right_forearm_prev_date = combined_data.get('right_forearm_prev_date')
            right_forearm_prev_bmd = to_float(combined_data.get('right_forearm_prev_bmd'))
            right_forearm_change_percent = combined_data.get('right_forearm_change_percent')
            
            # UPDATE
            cursor.execute("""
                UPDATE reports.bd SET
                    report = %s,
                    left_hip_bmd = %s,
                    left_hip_tscore = %s,
                    left_hip_zscore = %s,
                    right_hip_bmd = %s,
                    right_hip_tscore = %s,
                    right_hip_zscore = %s,
                    lumbar_bmd = %s,
                    lumbar_tscore = %s,
                    lumbar_zscore = %s,
                    left_forearm_bmd = %s,
                    left_forearm_tscore = %s,
                    left_forearm_zscore = %s,
                    right_forearm_bmd = %s,
                    right_forearm_tscore = %s,
                    right_forearm_zscore = %s,
                    "hip_fracture_risk│" = %s,
                    "WHO_Classification" = %s,
                    major_fracture_risk = %s,
                    major_fracture_risk_prior = %s,
                    hip_fracture_risk_prior = %s,
                    lumbar_prev_date = %s,
                    lumbar_prev_bmd = %s,
                    lumbar_change_percent = %s,
                    left_hip_prev_date = %s,
                    left_hip_prev_bmd = %s,
                    left_hip_change_percent = %s,
                    right_hip_prev_date = %s,
                    right_hip_prev_bmd = %s,
                    right_hip_change_percent = %s,
                    left_forearm_prev_date = %s,
                    left_forearm_prev_bmd = %s,
                    left_forearm_change_percent = %s,
                    right_forearm_prev_date = %s,
                    right_forearm_prev_bmd = %s,
                    right_forearm_change_percent = %s,
                    receivedon = %s
                WHERE guid = %s
            """, (
                combined_report,
                left_hip_bmd, left_hip_tscore, left_hip_zscore,
                right_hip_bmd, right_hip_tscore, right_hip_zscore,
                lumbar_bmd, lumbar_tscore, lumbar_zscore,
                left_forearm_bmd, left_forearm_tscore, left_forearm_zscore,
                right_forearm_bmd, right_forearm_tscore, right_forearm_zscore,
                hip_fracture_risk, combined_data.get('who_classification'),
                major_fracture_risk, major_fracture_risk_prior, hip_fracture_risk_prior,
                lumbar_prev_date, lumbar_prev_bmd, lumbar_change_percent,
                left_hip_prev_date, left_hip_prev_bmd, left_hip_change_percent,
                right_hip_prev_date, right_hip_prev_bmd, right_hip_change_percent,
                left_forearm_prev_date, left_forearm_prev_bmd, left_forearm_change_percent,
                right_forearm_prev_date, right_forearm_prev_bmd, right_forearm_change_percent,
                datetime.now(),
                existing_guid
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"\n✅ Registro ACTUALIZADO en PostgreSQL")
            print(f"   └─ GUID: {existing_guid}")
            print(f"   └─ Datos combinados: Lumbar BMD={lumbar_bmd}, Left Hip BMD={left_hip_bmd}, Right Hip BMD={right_hip_bmd}")
            
            return True
        
        else:
            # No existe - INSERTAR nuevo registro
            print(f"\n📝 Nuevo registro - Insertando en base de datos")
            
            # Limpiar campos temporales (flags de control)
            data.pop('_is_memorial_frax', None)
            
            # Generar GUID único
            guid = str(uuid.uuid4())
            
            # Función para limpiar y convertir valores con 3 decimales de precisión
            def to_float(val):
                if not val:
                    return None
                val_str = str(val).replace('%', '').strip()
                try:
                    return round(float(val_str), 3)
                except:
                    return None
            
            # Convertir valores numéricos
            left_hip_bmd = to_float(data.get('left_hip_bmd'))
            left_hip_tscore = to_float(data.get('left_hip_tscore'))
            left_hip_zscore = to_float(data.get('left_hip_zscore'))
            right_hip_bmd = to_float(data.get('right_hip_bmd'))
            right_hip_tscore = to_float(data.get('right_hip_tscore'))
            right_hip_zscore = to_float(data.get('right_hip_zscore'))
            lumbar_bmd = to_float(data.get('lumbar_bmd'))
            lumbar_tscore = to_float(data.get('lumbar_tscore'))
            lumbar_zscore = to_float(data.get('lumbar_zscore'))
            left_forearm_bmd = to_float(data.get('left_forearm_bmd'))
            left_forearm_tscore = to_float(data.get('left_forearm_tscore'))
            left_forearm_zscore = to_float(data.get('left_forearm_zscore'))
            right_forearm_bmd = to_float(data.get('right_forearm_bmd'))
            right_forearm_tscore = to_float(data.get('right_forearm_tscore'))
            right_forearm_zscore = to_float(data.get('right_forearm_zscore'))
            hip_fracture_risk = to_float(data.get('hip_fracture_risk'))
            major_fracture_risk = to_float(data.get('major_fracture_risk'))
            
            # DESERT: Siempre None para valores "with prior fracture"
            major_fracture_risk_prior = None
            hip_fracture_risk_prior = None
            
            # Datos de comparación histórica
            lumbar_prev_date = data.get('lumbar_prev_date')
            lumbar_prev_bmd = to_float(data.get('lumbar_prev_bmd'))
            lumbar_change_percent = data.get('lumbar_change_percent')
            left_hip_prev_date = data.get('left_hip_prev_date')
            left_hip_prev_bmd = to_float(data.get('left_hip_prev_bmd'))
            left_hip_change_percent = data.get('left_hip_change_percent')
            right_hip_prev_date = data.get('right_hip_prev_date')
            right_hip_prev_bmd = to_float(data.get('right_hip_prev_bmd'))
            right_hip_change_percent = data.get('right_hip_change_percent')
            left_forearm_prev_date = data.get('left_forearm_prev_date')
            left_forearm_prev_bmd = to_float(data.get('left_forearm_prev_bmd'))
            left_forearm_change_percent = data.get('left_forearm_change_percent')
            right_forearm_prev_date = data.get('right_forearm_prev_date')
            right_forearm_prev_bmd = to_float(data.get('right_forearm_prev_bmd'))
            right_forearm_change_percent = data.get('right_forearm_change_percent')
            
            # Generar reporte
            report_text = generate_report(data)
            
            # Guardar reporte como archivo .txt
            save_report_to_file(report_text, mrn, acc)
            
            # INSERT
            cursor.execute("""
                INSERT INTO reports.bd (
                    guid, mrn, acc, pat_name, report,
                    left_hip_bmd, left_hip_tscore, left_hip_zscore,
                    right_hip_bmd, right_hip_tscore, right_hip_zscore,
                    lumbar_bmd, lumbar_tscore, lumbar_zscore,
                    left_forearm_bmd, left_forearm_tscore, left_forearm_zscore,
                    right_forearm_bmd, right_forearm_tscore, right_forearm_zscore,
                    "hip_fracture_risk│", "WHO_Classification",
                    major_fracture_risk, major_fracture_risk_prior, hip_fracture_risk_prior,
                    lumbar_prev_date, lumbar_prev_bmd, lumbar_change_percent,
                    left_hip_prev_date, left_hip_prev_bmd, left_hip_change_percent,
                    right_hip_prev_date, right_hip_prev_bmd, right_hip_change_percent,
                    left_forearm_prev_date, left_forearm_prev_bmd, left_forearm_change_percent,
                    right_forearm_prev_date, right_forearm_prev_bmd, right_forearm_change_percent,
                    receivedon, studydate
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
            """, (
                guid, mrn, acc, data.get('patient_name'), report_text,
                left_hip_bmd, left_hip_tscore, left_hip_zscore,
                right_hip_bmd, right_hip_tscore, right_hip_zscore,
                lumbar_bmd, lumbar_tscore, lumbar_zscore,
                left_forearm_bmd, left_forearm_tscore, left_forearm_zscore,
                right_forearm_bmd, right_forearm_tscore, right_forearm_zscore,
                hip_fracture_risk, data.get('who_classification'),
                major_fracture_risk, major_fracture_risk_prior, hip_fracture_risk_prior,
                lumbar_prev_date, lumbar_prev_bmd, lumbar_change_percent,
                left_hip_prev_date, left_hip_prev_bmd, left_hip_change_percent,
                right_hip_prev_date, right_hip_prev_bmd, right_hip_change_percent,
                left_forearm_prev_date, left_forearm_prev_bmd, left_forearm_change_percent,
                right_forearm_prev_date, right_forearm_prev_bmd, right_forearm_change_percent,
                datetime.now(), datetime.now()
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"\n✅ Datos insertados en PostgreSQL")
            print(f"   └─ GUID: {guid}")
            print(f"   └─ MRN: {mrn}")
            print(f"   └─ ACC: {acc}")
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
        
        # Find ALL DICOM files for this patient
        dicom_base = Path("/home/ubuntu/DICOMReceiver/dicom_storage")
        patient_path = dicom_base / patient_id
        
        if not patient_path.exists():
            print(f"  ✗ Patient directory not found")
            continue
        
        # Get all DICOM files from all study directories
        dicom_files = []
        for study_dir in patient_path.iterdir():
            if study_dir.is_dir():
                for dcm_file in study_dir.glob("BD_*"):
                    if dcm_file.is_file():
                        dicom_files.append(dcm_file)
        
        if not dicom_files:
            print(f"  ✗ No DICOM files found")
            continue
        
        print(f"  ✓ Found {len(dicom_files)} DICOM file(s)")
        
        # Separar archivos por ReportType y tipo de scan (Lumbar Spine primero)
        # Procesar Lumbar Spine PRIMERO para capturar lumbar_vertebrae_range
        # Luego ReportType=1, luego otros, finalmente ReportType=9
        files_lumbar = []
        files_type_1 = []
        files_type_9 = []
        files_other = []
        
        for dcm_file in dicom_files:
            try:
                ds = pydicom.dcmread(dcm_file, stop_before_pixels=True, force=True)
                if (0x0019, 0x1000) in ds:
                    xml_data = ds[0x0019, 0x1000].value
                    if isinstance(xml_data, bytes):
                        xml_check = xml_data.decode('utf-8', errors='ignore')
                    else:
                        xml_check = str(xml_data)
                    
                    # Verificar si es Lumbar Spine
                    is_lumbar = False
                    scan_mode_match = re.search(r'ScanMode\s*=\s*"([^"]+)"', xml_check)
                    if scan_mode_match and 'SPINE' in scan_mode_match.group(1).upper():
                        is_lumbar = True
                    
                    if is_lumbar:
                        files_lumbar.append(dcm_file)
                    else:
                        report_type_match = re.search(r'<ReportType>\s*(\d+)', xml_check)
                        if report_type_match:
                            report_type = report_type_match.group(1).strip()
                            if report_type == '1':
                                files_type_1.append(dcm_file)
                            elif report_type == '9':
                                files_type_9.append(dcm_file)
                            else:
                                files_other.append(dcm_file)
                        else:
                            files_other.append(dcm_file)
            except:
                files_other.append(dcm_file)
        
        # Procesar en orden: Lumbar primero, luego ReportType=1, otros, ReportType=9 (último sobrescribe)
        dicom_files_sorted = files_lumbar + files_type_1 + files_other + files_type_9
        
        # Process each DICOM file
        for dcm_file in dicom_files_sorted:
            print(f"\n  Processing: {dcm_file.name[:50]}...")
            
            # Extract and save XML, and get AccessionNumber from DICOM
            xml_text, accession_number, xml_file_path = extract_and_save_xml(dcm_file, patient_id)
            if not xml_text:
                print(f"    ✗ No XML found in this DICOM file")
                continue
            
            # Parse XML data
            data = extract_from_xml(xml_text)
            
            # Verificar si la procedencia es Memorial - DESACTIVADO (ahora procesamos Memorial también)
            # institution = data.get('institution', '')
            # if institution and 'memorial' in institution.lower():
            #     print(f"    ⚠️  Estudio de MEMORIAL detectado (institución: {institution}) - SALTANDO")
            #     continue
            
            # Detectar hip_side del ScanMode
            hip_side_match = re.search(r'ScanMode\s*=\s*"([^"]*)"', xml_text)
            if hip_side_match:
                scan_mode = hip_side_match.group(1).upper()
                if 'LEFT' in scan_mode and 'HIP' in scan_mode:
                    data['hip_side'] = 'left'
                elif 'RIGHT' in scan_mode and 'HIP' in scan_mode:
                    data['hip_side'] = 'right'
            
            # Verificar si es paciente pediátrico
            if is_pediatric_patient(xml_text, data.get('age')):
                print(f"    ⚠️  Paciente PEDIÁTRICO detectado (edad: {data.get('age')}) - SALTANDO")
                continue
            
            # Agregar AccessionNumber a los datos
            data['accession_number'] = accession_number
            
            print(f"    ✓ Extracted from XML: {len([v for v in data.values() if v])} fields")
            print(f"    ✓ AccessionNumber: {accession_number}")
            
            # Verificar si Major FRAX fue extraído del XML
            if data.get('major_fracture_risk'):
                print(f"    ✓ Major FRAX from XML: {data.get('major_fracture_risk')}")
            else:
                # Solo intentar OCR si hay JPEG disponible y no se encontró en XML
                jpeg_base = Path("/home/ubuntu/DICOMReceiver/pixel_extraction/BD") / patient_id
                jpeg_files = list(jpeg_base.glob("*.jpg")) if jpeg_base.exists() else []
                
                if jpeg_files:
                    major_frax = extract_major_frax_from_ocr(jpeg_files[0])
                    if major_frax:
                        data['major_fracture_risk'] = major_frax
                        print(f"    ✓ Extracted from OCR: Major FRAX = {major_frax}%")
                else:
                    print(f"    ⚠️  No JPEG available for OCR")
            
            # Verificar Hip FRAX
            if data.get('hip_fracture_risk'):
                print(f"    ✓ Hip FRAX from XML: {data.get('hip_fracture_risk')}")
            
            # Insert/Update into PostgreSQL (will merge with existing record if any)
            print(f"\n    📊 Guardando en PostgreSQL...")
            if insert_into_database(data, None):  # Report will be generated in insert function
                print(f"    ✅ Datos guardados en reports.bd")
            else:
                print(f"    ⚠️  Error guardando en BD")


