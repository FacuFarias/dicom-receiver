#!/usr/bin/env python3
"""
Análisis de fabricantes y modelos de equipos DICOM BD
Escanea todos los archivos DICOM recibidos y genera estadísticas
"""

import os
import pydicom
from collections import Counter, defaultdict
from pathlib import Path

def analyze_dicom_manufacturers(base_path="/home/ubuntu/DICOMReceiver/dicom_storage"):
    """Analiza todos los archivos DICOM para identificar fabricantes y modelos"""
    
    manufacturers = []
    models = []
    manufacturer_model_pairs = []
    modalities = []
    errors = []
    
    print(f"🔍 Escaneando archivos DICOM en: {base_path}\n")
    
    # Recorrer todos los subdirectorios
    for patient_dir in Path(base_path).iterdir():
        if not patient_dir.is_dir():
            continue
            
        for study_dir in patient_dir.iterdir():
            if not study_dir.is_dir():
                continue
                
            # Buscar archivos DICOM (sin extensión .jpg)
            for dicom_file in study_dir.iterdir():
                if dicom_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    continue
                    
                try:
                    ds = pydicom.dcmread(str(dicom_file), force=True)
                    
                    # Extraer información
                    manufacturer = getattr(ds, 'Manufacturer', 'Unknown').strip()
                    model = getattr(ds, 'ManufacturerModelName', 'Unknown').strip()
                    modality = getattr(ds, 'Modality', 'Unknown').strip()
                    
                    # Solo analizar archivos de Bone Density
                    if modality == 'BD':
                        manufacturers.append(manufacturer)
                        models.append(model)
                        manufacturer_model_pairs.append(f"{manufacturer} - {model}")
                        modalities.append(modality)
                    
                except Exception as e:
                    errors.append(str(dicom_file))
    
    # Generar estadísticas
    total_files = len(manufacturers)
    
    print("=" * 80)
    print("📊 ANÁLISIS DE EQUIPOS DICOM BONE DENSITY (BD)")
    print("=" * 80)
    print(f"\n✅ Total de archivos BD analizados: {total_files}")
    print(f"❌ Archivos con errores: {len(errors)}\n")
    
    # Estadísticas de fabricantes
    print("=" * 80)
    print("🏭 FABRICANTES (Manufacturer)")
    print("=" * 80)
    manufacturer_counts = Counter(manufacturers)
    for manufacturer, count in manufacturer_counts.most_common():
        percentage = (count / total_files) * 100
        print(f"{manufacturer:40} | {count:5} archivos | {percentage:6.2f}%")
    
    # Estadísticas de modelos
    print("\n" + "=" * 80)
    print("🔧 MODELOS (ManufacturerModelName)")
    print("=" * 80)
    model_counts = Counter(models)
    for model, count in model_counts.most_common():
        percentage = (count / total_files) * 100
        print(f"{model:40} | {count:5} archivos | {percentage:6.2f}%")
    
    # Estadísticas de combinación fabricante-modelo
    print("\n" + "=" * 80)
    print("🏷️  COMBINACIÓN FABRICANTE - MODELO")
    print("=" * 80)
    pair_counts = Counter(manufacturer_model_pairs)
    for pair, count in pair_counts.most_common():
        percentage = (count / total_files) * 100
        print(f"{pair:60} | {count:5} archivos | {percentage:6.2f}%")
    
    # Información adicional
    print("\n" + "=" * 80)
    print("📋 RESUMEN")
    print("=" * 80)
    print(f"Fabricantes únicos: {len(manufacturer_counts)}")
    print(f"Modelos únicos: {len(model_counts)}")
    print(f"Combinaciones únicas: {len(pair_counts)}")
    
    if errors:
        print("\n" + "=" * 80)
        print(f"⚠️  ARCHIVOS CON ERRORES ({len(errors)} archivos)")
        print("=" * 80)
        for error_file in errors[:10]:  # Mostrar solo los primeros 10
            print(f"  - {error_file}")
        if len(errors) > 10:
            print(f"  ... y {len(errors) - 10} más")
    
    print("\n" + "=" * 80)
    
    return {
        'manufacturers': manufacturer_counts,
        'models': model_counts,
        'pairs': pair_counts,
        'total': total_files,
        'errors': len(errors)
    }

if __name__ == "__main__":
    results = analyze_dicom_manufacturers()
