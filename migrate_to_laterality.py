#!/usr/bin/env python3
"""
Script para migrar datos de femoral_*/forearm_* a las nuevas columnas con lateralidad
"""
import psycopg2

def migrate_data():
    """Migra datos existentes a las nuevas columnas con lateralidad"""
    conn = psycopg2.connect(
        host="localhost",
        user="facundo",
        password="qii123",
        database="qii"
    )
    cur = conn.cursor()
    
    print("Migrando datos existentes...")
    
    # Migrar femoral_* a left_hip_* (asumiendo left por defecto)
    cur.execute("""
        UPDATE reports.bd 
        SET 
          left_hip_bmd = femoral_bmd,
          left_hip_tscore = femoral_tscore,
          left_hip_zscore = femoral_zscore
        WHERE femoral_bmd IS NOT NULL
    """)
    femoral_migrated = cur.rowcount
    print(f"  ✓ {femoral_migrated} registros femoral migrados a left_hip")
    
    # Nota: forearm_* columns no existían antes, solo las nuevas left_forearm_* y right_forearm_*
    
    conn.commit()
    
    # Verificar migración
    cur.execute("SELECT COUNT(*) FROM reports.bd WHERE left_hip_bmd IS NOT NULL")
    total_left_hip = cur.fetchone()[0]
    
    print(f"\nEstado final:")
    print(f"  - Registros con left_hip: {total_left_hip}")
    
    conn.close()
    print("\n✅ Migración completada")

if __name__ == "__main__":
    migrate_data()
