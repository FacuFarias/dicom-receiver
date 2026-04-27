#!/usr/bin/env python3
"""
Script para consultar estadísticas de uso de OCR en reportes BD
"""

import psycopg2
from datetime import datetime

def query_bd_statistics():
    """Consulta estadísticas de reportes BD y uso potencial de OCR"""
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            user="facundo",
            password="qii123",
            database="qii"
        )
        
        cursor = conn.cursor()
        
        print("="*70)
        print("ESTADÍSTICAS DE REPORTES BD - Análisis de Fuentes de Datos")
        print("="*70)
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Total de reportes
        cursor.execute('SELECT COUNT(*) FROM reports.bd')
        total = cursor.fetchone()[0]
        print(f"📊 Total reportes BD: {total}")
        
        # Reportes con Major FRAX
        cursor.execute('''
            SELECT COUNT(*) 
            FROM reports.bd 
            WHERE major_fracture_risk IS NOT NULL 
            AND major_fracture_risk != ''
        ''')
        con_major_frax = cursor.fetchone()[0]
        
        # Reportes con Hip FRAX
        cursor.execute('''
            SELECT COUNT(*) 
            FROM reports.bd 
            WHERE "hip_fracture_risk│" IS NOT NULL 
            AND "hip_fracture_risk│" != ''
        ''')
        con_hip_frax = cursor.fetchone()[0]
        
        # Reportes SIN Major FRAX (candidatos a haber necesitado OCR)
        sin_major_frax = total - con_major_frax
        
        print(f"\n🎯 FRAX - Major Osteoporotic Fracture:")
        print(f"   Con valor: {con_major_frax} ({(con_major_frax/total*100):.1f}%)")
        print(f"   Sin valor: {sin_major_frax} ({(sin_major_frax/total*100):.1f}%)")
        
        print(f"\n🎯 FRAX - Hip Fracture:")
        print(f"   Con valor: {con_hip_frax} ({(con_hip_frax/total*100):.1f}%)")
        
        # Análisis por fabricante (si hay campo manufacturer)
        try:
            cursor.execute('''
                SELECT 
                    CASE 
                        WHEN major_fracture_risk IS NOT NULL AND major_fracture_risk != '' 
                        THEN 'Con FRAX'
                        ELSE 'Sin FRAX'
                    END as estado,
                    COUNT(*) as cantidad
                FROM reports.bd
                GROUP BY estado
            ''')
            
            print(f"\n📈 Distribución de reportes:")
            for row in cursor.fetchall():
                estado, cantidad = row
                print(f"   {estado}: {cantidad}")
                
        except Exception as e:
            print(f"   (No se pudo obtener distribución detallada)")
        
        # Nota sobre OCR
        print(f"\n⚠️  NOTA IMPORTANTE:")
        print(f"   - Los {sin_major_frax} reportes SIN Major FRAX son candidatos potenciales")
        print(f"     a haber necesitado OCR (si fueron estudios HIP)")
        print(f"   - Sin embargo, muchos pueden ser estudios LUMBAR que naturalmente")
        print(f"     no tienen FRAX")
        print(f"   - Para tracking preciso, se recomienda agregar logging específico")
        
        print("\n" + "="*70)
        
        # Sistema de archivos
        from pathlib import Path
        pixel_base = Path('/home/ubuntu/DICOMReceiver/pixel_extraction/BD')
        if pixel_base.exists():
            patient_dirs = [d for d in pixel_base.iterdir() if d.is_dir()]
            total_jpegs = sum(len(list(d.glob('*.jpg'))) for d in patient_dirs)
            
            print(f"\n💾 Sistema de Archivos:")
            print(f"   Pacientes con pixel extraction: {len(patient_dirs)}")
            print(f"   Total JPEGs extraídos: {total_jpegs}")
            print(f"   Promedio JPEGs por paciente: {total_jpegs/len(patient_dirs):.1f}")
        
        print("="*70)
        
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        print(f"\nVerificar que:")
        print(f"  1. PostgreSQL está corriendo: sudo systemctl status postgresql")
        print(f"  2. Las credenciales son correctas")
        print(f"  3. La base de datos 'qii' existe")
        return False
    
    return True

if __name__ == "__main__":
    query_bd_statistics()
