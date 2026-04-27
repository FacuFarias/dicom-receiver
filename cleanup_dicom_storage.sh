#!/bin/bash
# Política de retención diferenciada por modalidad:
# - BD (Bone Density): 24 horas
# - US (Ultrasound): 3 horas
# - Otros: 30 días
# Mantener máximo 15GB en dicom_storage

STORAGE_PATH="/home/ubuntu/DICOMReceiver/dicom_storage"
MAX_SIZE_GB=15

# Tiempos de retención en minutos
BD_RETENTION_MINUTES=$((24 * 60))  # 24 horas = 1440 minutos
US_RETENTION_MINUTES=$((3 * 60))   # 3 horas = 180 minutos
OTHER_RETENTION_DAYS=30

echo "[$(date)] Iniciando limpieza de DICOM storage..."

# Eliminar archivos US antiguos (> 3 horas)
US_DELETED=$(find "$STORAGE_PATH" -type f -name "US_*" -mmin +$US_RETENTION_MINUTES -delete -print 2>/dev/null | wc -l)
echo "  - Archivos US > 3 horas eliminados: $US_DELETED"

# Eliminar archivos BD antiguos (> 24 horas)
BD_DELETED=$(find "$STORAGE_PATH" -type f -name "BD_*" -mmin +$BD_RETENTION_MINUTES -delete -print 2>/dev/null | wc -l)
echo "  - Archivos BD > 24 horas eliminados: $BD_DELETED"

# Eliminar otros archivos antiguos (> 30 días) - SR, etc
OTHER_DELETED=$(find "$STORAGE_PATH" -type f \( -name "SR_*" -o -name "*.dcm" \) ! -name "US_*" ! -name "BD_*" -mtime +$OTHER_RETENTION_DAYS -delete -print 2>/dev/null | wc -l)
echo "  - Otros archivos > ${OTHER_RETENTION_DAYS} días eliminados: $OTHER_DELETED"

# Eliminar carpetas vacías (StudyUID y PatientID)
EMPTY_DIRS=$(find "$STORAGE_PATH" -mindepth 1 -type d -empty -delete -print 2>/dev/null | wc -l)
if [ "$EMPTY_DIRS" -gt 0 ]; then
    echo "  - Carpetas vacías eliminadas: $EMPTY_DIRS"
fi

# Verificar tamaño total
CURRENT_SIZE=$(du -sb "$STORAGE_PATH" 2>/dev/null | awk '{print $1}')
MAX_SIZE_BYTES=$((MAX_SIZE_GB * 1024 * 1024 * 1024))

if [ "$CURRENT_SIZE" -gt "$MAX_SIZE_BYTES" ]; then
    echo "  - Tamaño excede límite ($(($CURRENT_SIZE/1024/1024/1024))GB > ${MAX_SIZE_GB}GB)"
    echo "  - Eliminando archivos más antiguos..."
    find "$STORAGE_PATH" -type f -name "*.dcm" -printf '%T+ %p\n' | sort | head -n 500 | cut -d' ' -f2- | xargs rm -f
fi

FINAL_SIZE=$(du -sh "$STORAGE_PATH" 2>/dev/null | awk '{print $1}')
echo "  - Tamaño final: $FINAL_SIZE"
echo "[$(date)] Limpieza completada"
