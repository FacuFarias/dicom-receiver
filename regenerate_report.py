#!/usr/bin/env python3
"""
Script para regenerar el reporte de un registro específico de BD
"""

import sys
import psycopg2
from pathlib import Path
sys.path.append('/home/ubuntu/DICOMReceiver/algorithms/bd_extracts')
from bd_extract_hologic import generate_report

def regenerate_report(mrn, acc):
    """Regenera el reporte para un registro específico"""
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            user="facundo",
            password="qii123",
            database="qii"
        )
        
        cursor = conn.cursor()
        
        # Obtener datos necesarios del registro
        cursor.execute("""
            SELECT guid, mrn, acc, 
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
                   left_forearm_prev_date, left_forearm_prev_bmd, left_forearm_change_percent,
                   right_forearm_prev_date, right_forearm_prev_bmd, right_forearm_change_percent
            FROM reports.bd 
            WHERE mrn = %s AND acc = %s
        """, (mrn, acc))
        
        row = cursor.fetchone()
        
        if not row:
            print(f"✗ No se encontró registro para MRN={mrn}, ACC={acc}")
            return False
        
        # Construir diccionario de datos
        data = {
            'patient_id': row[1],  # mrn
            'accession_number': row[2],  # acc
            'lumbar_bmd': row[3],
            'lumbar_tscore': row[4],
            'lumbar_zscore': row[5],
            'left_hip_bmd': row[6],
            'left_hip_tscore': row[7],
            'left_hip_zscore': row[8],
            'right_hip_bmd': row[9],
            'right_hip_tscore': row[10],
            'right_hip_zscore': row[11],
            'left_forearm_bmd': row[12],
            'left_forearm_tscore': row[13],
            'left_forearm_zscore': row[14],
            'right_forearm_bmd': row[15],
            'right_forearm_tscore': row[16],
            'right_forearm_zscore': row[17],
            'major_fracture_risk': row[18],
            'hip_fracture_risk': row[19],
            'who_classification': row[20],
            'major_fracture_risk_prior': row[21],
            'hip_fracture_risk_prior': row[22],
            'lumbar_prev_date': row[23],
            'lumbar_prev_bmd': row[24],
            'lumbar_change_percent': row[25],
            'left_hip_prev_date': row[26],
            'left_hip_prev_bmd': row[27],
            'left_hip_change_percent': row[28],
            'right_hip_prev_date': row[29],
            'right_hip_prev_bmd': row[30],
            'right_hip_change_percent': row[31],
            'left_forearm_prev_date': row[32],
            'left_forearm_prev_bmd': row[33],
            'left_forearm_change_percent': row[34],
            'right_forearm_prev_date': row[35],
            'right_forearm_prev_bmd': row[36],
            'right_forearm_change_percent': row[37],
        }
        
        print(f"\n📋 Regenerando reporte para:")
        print(f"   MRN: {mrn}")
        print(f"   ACC: {acc}")
        print(f"   Major FRAX: {data.get('major_fracture_risk')}")
        print(f"   Hip FRAX: {data.get('hip_fracture_risk')}")
        print(f"   Major FRAX (prior): {data.get('major_fracture_risk_prior')}")
        print(f"   Hip FRAX (prior): {data.get('hip_fracture_risk_prior')}")
        
        # Generar nuevo reporte
        report_text = generate_report(data)
        
        # Actualizar el campo bd_report en la base de datos
        cursor.execute("""
            UPDATE reports.bd 
            SET bd_report = %s
            WHERE mrn = %s AND acc = %s
        """, (report_text, mrn, acc))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Guardar reporte en archivo
        report_path = f"/home/ubuntu/DICOMReceiver/reports/bd_report_{mrn}_{acc}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        print(f"\n✅ Reporte regenerado exitosamente")
        print(f"   📄 Guardado en: {report_path}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python3 regenerate_report.py <MRN> <ACC>")
        print("Ejemplo: python3 regenerate_report.py MMD1607371000 6568829")
        sys.exit(1)
    
    mrn = sys.argv[1]
    acc = sys.argv[2]
    
    success = regenerate_report(mrn, acc)
    sys.exit(0 if success else 1)
