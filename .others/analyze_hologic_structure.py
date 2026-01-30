#!/usr/bin/env python3
"""
Análisis de estructura DICOM de equipos HOLOGIC
Verifica si todos los modelos tienen el tag XML (0x0019, 0x1000) con datos útiles
"""

import os
import pydicom
import re
from collections import defaultdict
from pathlib import Path

def analyze_hologic_xml_structure(base_path="/home/ubuntu/DICOMReceiver/dicom_storage"):
    """Analiza archivos DICOM de HOLOGIC para verificar estructura XML"""
    
    print(f"🔍 Analizando estructura de archivos DICOM HOLOGIC\n")
    print("=" * 100)
    
    # Agrupar por modelo
    models_analysis = defaultdict(lambda: {
        'total_files': 0,
        'has_xml_tag': 0,
        'xml_with_data': 0,
        'xml_samples': [],
        'no_xml_samples': []
    })
    
    # Recorrer todos los subdirectorios
    for patient_dir in Path(base_path).iterdir():
        if not patient_dir.is_dir():
            continue
            
        for study_dir in patient_dir.iterdir():
            if not study_dir.is_dir():
                continue
                
            # Buscar archivos DICOM
            for dicom_file in study_dir.iterdir():
                if dicom_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    continue
                    
                try:
                    ds = pydicom.dcmread(str(dicom_file), force=True)
                    
                    manufacturer = getattr(ds, 'Manufacturer', 'Unknown').strip()
                    model = getattr(ds, 'ManufacturerModelName', 'Unknown').strip()
                    modality = getattr(ds, 'Modality', 'Unknown').strip()
                    
                    # Solo analizar HOLOGIC BD
                    if modality != 'BD' or 'HOLOGIC' not in manufacturer.upper():
                        continue
                    
                    # Normalizar nombre del modelo (quitar espacios extra)
                    model_key = ' '.join(model.split())
                    
                    models_analysis[model_key]['total_files'] += 1
                    
                    # Verificar tag XML (0x0019, 0x1000)
                    has_xml = (0x0019, 0x1000) in ds
                    
                    if has_xml:
                        models_analysis[model_key]['has_xml_tag'] += 1
                        
                        # Intentar decodificar XML
                        try:
                            xml_data = ds[0x0019, 0x1000].value
                            if isinstance(xml_data, bytes):
                                xml_text = xml_data.decode('utf-8', errors='ignore')
                            else:
                                xml_text = str(xml_data)
                            
                            # Verificar si tiene datos útiles (ResultsTable, ScanMode, etc.)
                            has_useful_data = False
                            if 'ResultsTable' in xml_text or 'ScanMode' in xml_text or 'Report' in xml_text:
                                has_useful_data = True
                                models_analysis[model_key]['xml_with_data'] += 1
                            
                            # Guardar muestra del primer archivo de cada modelo
                            if len(models_analysis[model_key]['xml_samples']) < 2:
                                # Extraer información clave
                                scan_mode = re.search(r'ScanMode\s*=\s*"([^"]*)"', xml_text)
                                body_part = getattr(ds, 'BodyPartExamined', 'N/A')
                                patient_id = getattr(ds, 'PatientID', 'N/A')
                                
                                models_analysis[model_key]['xml_samples'].append({
                                    'file': str(dicom_file.relative_to(base_path)),
                                    'patient_id': patient_id,
                                    'body_part': body_part,
                                    'scan_mode': scan_mode.group(1) if scan_mode else 'N/A',
                                    'has_useful_data': has_useful_data,
                                    'xml_length': len(xml_text)
                                })
                        except Exception as xml_err:
                            pass
                    else:
                        # No tiene XML tag
                        if len(models_analysis[model_key]['no_xml_samples']) < 2:
                            patient_id = getattr(ds, 'PatientID', 'N/A')
                            body_part = getattr(ds, 'BodyPartExamined', 'N/A')
                            
                            models_analysis[model_key]['no_xml_samples'].append({
                                'file': str(dicom_file.relative_to(base_path)),
                                'patient_id': patient_id,
                                'body_part': body_part
                            })
                    
                except Exception as e:
                    pass
    
    # Generar reporte
    print("\n📊 RESUMEN POR MODELO HOLOGIC")
    print("=" * 100)
    
    total_hologic_files = 0
    total_with_xml = 0
    total_with_useful_data = 0
    
    for model, stats in sorted(models_analysis.items()):
        total_hologic_files += stats['total_files']
        total_with_xml += stats['has_xml_tag']
        total_with_useful_data += stats['xml_with_data']
        
        xml_percentage = (stats['has_xml_tag'] / stats['total_files'] * 100) if stats['total_files'] > 0 else 0
        data_percentage = (stats['xml_with_data'] / stats['total_files'] * 100) if stats['total_files'] > 0 else 0
        
        print(f"\n🔧 {model}")
        print(f"   Total archivos: {stats['total_files']}")
        print(f"   Con tag XML (0x0019, 0x1000): {stats['has_xml_tag']} ({xml_percentage:.1f}%)")
        print(f"   Con datos útiles en XML: {stats['xml_with_data']} ({data_percentage:.1f}%)")
        
        # Mostrar muestras con XML
        if stats['xml_samples']:
            print(f"\n   ✅ Ejemplos CON XML:")
            for sample in stats['xml_samples'][:2]:
                print(f"      • Paciente: {sample['patient_id']} | BodyPart: {sample['body_part']} | ScanMode: {sample['scan_mode']}")
                print(f"        XML length: {sample['xml_length']:,} chars | Útil: {sample['has_useful_data']}")
                print(f"        Archivo: {sample['file'][:80]}...")
        
        # Mostrar muestras sin XML
        if stats['no_xml_samples']:
            print(f"\n   ❌ Ejemplos SIN XML:")
            for sample in stats['no_xml_samples'][:2]:
                print(f"      • Paciente: {sample['patient_id']} | BodyPart: {sample['body_part']}")
                print(f"        Archivo: {sample['file'][:80]}...")
    
    # Resumen general
    print("\n" + "=" * 100)
    print("📋 RESUMEN GENERAL HOLOGIC")
    print("=" * 100)
    print(f"Total archivos HOLOGIC BD: {total_hologic_files}")
    print(f"Archivos con tag XML (0x0019, 0x1000): {total_with_xml} ({total_with_xml/total_hologic_files*100:.1f}%)")
    print(f"Archivos con datos útiles en XML: {total_with_useful_data} ({total_with_useful_data/total_hologic_files*100:.1f}%)")
    
    if total_hologic_files == total_with_xml:
        print("\n✅ TODOS los archivos HOLOGIC tienen el tag XML")
    else:
        missing = total_hologic_files - total_with_xml
        print(f"\n⚠️  {missing} archivos HOLOGIC NO tienen tag XML ({missing/total_hologic_files*100:.1f}%)")
    
    if total_with_xml == total_with_useful_data:
        print("✅ TODOS los archivos con XML contienen datos útiles")
    else:
        empty = total_with_xml - total_with_useful_data
        print(f"⚠️  {empty} archivos tienen XML pero SIN datos útiles")
    
    print("=" * 100)
    
    return models_analysis

if __name__ == "__main__":
    results = analyze_hologic_xml_structure()
