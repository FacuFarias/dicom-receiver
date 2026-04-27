#!/usr/bin/env python3
"""
Analiza logs de BD processing para generar estadísticas de fuentes de datos FRAX
(XML vs OCR)

Ejecutar: python3 analyze_frax_sources.py
"""

from pathlib import Path
from datetime import datetime
import re
from collections import defaultdict

def analyze_frax_logs():
    """Analiza logs para obtener estadísticas de fuentes FRAX"""
    
    log_file = Path("/home/ubuntu/DICOMReceiver/logs/bd_processing.log")
    
    if not log_file.exists():
        print(f"❌ Archivo de log no encontrado: {log_file}")
        return
    
    # Contadores
    stats = {
        'major_frax_xml': 0,
        'major_frax_ocr': 0,
        'major_frax_ocr_failed': 0,
        'major_frax_no_jpeg': 0,
        'hip_frax_xml': 0,
        'total_patients': set()
    }
    
    # Detalles por paciente
    patient_details = defaultdict(lambda: {
        'major_frax_source': None,
        'hip_frax_source': None,
        'timestamp': None
    })
    
    print("="*80)
    print("ANÁLISIS DE FUENTES DE DATOS FRAX - Reportes BD")
    print("="*80)
    print(f"Analizando: {log_file}")
    print(f"Tamaño: {log_file.stat().st_size / 1024:.1f} KB\n")
    
    # Leer log
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            # Formato: [timestamp] [Patient: ID] [STEP] [STATUS] details
            match = re.match(r'\[(.*?)\] \[Patient: (.*?)\] \[FRAX_SOURCE\] \[(.*?)\] (.*)', line)
            if match:
                timestamp, patient_id, status, details = match.groups()
                
                stats['total_patients'].add(patient_id)
                patient_details[patient_id]['timestamp'] = timestamp
                
                details_lower = details.lower()
                
                # Major FRAX desde XML
                if 'major frax' in details_lower and 'xml' in details_lower:
                    stats['major_frax_xml'] += 1
                    patient_details[patient_id]['major_frax_source'] = 'XML'
                
                # Major FRAX desde OCR
                elif 'major frax' in details_lower and 'ocr' in details_lower and 'fallback' in details_lower:
                    stats['major_frax_ocr'] += 1
                    patient_details[patient_id]['major_frax_source'] = 'OCR'
                
                # Major FRAX - OCR sin resultados
                elif 'major frax' in details_lower and 'ocr sin resultados' in details_lower:
                    stats['major_frax_ocr_failed'] += 1
                    patient_details[patient_id]['major_frax_source'] = 'OCR_FAILED'
                
                # Major FRAX - Sin JPEG
                elif 'major frax' in details_lower and 'sin jpeg' in details_lower:
                    stats['major_frax_no_jpeg'] += 1
                    patient_details[patient_id]['major_frax_source'] = 'NO_JPEG'
                
                # Hip FRAX desde XML
                if 'hip frax' in details_lower and 'xml' in details_lower:
                    stats['hip_frax_xml'] += 1
                    patient_details[patient_id]['hip_frax_source'] = 'XML'
    
    # Calcular totales
    total_with_major_frax = stats['major_frax_xml'] + stats['major_frax_ocr']
    total_without_major_frax = stats['major_frax_ocr_failed'] + stats['major_frax_no_jpeg']
    total_major_attempts = total_with_major_frax + total_without_major_frax
    
    # Mostrar resultados
    print("📊 ESTADÍSTICAS GLOBALES")
    print("-" * 80)
    print(f"Total de pacientes procesados: {len(stats['total_patients'])}")
    print(f"Total de extracciones FRAX registradas: {total_major_attempts}")
    
    print("\n🎯 MAJOR FRAX - Fuentes de Datos")
    print("-" * 80)
    print(f"  Extraído de XML:              {stats['major_frax_xml']:>6} ({stats['major_frax_xml']/total_major_attempts*100:>5.1f}%)" if total_major_attempts > 0 else "  Extraído de XML:              0")
    print(f"  Extraído via OCR (fallback):  {stats['major_frax_ocr']:>6} ({stats['major_frax_ocr']/total_major_attempts*100:>5.1f}%)" if total_major_attempts > 0 else "  Extraído via OCR (fallback):  0")
    print(f"  OCR sin resultados:           {stats['major_frax_ocr_failed']:>6} ({stats['major_frax_ocr_failed']/total_major_attempts*100:>5.1f}%)" if total_major_attempts > 0 else "  OCR sin resultados:           0")
    print(f"  Sin JPEG para OCR:            {stats['major_frax_no_jpeg']:>6} ({stats['major_frax_no_jpeg']/total_major_attempts*100:>5.1f}%)" if total_major_attempts > 0 else "  Sin JPEG para OCR:            0")
    print(f"  {'─'*76}")
    print(f"  Total con FRAX exitoso:       {total_with_major_frax:>6} ({total_with_major_frax/total_major_attempts*100:>5.1f}%)" if total_major_attempts > 0 else "  Total con FRAX exitoso:       0")
    print(f"  Total sin FRAX:               {total_without_major_frax:>6} ({total_without_major_frax/total_major_attempts*100:>5.1f}%)" if total_major_attempts > 0 else "  Total sin FRAX:               0")
    
    print("\n🎯 HIP FRAX")
    print("-" * 80)
    print(f"  Extraído de XML:              {stats['hip_frax_xml']:>6}")
    
    print("\n💡 INTERPRETACIÓN")
    print("-" * 80)
    if stats['major_frax_ocr'] > 0:
        print(f"  ✓ El {stats['major_frax_ocr']/total_major_attempts*100:.1f}% de reportes requirieron OCR como fallback")
        print(f"    (pixel extraction fue necesario en lugar de XML)")
    else:
        print(f"  ✓ Ningún reporte ha requerido OCR hasta ahora")
        print(f"    (todos los FRAX se extrajeron de XML)")
    
    if stats['major_frax_no_jpeg'] > 0:
        print(f"  ⚠️  {stats['major_frax_no_jpeg']} reportes no pudieron usar OCR (sin JPEG disponible)")
    
    # Mostrar últimos 10 pacientes procesados
    print("\n📋 ÚLTIMOS 10 PACIENTES PROCESADOS")
    print("-" * 80)
    recent_patients = sorted(
        [(pid, details) for pid, details in patient_details.items()],
        key=lambda x: x[1]['timestamp'],
        reverse=True
    )[:10]
    
    for patient_id, details in recent_patients:
        major_source = details['major_frax_source'] or '-'
        timestamp = details['timestamp']
        print(f"  [{timestamp}] Patient {patient_id:>10}: Major FRAX from {major_source}")
    
    print("\n" + "="*80)
    print(f"Análisis completado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

if __name__ == "__main__":
    analyze_frax_logs()
