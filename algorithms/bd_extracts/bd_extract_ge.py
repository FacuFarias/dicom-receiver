#!/usr/bin/env python3
"""
BD Extraction for GE Healthcare Lunar Equipment

GE Lunar equipment sends bone density data in DICOM Structured Report (SR) format.
This script extracts BMD values, T-scores, Z-scores, and FRAX data from the SR.

Author: System
Date: 2026-02-24
"""

import sys
import re
import uuid
import pydicom
import psycopg2
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

# Importar funciones compartidas de Hologic
import sys
sys.path.append(str(Path(__file__).parent))
from bd_extract_hologic import generate_report


def parse_numeric_value(value):
    """Convierte texto numérico GE a float, soportando coma decimal (ej: '1,023')."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().strip('"')
    if not text:
        return None

    # Si solo hay coma, se asume separador decimal.
    if ',' in text and '.' not in text:
        text = text.replace(',', '.')
    # Si hay ambos separadores, quitar comas como miles.
    elif ',' in text and '.' in text:
        text = text.replace(',', '')

    try:
        return float(text)
    except ValueError:
        return None


def normalize_lumbar_range(roi_name):
    """Normaliza un rango lumbar tipo L1-L4; retorna None si no es rango lumbar válido."""
    if not roi_name:
        return None
    match = re.match(r'^\s*(L[1-4])\s*-\s*(L[1-4])\s*$', str(roi_name), re.IGNORECASE)
    if not match:
        return None
    return f"{match.group(1).upper()}-{match.group(2).upper()}"


def lumbar_range_priority(roi_name):
    """Prioridad de rangos lumbares: L1-L4 > otros rangos válidos > inválido."""
    normalized = normalize_lumbar_range(roi_name)
    if not normalized:
        return -1
    if normalized == 'L1-L4':
        return 100
    start = int(normalized[1])
    end = int(normalized[4])
    if end <= start:
        return -1
    return end - start


def extract_from_xml_imagecomments(ds):
    """
    Extrae datos del tag ImageComments (0020,4000) que contiene XML estructurado.
    
    GE Lunar incluye toda la información en formato XML dentro del tag ImageComments.
    Hay dos formatos diferentes:
    
    Formato 1 (más antiguo): <DENSITOMETRY_RESULTS>
    Formato 2 (más nuevo): <DXA_RESULTS>
    
    Args:
        ds: pydicom Dataset
        
    Returns:
        dict con los datos extraídos, o None si no hay ImageComments o no se puede parsear
    """
    if not hasattr(ds, 'ImageComments'):
        return None
    
    xml_str = ds.ImageComments
    
    try:
        root = ET.fromstring(xml_str)
        
        # Detectar formato
        if root.tag == 'DENSITOMETRY_RESULTS':
            return parse_densitometry_results_format(root, ds)
        elif root.tag == 'DXA_RESULTS':
            return parse_dxa_results_format(root, ds)
        else:
            print(f"⚠️  Formato XML desconocido: {root.tag}")
            return None
            
    except ET.ParseError as e:
        print(f"⚠️  Error parseando XML: {e}")
        return None


def parse_densitometry_results_format(root, ds):
    """
    Parsea formato XML: <DENSITOMETRY_RESULTS> (formato más antiguo)
    
    Estructura:
    <DENSITOMETRY_RESULTS>
      <CURRENT_EXAM>
        <SCAN type="AP Spine">
          <TREND>
            <TREND_ROI>L1-L4</TREND_ROI>
            <BASELINE_EXAM_DATE>3/13/2023</BASELINE_EXAM_DATE>
            <EXAM>
              <EXAM_DATE>3/13/2023</EXAM_DATE>
              <BMD>1.042</BMD>
              <YAT>-1.2</YAT>
              <AMZ>0.7</AMZ>
            </EXAM>
            <EXAM>
              <EXAM_DATE>4/6/2026</EXAM_DATE>
              <BMD>1.014</BMD>
              <YAT>-1.5</YAT>
              <AMZ>0.4</AMZ>
              <BMD_CHANGE>
                <TYPE>ROC_VS_PREVIOUS</TYPE>
                <VALUE>-2.7</VALUE>
              </BMD_CHANGE>
            </EXAM>
          </TREND>
        </SCAN>
      </CURRENT_EXAM>
    </DENSITOMETRY_RESULTS>
    """
    data = {
        'patient_id': getattr(ds, 'PatientID', None),
        'pat_name': str(getattr(ds, 'PatientName', '')),
        'accession_number': getattr(ds, 'AccessionNumber', None),
        
        'lumbar_bmd': None, 'lumbar_tscore': None, 'lumbar_zscore': None,
        'lumbar_vertebrae_range': None,
        'lumbar_prev_date': None, 'lumbar_prev_bmd': None, 'lumbar_change_percent': None,
        
        'left_hip_bmd': None, 'left_hip_tscore': None, 'left_hip_zscore': None,
        'left_hip_region': 'Femoral Neck',
        'left_hip_prev_date': None, 'left_hip_prev_bmd': None, 'left_hip_change_percent': None,
        
        'right_hip_bmd': None, 'right_hip_tscore': None, 'right_hip_zscore': None,
        'right_hip_region': 'Femoral Neck',
        'right_hip_prev_date': None, 'right_hip_prev_bmd': None, 'right_hip_change_percent': None,
        
        'left_total_hip_bmd': None, 'left_total_hip_tscore': None, 'left_total_hip_zscore': None,
        'right_total_hip_bmd': None, 'right_total_hip_tscore': None, 'right_total_hip_zscore': None,
        
        'left_forearm_bmd': None, 'left_forearm_tscore': None, 'left_forearm_zscore': None,
        'right_forearm_bmd': None, 'right_forearm_tscore': None, 'right_forearm_zscore': None,
    }
    
    current_exam = root.find('CURRENT_EXAM')
    if current_exam is None:
        return data
    
    # Buscar todos los SCAN
    for scan in current_exam.findall('SCAN'):
        scan_type = scan.get('type', '')
        
        trend = scan.find('TREND')
        if trend is None:
            continue
        
        trend_roi = trend.find('TREND_ROI')
        if trend_roi is None:
            continue
        
        roi_name = trend_roi.text
        
        # Buscar todos los EXAM (el último es el actual)
        exams = trend.findall('EXAM')
        if len(exams) < 1:
            continue
        
        # Current = último exam. Prior = penúltimo (inmediato anterior) si existe.
        current_exam_data = exams[-1]
        prior_exam = exams[-2] if len(exams) >= 2 else None
        
        # Extraer fecha del prior
        prior_date_str = None
        if prior_exam is not None:
            prior_date_elem = prior_exam.find('EXAM_DATE')
            prior_date_str = prior_date_elem.text if prior_date_elem is not None else None
        
        # Convertir fecha MM/DD/YYYY a YYYY-MM-DD
        prior_date = None
        if prior_date_str:
            try:
                date_parts = prior_date_str.split('/')
                if len(date_parts) == 3:
                    prior_date = f"{date_parts[2]}-{date_parts[0].zfill(2)}-{date_parts[1].zfill(2)}"
            except:
                pass
        
        # Extraer BMD del prior
        prior_bmd = None
        if prior_exam is not None:
            prior_bmd_elem = prior_exam.find('BMD')
            prior_bmd = parse_numeric_value(prior_bmd_elem.text) if prior_bmd_elem is not None else None
        
        # Extraer BMD actual
        current_bmd_elem = current_exam_data.find('BMD')
        current_bmd = parse_numeric_value(current_bmd_elem.text) if current_bmd_elem is not None else None
        
        # Extraer T-score actual (YAT)
        current_tscore_elem = current_exam_data.find('YAT')
        current_tscore = parse_numeric_value(current_tscore_elem.text) if current_tscore_elem is not None else None
        
        # Extraer Z-score actual (AMZ)
        current_zscore_elem = current_exam_data.find('AMZ')
        current_zscore = parse_numeric_value(current_zscore_elem.text) if current_zscore_elem is not None else None
        
        # Extraer cambio porcentual
        change_percent = None
        for bmd_change in current_exam_data.findall('BMD_CHANGE'):
            type_elem = bmd_change.find('TYPE')
            if type_elem is not None and type_elem.text == 'ROC_VS_PREVIOUS':
                value_elem = bmd_change.find('VALUE')
                if value_elem is not None:
                    change_percent = parse_numeric_value(value_elem.text)
                    break

        # Fallback: calcular cambio si no viene explícito en XML
        if change_percent is None and current_bmd is not None and prior_bmd is not None:
            try:
                if float(prior_bmd) != 0:
                    change_percent = ((float(current_bmd) - float(prior_bmd)) / float(prior_bmd)) * 100
            except (ValueError, TypeError, ZeroDivisionError):
                pass
        
        # Asignar a la región correspondiente
        # Aceptar rangos lumbares (L1-L4, L1-L3, L2-L4, etc.), no vértebras individuales
        normalized_lumbar_range = normalize_lumbar_range(roi_name)
        if normalized_lumbar_range:
            current_priority = lumbar_range_priority(normalized_lumbar_range)
            selected_priority = lumbar_range_priority(data.get('lumbar_vertebrae_range'))
            if current_priority >= selected_priority:
                data['lumbar_bmd'] = current_bmd
                data['lumbar_tscore'] = current_tscore
                data['lumbar_zscore'] = current_zscore
                data['lumbar_vertebrae_range'] = normalized_lumbar_range
                data['lumbar_prev_date'] = prior_date
                data['lumbar_prev_bmd'] = prior_bmd
                data['lumbar_change_percent'] = change_percent
            
        # Solo exactamente "Neck", no "Upper Neck", "Lower Neck", "Neck Mean", etc.
        elif roi_name == 'Neck':
            # Ajustar BMD si está en gramos (>100) a g/cm²
            if current_bmd and current_bmd > 10:
                current_bmd = current_bmd / 1000.0
            if prior_bmd and prior_bmd > 10:
                prior_bmd = prior_bmd / 1000.0
            
            if 'Left' in scan_type:
                data['left_hip_bmd'] = current_bmd
                data['left_hip_tscore'] = current_tscore
                data['left_hip_zscore'] = current_zscore
                data['left_hip_prev_date'] = prior_date
                data['left_hip_prev_bmd'] = prior_bmd
                data['left_hip_change_percent'] = change_percent
                
            elif 'Right' in scan_type:
                data['right_hip_bmd'] = current_bmd
                data['right_hip_tscore'] = current_tscore
                data['right_hip_zscore'] = current_zscore
                data['right_hip_prev_date'] = prior_date
                data['right_hip_prev_bmd'] = prior_bmd
                data['right_hip_change_percent'] = change_percent

        # Forearm (GE suele enviar Radius 33% en estudios de antebrazo)
        elif roi_name == 'Radius 33%':
            # Ajustar BMD si está en gramos (>100) a g/cm²
            if current_bmd and current_bmd > 10:
                current_bmd = current_bmd / 1000.0
            if prior_bmd and prior_bmd > 10:
                prior_bmd = prior_bmd / 1000.0

            if 'Left' in scan_type:
                data['left_forearm_bmd'] = current_bmd
                data['left_forearm_tscore'] = current_tscore
                data['left_forearm_zscore'] = current_zscore
                data['left_forearm_prev_date'] = prior_date
                data['left_forearm_prev_bmd'] = prior_bmd
                data['left_forearm_change_percent'] = change_percent

            elif 'Right' in scan_type:
                data['right_forearm_bmd'] = current_bmd
                data['right_forearm_tscore'] = current_tscore
                data['right_forearm_zscore'] = current_zscore
                data['right_forearm_prev_date'] = prior_date
                data['right_forearm_prev_bmd'] = prior_bmd
                data['right_forearm_change_percent'] = change_percent
        
        # Total Hip region
        elif roi_name == 'Total':
            # Ajustar BMD si está en gramos (>100) a g/cm²
            if current_bmd and current_bmd > 10:
                current_bmd = current_bmd / 1000.0
            if prior_bmd and prior_bmd > 10:
                prior_bmd = prior_bmd / 1000.0
            
            if 'Left' in scan_type:
                data['left_total_hip_bmd'] = current_bmd
                data['left_total_hip_tscore'] = current_tscore
                data['left_total_hip_zscore'] = current_zscore
                
            elif 'Right' in scan_type:
                data['right_total_hip_bmd'] = current_bmd
                data['right_total_hip_tscore'] = current_tscore
                data['right_total_hip_zscore'] = current_zscore
    
    return data


def parse_dxa_results_format(root, ds):
    """
    Parsea formato XML: <DXA_RESULTS> (formato más nuevo)
    
    Estructura:
    <DXA_RESULTS>
      <SCAN type="AP Spine">
        <ROI region="L1-L4">
          <BMD>1.071</BMD>
          <BMD_TSCORE>-1.0</BMD_TSCORE>
          <BMD_ZSCORE>1.0</BMD_ZSCORE>
        </ROI>
        <TREND region="L1-L4">
          <EXAM date="04/06/2026">
            <BMD>1.071</BMD>
            <CHANGE type="PCHANGE_VS_PREVIOUS">
              <BMD units="%">-0.9</BMD>
            </CHANGE>
          </EXAM>
          <EXAM date="07/30/2025">
            <BMD>1.081</BMD>
          </EXAM>
        </TREND>
      </SCAN>
    </DXA_RESULTS>
    """
    data = {
        'patient_id': getattr(ds, 'PatientID', None),
        'pat_name': str(getattr(ds, 'PatientName', '')),
        'accession_number': getattr(ds, 'AccessionNumber', None),
        
        'lumbar_bmd': None, 'lumbar_tscore': None, 'lumbar_zscore': None,
        'lumbar_vertebrae_range': None,
        'lumbar_prev_date': None, 'lumbar_prev_bmd': None, 'lumbar_change_percent': None,
        
        'left_hip_bmd': None, 'left_hip_tscore': None, 'left_hip_zscore': None,
        'left_hip_region': 'Femoral Neck',
        'left_hip_prev_date': None, 'left_hip_prev_bmd': None, 'left_hip_change_percent': None,
        
        'right_hip_bmd': None, 'right_hip_tscore': None, 'right_hip_zscore': None,
        'right_hip_region': 'Femoral Neck',
        'right_hip_prev_date': None, 'right_hip_prev_bmd': None, 'right_hip_change_percent': None,
        
        'left_total_hip_bmd': None, 'left_total_hip_tscore': None, 'left_total_hip_zscore': None,
        'right_total_hip_bmd': None, 'right_total_hip_tscore': None, 'right_total_hip_zscore': None,
        
        'left_forearm_bmd': None, 'left_forearm_tscore': None, 'left_forearm_zscore': None,
        'right_forearm_bmd': None, 'right_forearm_tscore': None, 'right_forearm_zscore': None,
    }
    
    # Buscar todos los SCAN
    for scan in root.findall('SCAN'):
        scan_type = scan.get('type', '')
        
        # Extraer datos actuales de ROI
        for roi in scan.findall('ROI'):
            region = roi.get('region', '')
            region_lower = region.lower() if region else ''
            scan_type_lower = scan_type.lower() if scan_type else ''
            
            bmd_elem = roi.find('BMD')
            tscore_elem = roi.find('BMD_TSCORE')
            zscore_elem = roi.find('BMD_ZSCORE')
            
            bmd = parse_numeric_value(bmd_elem.text) if bmd_elem is not None else None
            tscore = parse_numeric_value(tscore_elem.text) if tscore_elem is not None else None
            zscore = parse_numeric_value(zscore_elem.text) if zscore_elem is not None else None
            
            normalized_lumbar_range = None
            if region:
                range_match = re.search(r'\bL[1-4]\s*-\s*L[1-4]\b', region, re.IGNORECASE)
                if range_match:
                    normalized_lumbar_range = normalize_lumbar_range(range_match.group(0))

            if normalized_lumbar_range:
                current_priority = lumbar_range_priority(normalized_lumbar_range)
                selected_priority = lumbar_range_priority(data.get('lumbar_vertebrae_range'))
                if current_priority >= selected_priority:
                    data['lumbar_bmd'] = bmd
                    data['lumbar_tscore'] = tscore
                    data['lumbar_zscore'] = zscore
                    data['lumbar_vertebrae_range'] = normalized_lumbar_range
                
            elif 'neck left' in region_lower or (region_lower == 'neck' and 'left' in scan_type_lower):
                data['left_hip_bmd'] = bmd
                data['left_hip_tscore'] = tscore
                data['left_hip_zscore'] = zscore
                data['_left_hip_from_neck'] = True
                
            elif 'neck right' in region_lower or (region_lower == 'neck' and 'right' in scan_type_lower):
                data['right_hip_bmd'] = bmd
                data['right_hip_tscore'] = tscore
                data['right_hip_zscore'] = zscore
                data['_right_hip_from_neck'] = True
                
            elif 'total left' in region_lower or (region_lower == 'total' and 'left' in scan_type_lower):
                data['left_total_hip_bmd'] = bmd
                data['left_total_hip_tscore'] = tscore
                data['left_total_hip_zscore'] = zscore
                
            elif 'total right' in region_lower or (region_lower == 'total' and 'right' in scan_type_lower):
                data['right_total_hip_bmd'] = bmd
                data['right_total_hip_tscore'] = tscore
                data['right_total_hip_zscore'] = zscore
        
        # Extraer datos de TREND (prior comparison)
        for trend in scan.findall('TREND'):
            region = trend.get('region', '')
            region_lower = region.lower() if region else ''
            scan_type_lower = scan_type.lower() if scan_type else ''
            
            exams = trend.findall('EXAM')
            if len(exams) < 2:
                continue
            
            # Prior = segundo exam (más antiguo), Current = primer exam (más nuevo)
            current_exam = exams[0]
            prior_exam = exams[1]
            
            # Extraer fecha del prior
            prior_date_str = prior_exam.get('date', '')
            prior_date = None
            if prior_date_str:
                try:
                    date_parts = prior_date_str.split('/')
                    if len(date_parts) == 3:
                        prior_date = f"{date_parts[2]}-{date_parts[0].zfill(2)}-{date_parts[1].zfill(2)}"
                except:
                    pass
            
            # Extraer BMD del prior
            prior_bmd_elem = prior_exam.find('BMD')
            prior_bmd = parse_numeric_value(prior_bmd_elem.text) if prior_bmd_elem is not None else None
            
            # Extraer cambio porcentual
            change_percent = None
            for change in current_exam.findall('CHANGE'):
                if change.get('type') == 'PCHANGE_VS_PREVIOUS':
                    bmd_elem = change.find('BMD')
                    if bmd_elem is not None:
                        change_percent = parse_numeric_value(bmd_elem.text)
                        break

            # Fallback: calcular cambio si no viene explícito en XML
            current_bmd_elem = current_exam.find('BMD')
            current_bmd = parse_numeric_value(current_bmd_elem.text) if current_bmd_elem is not None else None
            if change_percent is None and current_bmd is not None and prior_bmd is not None:
                try:
                    if float(prior_bmd) != 0:
                        change_percent = ((float(current_bmd) - float(prior_bmd)) / float(prior_bmd)) * 100
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            
            # Asignar a la región correspondiente
            if region and re.search(r'\bL[1-4]\s*-\s*L[1-4]\b', region, re.IGNORECASE):
                data['lumbar_prev_date'] = prior_date
                data['lumbar_prev_bmd'] = prior_bmd
                data['lumbar_change_percent'] = change_percent

            elif 'neck left' in region_lower or (region_lower == 'neck' and 'left' in scan_type_lower):
                data['left_hip_prev_date'] = prior_date
                data['left_hip_prev_bmd'] = prior_bmd
                data['left_hip_change_percent'] = change_percent

            elif 'neck right' in region_lower or (region_lower == 'neck' and 'right' in scan_type_lower):
                data['right_hip_prev_date'] = prior_date
                data['right_hip_prev_bmd'] = prior_bmd
                data['right_hip_change_percent'] = change_percent
                
            elif 'Total Mean' in region or 'Neck Mean' in region:
                # El DualFemur envía Total Mean que aplica a ambos hips
                data['left_hip_prev_date'] = prior_date
                data['left_hip_prev_bmd'] = prior_bmd
                data['left_hip_change_percent'] = change_percent
                data['right_hip_prev_date'] = prior_date
                data['right_hip_prev_bmd'] = prior_bmd
                data['right_hip_change_percent'] = change_percent
    
    return data


def extract_from_sr(ds):
    """
    Extrae datos del DICOM Structured Report de GE Lunar.
    
    GE Lunar envía SR con estructura jerárquica de containers:
    - AP Spine > L1-L4 > [BMD, T-score, Z-score]
    - DualFemur > Neck Left/Right > [BMD, T-score, Z-score]
    
    Args:
        ds: pydicom Dataset del SR
        
    Returns:
        dict con los datos extraídos
    """
    data = {
        # Demográficos desde DICOM header
        'patient_id': None,
        'pat_name': None,
        'accession_number': None,
        
        # Lumbar Spine (L1-L4)
        'lumbar_bmd': None,
        'lumbar_tscore': None,
        'lumbar_zscore': None,
        'lumbar_vertebrae_range': None,
        
        # Left Hip (Femoral Neck)
        'left_hip_bmd': None,
        'left_hip_tscore': None,
        'left_hip_zscore': None,
        
        # Left Total Hip
        'left_total_hip_bmd': None,
        'left_total_hip_tscore': None,
        'left_total_hip_zscore': None,
        
        # Right Hip (Femoral Neck)
        'right_hip_bmd': None,
        'right_hip_tscore': None,
        'right_hip_zscore': None,

        # Flags internos para asegurar origen Femoral Neck en cadera
        '_left_hip_from_neck': False,
        '_right_hip_from_neck': False,
        
        # Right Total Hip
        'right_total_hip_bmd': None,
        'right_total_hip_tscore': None,
        'right_total_hip_zscore': None,
        
        # Left Forearm
        'left_forearm_bmd': None,
        'left_forearm_tscore': None,
        'left_forearm_zscore': None,
        
        # Right Forearm
        'right_forearm_bmd': None,
        'right_forearm_tscore': None,
        'right_forearm_zscore': None,
        
        # FRAX
        'major_fracture_risk': None,
        'hip_fracture_risk': None,
        'major_fracture_risk_prior': None,
        'hip_fracture_risk_prior': None,
        
        # WHO Classification
        'who_classification': None,
        
        # Datos previos (comparación)
        'lumbar_prev_date': None,
        'lumbar_prev_bmd': None,
        'lumbar_change_percent': None,
        'left_hip_prev_date': None,
        'left_hip_prev_bmd': None,
        'left_hip_change_percent': None,
        'right_hip_prev_date': None,
        'right_hip_prev_bmd': None,
        'right_hip_change_percent': None,
    }
    
    # Extraer datos del header DICOM
    data['patient_id'] = getattr(ds, 'PatientID', None)
    data['accession_number'] = getattr(ds, 'AccessionNumber', None)
    data['pat_name'] = str(getattr(ds, 'PatientName', '')).strip()
    
    # ═════════════════════════════════════════════════════════════════════
    # EXTRACCIÓN DE DATOS DEL STRUCTURED REPORT (ContentSequence)
    # ═════════════════════════════════════════════════════════════════════
    
    if not hasattr(ds, 'ContentSequence'):
        print("⚠️  Este DICOM SR no contiene ContentSequence")
        return data
    
    def get_concept_name(item):
        """Obtiene el CodeMeaning del ConceptNameCodeSequence"""
        if hasattr(item, 'ConceptNameCodeSequence') and len(item.ConceptNameCodeSequence) > 0:
            return getattr(item.ConceptNameCodeSequence[0], 'CodeMeaning', None)
        return None
    
    def get_numeric_value(item):
        """Extrae el valor numérico de un item NUM"""
        if hasattr(item, 'MeasuredValueSequence') and len(item.MeasuredValueSequence) > 0:
            return getattr(item.MeasuredValueSequence[0], 'NumericValue', None)
        return None
    
    def get_text_value(item):
        """Extrae el valor de texto de un item TEXT"""
        return getattr(item, 'TextValue', None)
    
    def extract_region_values(content_seq):
        """
        Extrae BMD, T-score y Z-score de un container de región.
        
        Args:
            content_seq: ContentSequence de un container de región (ej. "L1-L4", "Neck Left")
            
        Returns:
            dict con keys: 'bmd', 'tscore', 'zscore', 'bmc', 'area'
        """
        values = {
            'bmd': None,
            'tscore': None,
            'zscore': None,
            'bmc': None,
            'area': None
        }
        
        for item in content_seq:
            concept_name = get_concept_name(item)
            value_type = getattr(item, 'ValueType', None)
            
            if not concept_name:
                continue
            
            # Permitir tipos NUM y TEXT (T-scores y Z-scores vienen como TEXT)
            if value_type not in ('NUM', 'TEXT'):
                continue
            
            concept_lower = concept_name.lower()
            value = None
            
            # Extraer valor según el tipo
            if value_type == 'NUM':
                value = get_numeric_value(item)
            elif value_type == 'TEXT':
                # Los T-scores y Z-scores vienen como TEXT en formato string "-1.0", "1.0"
                text_value = get_text_value(item)
                if text_value:
                    try:
                        value = parse_numeric_value(text_value)
                    except (ValueError, AttributeError):
                        continue
            
            if value is None:
                continue
            
            # Identificar tipo de valor
            # IMPORTANTE: Debe ser exactamente "bmd" o "bone mineral density", 
            # no "bmd_pam", "bmd_pya", "bmd_tscore", etc.
            if concept_lower == 'bmd' or concept_lower == 'bone mineral density':
                values['bmd'] = float(value)
            elif 't-score' in concept_lower or 't score' in concept_lower or 'bmd_tscore' in concept_lower:
                values['tscore'] = float(value)
            elif 'z-score' in concept_lower or 'z score' in concept_lower or 'bmd_zscore' in concept_lower:
                values['zscore'] = float(value)
            elif 'bmc' in concept_lower or 'bone mineral content' in concept_lower:
                values['bmc'] = float(value)
            elif 'area' in concept_lower:
                values['area'] = float(value)
        
        return values
    
    def process_container(container_item):
        """
        Procesa un container DICOM SR y extrae datos de regiones específicas.
        
        Args:
            container_item: Item de ContentSequence con ValueType='CONTAINER'
        """
        container_name = get_concept_name(container_item)
        if not container_name or not hasattr(container_item, 'ContentSequence'):
            return
        
        container_lower = container_name.lower()
        
        # ─────────────────────────────────────────────────────────────────
        # AP SPINE (Lumbar L1-L4)
        # ─────────────────────────────────────────────────────────────────
        if 'ap spine' in container_lower or 'lumbar' in container_lower:
            # Buscar sub-container "L1-L4"
            for region_item in container_item.ContentSequence:
                region_name = get_concept_name(region_item)
                if not region_name:
                    continue
                
                region_lower = region_name.lower()
                
                # IMPORTANTE: Verificar Trend PRIMERO, antes de L1-L4, porque "Trend L1-L4" contiene "L1-L4"
                if 'trend' in region_lower and re.search(r'l[1-4]\s*-?\s*l[1-4]', region_lower):
                    if hasattr(region_item, 'ContentSequence'):
                        trend_info = extract_trend_data(region_item, 'lumbar')
                        if trend_info['prev_date']:
                            data['lumbar_prev_date'] = trend_info['prev_date']
                        if trend_info['prev_bmd']:
                            data['lumbar_prev_bmd'] = trend_info['prev_bmd']
                        if trend_info['change_percent']:
                            data['lumbar_change_percent'] = trend_info['change_percent']
                        if any(trend_info.values()):
                            print(f"  ✓ Trend Lumbar: Prior Date={trend_info['prev_date']}, Prior BMD={trend_info['prev_bmd']}, Change={trend_info['change_percent']}")
                
                # GE Lunar usa "L1-L4", "L2-L4", "L1-L3", etc. como nombre del container
                # Aceptar cualquier rango de vértebras lumbares (L#-L#)
                elif re.match(r'l[1-4]\s*-?\s*l[1-4]', region_lower):
                    if hasattr(region_item, 'ContentSequence'):
                        values = extract_region_values(region_item.ContentSequence)
                        normalized_lumbar_range = normalize_lumbar_range(region_name)
                        if normalized_lumbar_range:
                            current_priority = lumbar_range_priority(normalized_lumbar_range)
                            selected_priority = lumbar_range_priority(data.get('lumbar_vertebrae_range'))
                            if current_priority >= selected_priority:
                                data['lumbar_bmd'] = values['bmd']
                                data['lumbar_tscore'] = values['tscore']
                                data['lumbar_zscore'] = values['zscore']
                                data['lumbar_vertebrae_range'] = normalized_lumbar_range
                        print(f"  ✓ Lumbar {region_name}: BMD={values['bmd']}, T={values['tscore']}, Z={values['zscore']}")
        
        # ─────────────────────────────────────────────────────────────────
        # DUALFEMUR (Hip - Left and Right Neck + Total)
        # ─────────────────────────────────────────────────────────────────
        elif 'dualfemur' in container_lower or 'dual femur' in container_lower or 'femur' in container_lower:
            # Buscar sub-containers "Neck Left", "Neck Right", "Total Left", "Total Right"
            for region_item in container_item.ContentSequence:
                region_name = get_concept_name(region_item)
                if not region_name:
                    continue
                
                region_lower = region_name.lower()
                
                # Left Hip - Femoral Neck
                if 'neck left' in region_lower or ('left' in region_lower and 'neck' in region_lower):
                    if hasattr(region_item, 'ContentSequence'):
                        values = extract_region_values(region_item.ContentSequence)
                        data['left_hip_bmd'] = values['bmd']
                        data['left_hip_tscore'] = values['tscore']
                        data['left_hip_zscore'] = values['zscore']
                        data['_left_hip_from_neck'] = True
                        print(f"  ✓ Left Neck: BMD={values['bmd']}, T={values['tscore']}, Z={values['zscore']}")
                
                # Right Hip - Femoral Neck
                elif 'neck right' in region_lower or ('right' in region_lower and 'neck' in region_lower):
                    if hasattr(region_item, 'ContentSequence'):
                        values = extract_region_values(region_item.ContentSequence)
                        data['right_hip_bmd'] = values['bmd']
                        data['right_hip_tscore'] = values['tscore']
                        data['right_hip_zscore'] = values['zscore']
                        data['_right_hip_from_neck'] = True
                        print(f"  ✓ Right Neck: BMD={values['bmd']}, T={values['tscore']}, Z={values['zscore']}")
                
                # Left Hip - Total
                elif 'total left' in region_lower or ('left' in region_lower and 'total' in region_lower and 'mean' not in region_lower):
                    if hasattr(region_item, 'ContentSequence'):
                        values = extract_region_values(region_item.ContentSequence)
                        data['left_total_hip_bmd'] = values['bmd']
                        data['left_total_hip_tscore'] = values['tscore']
                        data['left_total_hip_zscore'] = values['zscore']
                        print(f"  ✓ Left Total Hip: BMD={values['bmd']}, T={values['tscore']}, Z={values['zscore']}")
                
                # Right Hip - Total
                elif 'total right' in region_lower or ('right' in region_lower and 'total' in region_lower and 'mean' not in region_lower):
                    if hasattr(region_item, 'ContentSequence'):
                        values = extract_region_values(region_item.ContentSequence)
                        data['right_total_hip_bmd'] = values['bmd']
                        data['right_total_hip_tscore'] = values['tscore']
                        data['right_total_hip_zscore'] = values['zscore']
                        print(f"  ✓ Right Total Hip: BMD={values['bmd']}, T={values['tscore']}, Z={values['zscore']}")
                
                # Trend Neck Left - prior específico de cuello femoral izquierdo
                elif 'trend' in region_lower and 'left' in region_lower and 'neck' in region_lower:
                    if hasattr(region_item, 'ContentSequence'):
                        trend_info = extract_trend_data(region_item, 'left_hip')
                        if trend_info['prev_date']:
                            data['left_hip_prev_date'] = trend_info['prev_date']
                        if trend_info['prev_bmd']:
                            data['left_hip_prev_bmd'] = trend_info['prev_bmd']
                        if trend_info['change_percent']:
                            data['left_hip_change_percent'] = trend_info['change_percent']
                        if any(trend_info.values()):
                            print(f"  ✓ Trend Neck Left: Prior Date={trend_info['prev_date']}, Prior BMD={trend_info['prev_bmd']}, Change={trend_info['change_percent']}")

                # Trend Neck Right - prior específico de cuello femoral derecho
                elif 'trend' in region_lower and 'right' in region_lower and 'neck' in region_lower:
                    if hasattr(region_item, 'ContentSequence'):
                        trend_info = extract_trend_data(region_item, 'right_hip')
                        if trend_info['prev_date']:
                            data['right_hip_prev_date'] = trend_info['prev_date']
                        if trend_info['prev_bmd']:
                            data['right_hip_prev_bmd'] = trend_info['prev_bmd']
                        if trend_info['change_percent']:
                            data['right_hip_change_percent'] = trend_info['change_percent']
                        if any(trend_info.values()):
                            print(f"  ✓ Trend Neck Right: Prior Date={trend_info['prev_date']}, Prior BMD={trend_info['prev_bmd']}, Change={trend_info['change_percent']}")

                # Trend Total/Mean - aplicar a ambos hips
                elif 'trend' in region_lower and ('total' in region_lower or 'mean' in region_lower):
                    if hasattr(region_item, 'ContentSequence'):
                        trend_info = extract_trend_data(region_item, 'hip')
                        if trend_info['prev_date'] or trend_info['prev_bmd'] or trend_info['change_percent']:
                            # Aplicar mismo trend a ambos hips
                            if trend_info['prev_date']:
                                data['left_hip_prev_date'] = trend_info['prev_date']
                                data['right_hip_prev_date'] = trend_info['prev_date']
                            if trend_info['prev_bmd']:
                                data['left_hip_prev_bmd'] = trend_info['prev_bmd']
                                data['right_hip_prev_bmd'] = trend_info['prev_bmd']
                            if trend_info['change_percent']:
                                data['left_hip_change_percent'] = trend_info['change_percent']
                                data['right_hip_change_percent'] = trend_info['change_percent']
                            print(f"  ✓ Trend Total Mean: Prior Date={trend_info['prev_date']}, Prior BMD={trend_info['prev_bmd']}, Change={trend_info['change_percent']}")
        
        # ─────────────────────────────────────────────────────────────────
        # FOREARM (Left and Right)
        # ─────────────────────────────────────────────────────────────────
        elif 'forearm' in container_lower or 'radius' in container_lower:
            for region_item in container_item.ContentSequence:
                region_name = get_concept_name(region_item)
                if not region_name:
                    continue
                
                region_lower = region_name.lower()
                
                if hasattr(region_item, 'ContentSequence'):
                    values = extract_region_values(region_item.ContentSequence)
                    
                    if 'left' in region_lower:
                        data['left_forearm_bmd'] = values['bmd']
                        data['left_forearm_tscore'] = values['tscore']
                        data['left_forearm_zscore'] = values['zscore']
                        print(f"  ✓ Left Forearm: BMD={values['bmd']}, T={values['tscore']}, Z={values['zscore']}")
                    
                    elif 'right' in region_lower:
                        data['right_forearm_bmd'] = values['bmd']
                        data['right_forearm_tscore'] = values['tscore']
                        data['right_forearm_zscore'] = values['zscore']
                        print(f"  ✓ Right Forearm: BMD={values['bmd']}, T={values['tscore']}, Z={values['zscore']}")
        
        # ─────────────────────────────────────────────────────────────────
        # FRAX (si existe en el SR)
        # ─────────────────────────────────────────────────────────────────
        elif 'frax' in container_lower:
            for item in container_item.ContentSequence:
                concept_name = get_concept_name(item)
                if not concept_name:
                    continue
                
                value_type = getattr(item, 'ValueType', None)
                concept_lower = concept_name.lower()
                
                if value_type == 'NUM':
                    value = get_numeric_value(item)
                    if value:
                        if 'major' in concept_lower:
                            if 'prior' in concept_lower:
                                data['major_fracture_risk_prior'] = float(value)
                            else:
                                data['major_fracture_risk'] = float(value)
                        elif 'hip' in concept_lower:
                            if 'prior' in concept_lower:
                                data['hip_fracture_risk_prior'] = float(value)
                            else:
                                data['hip_fracture_risk'] = float(value)
                
                elif value_type == 'TEXT':
                    text_value = get_text_value(item)
                    if text_value and 'who' in concept_lower:
                        data['who_classification'] = text_value
    
    def extract_trend_data(container_item, region_type):
        """
        Extrae datos de comparación con prior study de containers "Trend".
        
        Args:
            container_item: Container "Trend" con sub-containers de fechas
            region_type: 'lumbar', 'left_hip', o 'right_hip'
        
        Returns:
            dict con keys: 'prev_date', 'prev_bmd', 'change_percent'
        """
        trend_data = {
            'prev_date': None,
            'prev_bmd': None,
            'change_percent': None
        }
        
        if not hasattr(container_item, 'ContentSequence'):
            return trend_data
        
        # Buscar los containers con fechas (ej: "04/06/2026" y "07/30/2025")
        date_containers = []
        for item in container_item.ContentSequence:
            if getattr(item, 'ValueType', None) == 'CONTAINER':
                concept = get_concept_name(item)
                if concept and '/' in concept:  # Es una fecha como "04/06/2026"
                    date_containers.append(item)
        
        # Ordenar por fecha para identificar el más reciente y el prior
        if len(date_containers) >= 2:
            # El primer container suele ser el más reciente, el segundo el prior
            # Pero vamos a verificar extrayendo BMD de ambos
            
            # Procesar el container más reciente (primero) para obtener change_percent
            current_container = date_containers[0]
            current_date = get_concept_name(current_container)
            
            if hasattr(current_container, 'ContentSequence'):
                for item in current_container.ContentSequence:
                    concept = get_concept_name(item)
                    if not concept:
                        continue
                    
                    concept_lower = concept.lower()
                    value_type = getattr(item, 'ValueType', None)
                    
                    # Buscar PCHANGE_VS_PREVIOUS (cambio porcentual)
                    if 'pchange_vs_previous' in concept_lower or 'pchange vs previous' in concept_lower:
                        if value_type == 'CONTAINER' and hasattr(item, 'ContentSequence'):
                            for subitem in item.ContentSequence:
                                subconcept = get_concept_name(subitem)
                                if subconcept and 'bmd' in subconcept.lower():
                                    subvalue_type = getattr(subitem, 'ValueType', None)
                                    if subvalue_type == 'NUM':
                                        value = get_numeric_value(subitem)
                                        if value is not None:
                                            trend_data['change_percent'] = f"{value}%"
            
            # Procesar el container del prior (segundo) para obtener fecha y BMD
            prior_container = date_containers[1]
            prior_date = get_concept_name(prior_container)
            
            # Convertir fecha de MM/DD/YYYY a YYYY-MM-DD
            try:
                parts = prior_date.split('/')
                if len(parts) == 3:
                    month, day, year = parts
                    trend_data['prev_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                trend_data['prev_date'] = prior_date
            
            # Extraer BMD del prior
            if hasattr(prior_container, 'ContentSequence'):
                for item in prior_container.ContentSequence:
                    concept = get_concept_name(item)
                    if concept and concept.upper() == 'BMD':
                        value_type = getattr(item, 'ValueType', None)
                        if value_type == 'NUM':
                            value = get_numeric_value(item)
                            if value is not None:
                                trend_data['prev_bmd'] = float(value)
                                break
        
        return trend_data
    
    # ═════════════════════════════════════════════════════════════════════
    # RECORRER TODOS LOS CONTAINERS EN EL SR
    # ═════════════════════════════════════════════════════════════════════
    
    print("\n📊 Procesando ContentSequence del SR...")
    
    for item in ds.ContentSequence:
        value_type = getattr(item, 'ValueType', None)
        
        # Procesar solo containers
        if value_type == 'CONTAINER':
            process_container(item)
        
        # Buscar FRAX y WHO en nivel superior si no están en containers
        elif value_type == 'NUM' or value_type == 'TEXT':
            concept_name = get_concept_name(item)
            if concept_name:
                concept_lower = concept_name.lower()
                
                if 'frax' in concept_lower or 'fracture' in concept_lower:
                    if value_type == 'NUM':
                        value = get_numeric_value(item)
                        if value:
                            if 'major' in concept_lower:
                                data['major_fracture_risk'] = float(value)
                            elif 'hip' in concept_lower:
                                data['hip_fracture_risk'] = float(value)
                
                elif 'who' in concept_lower or 'classification' in concept_lower:
                    if value_type == 'TEXT':
                        text_value = get_text_value(item)
                        if text_value:
                            data['who_classification'] = text_value
        
        # Recursión en sub-containers
        if hasattr(item, 'ContentSequence'):
            for sub_item in item.ContentSequence:
                if getattr(sub_item, 'ValueType', None) == 'CONTAINER':
                    process_container(sub_item)
    
    return data


def insert_into_database(data):
    """
    Inserta o actualiza datos en PostgreSQL reports.bd
    Usa la misma lógica que Hologic para combinar datos de múltiples archivos
    """
    try:
        conn = psycopg2.connect(
            host="localhost",
            user="facundo",
            password="qii123",
            database="qii"
        )
        
        cursor = conn.cursor()
        
        mrn = data.get('patient_id', '')
        acc = data.get('accession_number', '')
        
        if not mrn or not acc:
            print("⚠️  Falta MRN o ACC - no se puede guardar en BD")
            return False
        
        # Verificar si ya existe
        cursor.execute("""
            SELECT guid, left_hip_bmd, right_hip_bmd, lumbar_bmd,
                   major_fracture_risk, "hip_fracture_risk│"
            FROM reports.bd 
            WHERE mrn = %s AND acc = %s
        """, (mrn, acc))
        
        existing = cursor.fetchone()
        
        # ═════════════════════════════════════════════════════════════════
        # BUSCAR ESTUDIO PREVIO PARA COMPARACIÓN
        # ═════════════════════════════════════════════════════════════════
        cursor.execute("""
            SELECT studydate, lumbar_bmd, left_hip_bmd, right_hip_bmd,
                   left_forearm_bmd, right_forearm_bmd
            FROM reports.bd
            WHERE mrn = %s AND acc != %s
            ORDER BY studydate DESC
            LIMIT 1
        """, (mrn, acc))
        
        prev_study = cursor.fetchone()
        
        if prev_study:
            prev_date, prev_lumbar_bmd, prev_left_hip_bmd, prev_right_hip_bmd, prev_left_forearm_bmd, prev_right_forearm_bmd = prev_study
            
            # Formatear fecha como MM/DD/YYYY
            prev_date_str = prev_date.strftime('%m/%d/%Y') if prev_date else None
            
            print(f"\n📊 Estudio previo encontrado:")
            print(f"   Fecha: {prev_date_str}")
            
            # Calcular cambios porcentuales si hay BMD actual y previo
            def calculate_change(current, previous):
                """Calcula cambio porcentual"""
                if current and previous:
                    try:
                        curr_val = float(current)
                        prev_val = float(previous)
                        if prev_val > 0:
                            change = ((curr_val - prev_val) / prev_val) * 100
                            return change
                    except (ValueError, TypeError):
                        pass
                return None
            
            # LUMBAR
            if data.get('lumbar_bmd') and prev_lumbar_bmd:
                change = calculate_change(data['lumbar_bmd'], prev_lumbar_bmd)
                if change is not None:
                    data['lumbar_prev_date'] = prev_date_str
                    data['lumbar_prev_bmd'] = float(prev_lumbar_bmd)
                    data['lumbar_change_percent'] = f"{change:+.1f}%"
                    print(f"   Lumbar: {prev_lumbar_bmd} → {data['lumbar_bmd']} ({change:+.1f}%)")
            
            # LEFT HIP
            if data.get('left_hip_bmd') and prev_left_hip_bmd:
                change = calculate_change(data['left_hip_bmd'], prev_left_hip_bmd)
                if change is not None:
                    data['left_hip_prev_date'] = prev_date_str
                    data['left_hip_prev_bmd'] = float(prev_left_hip_bmd)
                    data['left_hip_change_percent'] = f"{change:+.1f}%"
                    print(f"   Left Hip: {prev_left_hip_bmd} → {data['left_hip_bmd']} ({change:+.1f}%)")
            
            # RIGHT HIP
            if data.get('right_hip_bmd') and prev_right_hip_bmd:
                change = calculate_change(data['right_hip_bmd'], prev_right_hip_bmd)
                if change is not None:
                    data['right_hip_prev_date'] = prev_date_str
                    data['right_hip_prev_bmd'] = float(prev_right_hip_bmd)
                    data['right_hip_change_percent'] = f"{change:+.1f}%"
                    print(f"   Right Hip: {prev_right_hip_bmd} → {data['right_hip_bmd']} ({change:+.1f}%)")
            
            # LEFT FOREARM
            if data.get('left_forearm_bmd') and prev_left_forearm_bmd:
                change = calculate_change(data['left_forearm_bmd'], prev_left_forearm_bmd)
                if change is not None:
                    data['left_forearm_prev_date'] = prev_date_str
                    data['left_forearm_prev_bmd'] = float(prev_left_forearm_bmd)
                    data['left_forearm_change_percent'] = f"{change:+.1f}%"
                    print(f"   Left Forearm: {prev_left_forearm_bmd} → {data['left_forearm_bmd']} ({change:+.1f}%)")
            
            # RIGHT FOREARM
            if data.get('right_forearm_bmd') and prev_right_forearm_bmd:
                change = calculate_change(data['right_forearm_bmd'], prev_right_forearm_bmd)
                if change is not None:
                    data['right_forearm_prev_date'] = prev_date_str
                    data['right_forearm_prev_bmd'] = float(prev_right_forearm_bmd)
                    data['right_forearm_change_percent'] = f"{change:+.1f}%"
                    print(f"   Right Forearm: {prev_right_forearm_bmd} → {data['right_forearm_bmd']} ({change:+.1f}%)")
        
        # Convertir valores numéricos (float) a strings para compatibilidad con generate_report
        # La función generate_report de Hologic espera strings, no floats
        # Crear una copia del diccionario para no afectar los valores que van a la BD
        data_for_report = data.copy()
        numeric_fields = [
            'lumbar_bmd', 'lumbar_tscore', 'lumbar_zscore',
            'left_hip_bmd', 'left_hip_tscore', 'left_hip_zscore',
            'right_hip_bmd', 'right_hip_tscore', 'right_hip_zscore',
            'left_total_hip_bmd', 'left_total_hip_tscore', 'left_total_hip_zscore',
            'right_total_hip_bmd', 'right_total_hip_tscore', 'right_total_hip_zscore',
            'left_forearm_bmd', 'left_forearm_tscore', 'left_forearm_zscore',
            'right_forearm_bmd', 'right_forearm_tscore', 'right_forearm_zscore',
            'major_fracture_risk', 'hip_fracture_risk',
            'major_fracture_risk_prior', 'hip_fracture_risk_prior'
        ]
        
        for field in numeric_fields:
            if field in data_for_report and data_for_report[field] is not None:
                data_for_report[field] = str(data_for_report[field])

        # GE: en el texto del reporte mostrar cadera solo como femoral neck
        data_for_report['femoral_neck_only'] = True
        
        # Generar reporte
        report_text = generate_report(data_for_report)
        
        # Guardar reporte en archivo
        report_path = f"/home/ubuntu/DICOMReceiver/reports/bd_report_{mrn}_{acc}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"    ✓ Reporte guardado: {report_path}")
        
        if existing:
            # ACTUALIZAR - combinar datos
            print(f"\n📝 Registro existente encontrado - Actualizando")
            
            # Preparar datos para UPDATE (solo campos no nulos y que existen en la tabla)
            updates = []
            params = []
            
            # Campos válidos en la tabla reports.bd
            valid_fields = {
                'pat_name', 'lumbar_bmd', 'lumbar_tscore', 'lumbar_zscore',
                'left_hip_bmd', 'left_hip_tscore', 'left_hip_zscore',
                'right_hip_bmd', 'right_hip_tscore', 'right_hip_zscore',
                'left_forearm_bmd', 'left_forearm_tscore', 'left_forearm_zscore',
                'right_forearm_bmd', 'right_forearm_tscore', 'right_forearm_zscore',
                'major_fracture_risk', 'hip_fracture_risk', 'who_classification',
                'major_fracture_risk_prior', 'hip_fracture_risk_prior',
                'lumbar_prev_date', 'lumbar_prev_bmd', 'lumbar_change_percent',
                'left_hip_prev_date', 'left_hip_prev_bmd', 'left_hip_change_percent',
                'right_hip_prev_date', 'right_hip_prev_bmd', 'right_hip_change_percent'
            }
            
            for key, value in data.items():
                if value and key not in ['patient_id', 'accession_number'] and key in valid_fields:
                    # Mapear nombres de campos al schema de BD
                    db_field = key
                    if key == 'hip_fracture_risk':
                        db_field = 'hip_fracture_risk│'
                    elif key == 'who_classification':
                        db_field = 'WHO_Classification'
                    
                    updates.append(f'"{db_field}" = %s' if '│' in db_field or db_field.startswith('WHO') else f'{db_field} = %s')
                    params.append(value)
            
            # Agregar reporte
            updates.append('report = %s')
            params.append(report_text)
            
            # Agregar condiciones WHERE
            params.extend([mrn, acc])
            
            update_sql = f"""
                UPDATE reports.bd 
                SET {', '.join(updates)}
                WHERE mrn = %s AND acc = %s
            """
            
            cursor.execute(update_sql, params)
            conn.commit()
            
            print(f"✅ Registro ACTUALIZADO")
            
        else:
            # INSERTAR nuevo registro
            print(f"\n📝 Nuevo registro - Insertando en base de datos")
            
            guid = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO reports.bd (
                    guid, mrn, acc, pat_name, report,
                    lumbar_bmd, lumbar_tscore, lumbar_zscore,
                    left_hip_bmd, left_hip_tscore, left_hip_zscore,
                    right_hip_bmd, right_hip_tscore, right_hip_zscore,
                    left_forearm_bmd, left_forearm_tscore, left_forearm_zscore,
                    right_forearm_bmd, right_forearm_tscore, right_forearm_zscore,
                    major_fracture_risk, "hip_fracture_risk│", "WHO_Classification",
                    major_fracture_risk_prior, hip_fracture_risk_prior,
                    lumbar_prev_date, lumbar_prev_bmd, lumbar_change_percent,
                    left_hip_prev_date, left_hip_prev_bmd, left_hip_change_percent,
                    right_hip_prev_date, right_hip_prev_bmd, right_hip_change_percent,
                    receivedon, studydate
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """, (
                guid, mrn, acc, data.get('pat_name'), report_text,
                data.get('lumbar_bmd'), data.get('lumbar_tscore'), data.get('lumbar_zscore'),
                data.get('left_hip_bmd'), data.get('left_hip_tscore'), data.get('left_hip_zscore'),
                data.get('right_hip_bmd'), data.get('right_hip_tscore'), data.get('right_hip_zscore'),
                data.get('left_forearm_bmd'), data.get('left_forearm_tscore'), data.get('left_forearm_zscore'),
                data.get('right_forearm_bmd'), data.get('right_forearm_tscore'), data.get('right_forearm_zscore'),
                data.get('major_fracture_risk'), data.get('hip_fracture_risk'), data.get('who_classification'),
                data.get('major_fracture_risk_prior'), data.get('hip_fracture_risk_prior'),
                data.get('lumbar_prev_date'), data.get('lumbar_prev_bmd'), data.get('lumbar_change_percent'),
                data.get('left_hip_prev_date'), data.get('left_hip_prev_bmd'), data.get('left_hip_change_percent'),
                data.get('right_hip_prev_date'), data.get('right_hip_prev_bmd'), data.get('right_hip_change_percent')
            ))
            # NOTE: Total hip fields (left_total_hip_*, right_total_hip_*) are extracted and included
            # in the report text, but not stored separately in the database. If needed, add these columns:
            # left_total_hip_bmd, left_total_hip_tscore, left_total_hip_zscore,
            # right_total_hip_bmd, right_total_hip_tscore, right_total_hip_zscore
            
            conn.commit()
            
            print(f"✅ Datos insertados en PostgreSQL")
            print(f"   └─ GUID: {guid}")
            print(f"   └─ MRN: {mrn}")
            print(f"   └─ ACC: {acc}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error en base de datos: {e}")
        import traceback
        traceback.print_exc()
        return False


def main(patient_id):
    """
    Procesa estudios BD de GE Lunar desde DICOM SR
    
    Args:
        patient_id: Patient MRN/ID
    """
    print(f"\n{'='*80}")
    print(f"BD EXTRACTION - GE Healthcare Lunar (DICOM SR)")
    print(f"{'='*80}")
    print(f"Patient ID: {patient_id}\n")
    
    # Buscar archivos DICOM del paciente
    dicom_base = Path("/home/ubuntu/DICOMReceiver/dicom_storage")
    patient_path = dicom_base / patient_id
    
    if not patient_path.exists():
        print(f"✗ No se encontró directorio del paciente: {patient_path}")
        return False
    
    # Buscar archivos DICOM
    dicom_files = []
    for study_dir in patient_path.iterdir():
        if study_dir.is_dir():
            for dcm_file in study_dir.glob("*"):
                if dcm_file.is_file() and not dcm_file.suffix in ['.xml', '.jpg', '.jpeg', '.txt']:
                    dicom_files.append(dcm_file)
    
    if not dicom_files:
        print(f"✗ No se encontraron archivos DICOM")
        return False
    
    print(f"✓ Encontrados {len(dicom_files)} archivo(s) DICOM")
    
    # Acumular datos de todos los SR files
    accumulated_data = None
    sr_files_found = 0
    
    for dcm_file in dicom_files:
        print(f"\n{'─'*80}")
        print(f"Procesando: {dcm_file.name}")
        print(f"{'─'*80}")
        
        try:
            # Leer DICOM
            ds = pydicom.dcmread(dcm_file, force=True)
            
            # Verificar que sea un Structured Report
            modality = getattr(ds, 'Modality', None)
            if modality != 'SR':
                print(f"⚠️  No es un Structured Report (Modality: {modality}) - saltando")
                continue
            
            print(f"✓ DICOM SR detectado")
            sr_files_found += 1
            
            # Extraer de AMBAS fuentes y combinarlas inteligentemente
            # 1. Extraer de ContentSequence (BMD values correctos)
            data_cs = extract_from_sr(ds)
            
            # 2. Extraer de XML (T-scores, Z-scores, priors)
            data_xml = extract_from_xml_imagecomments(ds)
            
            # 3. Combinar: priorizar BMDs de ContentSequence, T/Z/priors de XML
            if data_xml is not None and data_cs is not None:
                # Empezar con datos de ContentSequence (BMDs correctos)
                data = data_cs.copy()
                
                # Sobrescribir solo T-scores, Z-scores, y datos de prior del XML
                # NO sobrescribir BMDs (son más precisos en ContentSequence)
                priority_xml_keys = [
                    'lumbar_tscore', 'lumbar_zscore',
                    'lumbar_prev_date', 'lumbar_prev_bmd', 'lumbar_change_percent',
                    # Requerimiento: left/right hip deben venir solo de Femoral Neck en ContentSequence
                    # 'left_hip_tscore', 'left_hip_zscore',
                    'left_hip_prev_date', 'left_hip_prev_bmd', 'left_hip_change_percent',
                    # Requerimiento: left/right hip deben venir solo de Femoral Neck en ContentSequence
                    # 'right_hip_tscore', 'right_hip_zscore',
                    'right_hip_prev_date', 'right_hip_prev_bmd', 'right_hip_change_percent'
                ]
                
                for key in priority_xml_keys:
                    if key in data_xml and data_xml[key] is not None:
                        data[key] = data_xml[key]

                # Si el XML trae Neck válido (ej. SCAN="Left Femur" + ROI="Neck")
                # y ContentSequence no lo trae, usar esos valores de cadera.
                if data_xml.get('_left_hip_from_neck'):
                    for key in ('left_hip_bmd', 'left_hip_tscore', 'left_hip_zscore'):
                        if data.get(key) is None and data_xml.get(key) is not None:
                            data[key] = data_xml[key]
                    data['_left_hip_from_neck'] = True

                if data_xml.get('_right_hip_from_neck'):
                    for key in ('right_hip_bmd', 'right_hip_tscore', 'right_hip_zscore'):
                        if data.get(key) is None and data_xml.get(key) is not None:
                            data[key] = data_xml[key]
                    data['_right_hip_from_neck'] = True

                # Completar cualquier campo faltante con XML.
                # Esto permite recuperar regiones que pueden no venir en ContentSequence
                # (ej. forearm/radius u otras variantes de GE), sin perder BMDs de CS cuando existen.
                for key, value in data_xml.items():
                    if key not in data or data[key] is None:
                        if value is not None:
                            # Requerimiento: evitar completar priors de cadera desde XML.
                            # data[key] = value
                            if key in {
                                'left_hip_bmd', 'left_hip_tscore', 'left_hip_zscore',
                                'right_hip_bmd', 'right_hip_tscore', 'right_hip_zscore',
                                # Priors de cadera se toman por extracción prioritaria o fallback BD,
                                # no por relleno indiscriminado.
                                'left_hip_prev_date', 'left_hip_prev_bmd', 'left_hip_change_percent',
                                'right_hip_prev_date', 'right_hip_prev_bmd', 'right_hip_change_percent'
                            }:
                                continue
                            data[key] = value

                # Regla final: cadera solo si vino de Neck Left/Right desde alguna fuente confiable
                left_from_neck = data_cs.get('_left_hip_from_neck') or (data_xml and data_xml.get('_left_hip_from_neck'))
                right_from_neck = data_cs.get('_right_hip_from_neck') or (data_xml and data_xml.get('_right_hip_from_neck'))

                if not left_from_neck:
                    data['left_hip_bmd'] = None
                    data['left_hip_tscore'] = None
                    data['left_hip_zscore'] = None
                if not right_from_neck:
                    data['right_hip_bmd'] = None
                    data['right_hip_tscore'] = None
                    data['right_hip_zscore'] = None
                
                print(f"✓ Datos combinados: ContentSequence (BMD) + XML (T/Z/priors)")
                
            elif data_xml is not None:
                data = data_xml
                print(f"✓ Datos extraídos desde XML ImageComments")
            elif data_cs is not None:
                data = data_cs
                print(f"✓ Datos extraídos desde ContentSequence")
            else:
                print(f"⚠️  No se pudieron extraer datos")
                continue
            
            print(f"✓ Campos extraídos: {len([v for v in data.values() if v])}")
            
            if data.get('lumbar_bmd'):
                print(f"  Lumbar BMD: {data.get('lumbar_bmd')}")
            if data.get('left_hip_bmd'):
                print(f"  Left Hip BMD: {data.get('left_hip_bmd')}")
            if data.get('right_hip_bmd'):
                print(f"  Right Hip BMD: {data.get('right_hip_bmd')}")
            if data.get('major_fracture_risk'):
                print(f"  Major FRAX: {data.get('major_fracture_risk')}%")
            if data.get('hip_fracture_risk'):
                print(f"  Hip FRAX: {data.get('hip_fracture_risk')}%")
            
            # Acumular datos (algunos SR tienen solo lumbar, otros solo hip, etc.)
            if accumulated_data is None:
                accumulated_data = data
            else:
                # Combinar datos - valores nuevos sobrescriben solo si no son None
                for key, value in data.items():
                    if value is None:
                        continue

                    if key in {'lumbar_bmd', 'lumbar_tscore', 'lumbar_zscore', 'lumbar_vertebrae_range'}:
                        new_range = data.get('lumbar_vertebrae_range')
                        current_range = accumulated_data.get('lumbar_vertebrae_range')
                        if lumbar_range_priority(new_range) >= lumbar_range_priority(current_range):
                            accumulated_data[key] = value
                    else:
                        accumulated_data[key] = value
        
        except Exception as e:
            print(f"✗ Error procesando archivo: {e}")
            import traceback
            traceback.print_exc()
    
    # Guardar datos acumulados en base de datos (una sola vez)
    processed = 0
    if accumulated_data and sr_files_found > 0:
        print(f"\n{'═'*80}")
        print(f"RESUMEN: Procesados {sr_files_found} archivos SR")
        print(f"{'═'*80}")
        print(f"  MRN: {accumulated_data.get('patient_id')}")
        print(f"  ACC: {accumulated_data.get('accession_number')}")
        if accumulated_data.get('lumbar_bmd'):
            print(f"  Lumbar BMD: {accumulated_data.get('lumbar_bmd')}")
        if accumulated_data.get('left_hip_bmd'):
            print(f"  Left Hip BMD: {accumulated_data.get('left_hip_bmd')}")
        if accumulated_data.get('right_hip_bmd'):
            print(f"  Right Hip BMD: {accumulated_data.get('right_hip_bmd')}")
        
        print(f"\n📊 Guardando en PostgreSQL...")
        if insert_into_database(accumulated_data):
            print(f"✅ Datos guardados en reports.bd")
            processed = 1
        else:
            print(f"⚠️  Error guardando en BD")
    
    print(f"\n{'='*80}")
    print(f"Completado: {processed}/{len(dicom_files)} archivos procesados")
    print(f"{'='*80}\n")
    
    return processed > 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bd_extract_ge.py <patient_id>")
        sys.exit(1)
    
    patient_id = sys.argv[1]
    success = main(patient_id)
    
    sys.exit(0 if success else 1)
