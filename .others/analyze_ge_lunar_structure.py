#!/usr/bin/env python3
"""
Análisis de estructura DICOM de equipos GE Healthcare Lunar
Verifica si tienen tags privados con XML o datos útiles
"""

import os
import pydicom
import re
from collections import defaultdict
from pathlib import Path

def analyze_ge_lunar_structure(base_path="/home/ubuntu/DICOMReceiver/dicom_storage"):
    """Analiza archivos DICOM de GE Lunar para verificar estructura de datos"""
    
    print(f"🔍 Analizando estructura de archivos DICOM GE Healthcare Lunar\n")
    print("=" * 100)
    
    # Agrupar por modelo
    models_analysis = defaultdict(lambda: {
        'total_files': 0,
        'samples': []
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
                    
                    # Solo analizar GE Healthcare BD
                    if modality != 'BD' or 'GE' not in manufacturer.upper():
                        continue
                    
                    models_analysis[model]['total_files'] += 1
                    
                    # Guardar muestra de primeros archivos
                    if len(models_analysis[model]['samples']) < 3:
                        patient_id = getattr(ds, 'PatientID', 'N/A')
                        body_part = getattr(ds, 'BodyPartExamined', 'N/A')
                        
                        # Buscar tags privados potenciales de GE
                        private_tags = {}
                        
                        # Tags privados comunes de GE (0x0009, 0x0011, 0x0019, 0x0029, etc.)
                        for tag in ds.keys():
                            group = tag.group
                            # Tags privados tienen grupo impar
                            if group % 2 == 1:
                                try:
                                    value = ds[tag].value
                                    # Solo guardar si tiene contenido interesante
                                    if value is not None:
                                        value_str = str(value)[:200] if not isinstance(value, bytes) else f"<bytes: {len(value)} bytes>"
                                        
                                        # Si son bytes grandes, verificar si es XML o texto
                                        if isinstance(value, bytes) and len(value) > 100:
                                            try:
                                                decoded = value.decode('utf-8', errors='ignore')
                                                if '<' in decoded and '>' in decoded:
                                                    value_str = f"XML/HTML detected: {len(value)} bytes"
                                                elif 'Report' in decoded or 'Scan' in decoded:
                                                    value_str = f"Text data: {len(value)} bytes - {decoded[:100]}"
                                            except:
                                                pass
                                        
                                        private_tags[str(tag)] = value_str
                                except:
                                    pass
                        
                        # Verificar tags específicos
                        has_hologic_xml = (0x0019, 0x1000) in ds
                        has_bmp = (0x0029, 0x1000) in ds
                        
                        # Tags estándar de imagen
                        sop_class = getattr(ds, 'SOPClassUID', 'N/A')
                        
                        models_analysis[model]['samples'].append({
                            'file': str(dicom_file.relative_to(base_path)),
                            'patient_id': patient_id,
                            'body_part': body_part,
                            'sop_class': sop_class,
                            'has_hologic_xml': has_hologic_xml,
                            'has_bmp': has_bmp,
                            'private_tags': private_tags,
                            'total_tags': len(ds.keys()),
                            'private_tags_count': len(private_tags)
                        })
                    
                except Exception as e:
                    pass
    
    # Generar reporte
    print("\n📊 RESUMEN POR MODELO GE LUNAR")
    print("=" * 100)
    
    total_ge_files = 0
    
    for model, stats in sorted(models_analysis.items()):
        total_ge_files += stats['total_files']
        
        print(f"\n🔧 {model}")
        print(f"   Total archivos: {stats['total_files']}")
        
        # Mostrar muestras
        if stats['samples']:
            print(f"\n   📁 Análisis de muestras:")
            for i, sample in enumerate(stats['samples'], 1):
                print(f"\n   --- Muestra {i} ---")
                print(f"      Paciente: {sample['patient_id']} | BodyPart: {sample['body_part']}")
                print(f"      SOP Class: {sample['sop_class']}")
                print(f"      Total de tags DICOM: {sample['total_tags']}")
                print(f"      Tags privados encontrados: {sample['private_tags_count']}")
                print(f"      Tiene tag HOLOGIC XML (0x0019, 0x1000): {sample['has_hologic_xml']}")
                print(f"      Tiene tag BMP (0x0029, 0x1000): {sample['has_bmp']}")
                
                if sample['private_tags']:
                    print(f"\n      🔑 Tags privados detectados:")
                    for tag, value in sorted(sample['private_tags'].items())[:10]:  # Max 10
                        print(f"         {tag}: {value}")
                    if len(sample['private_tags']) > 10:
                        print(f"         ... y {len(sample['private_tags']) - 10} más")
                else:
                    print(f"      ❌ No se encontraron tags privados con datos útiles")
                
                print(f"      Archivo: .../{sample['file'].split('/')[-1][:70]}")
    
    # Resumen general
    print("\n" + "=" * 100)
    print("📋 RESUMEN GENERAL GE LUNAR")
    print("=" * 100)
    print(f"Total archivos GE Healthcare BD: {total_ge_files}")
    print(f"Modelos únicos: {len(models_analysis)}")
    
    print("\n" + "=" * 100)
    print("🔍 CONCLUSIÓN")
    print("=" * 100)
    
    # Verificar si alguno tiene el tag XML de HOLOGIC
    has_any_hologic_xml = any(
        sample['has_hologic_xml'] 
        for stats in models_analysis.values() 
        for sample in stats['samples']
    )
    
    if has_any_hologic_xml:
        print("✅ Algunos archivos GE Lunar TIENEN el tag XML (0x0019, 0x1000)")
    else:
        print("❌ Los archivos GE Lunar NO tienen el tag XML (0x0019, 0x1000) de HOLOGIC")
    
    # Verificar si tienen otros tags privados útiles
    has_useful_private = any(
        len(sample['private_tags']) > 0
        for stats in models_analysis.values() 
        for sample in stats['samples']
    )
    
    if has_useful_private:
        print("✅ Los archivos GE Lunar tienen tags privados propietarios")
        print("   → Investigar si contienen datos de densitometría")
    else:
        print("❌ No se encontraron tags privados con información útil")
    
    print("=" * 100)
    
    return models_analysis

if __name__ == "__main__":
    results = analyze_ge_lunar_structure()
