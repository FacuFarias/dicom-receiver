#!/bin/bash
# Política de retención diferenciada por modalidad:
# - BD (Bone Density): 48 horas (2 días)
# - US (Ultrasound): 3 horas
# - SR (Structured Reports): 48 horas (2 días)
# - Otros: 30 días
# Mantener máximo 15GB en dicom_storage

LOG_FILE="/home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log"
STORAGE_PATH="/home/ubuntu/DICOMReceiver/dicom_storage"
MAX_SIZE_GB=15

# Tiempos de retención en minutos
BD_RETENTION_MINUTES=$((48 * 60))  # 48 horas = 2880 minutos
US_RETENTION_MINUTES=$((3 * 60))   # 3 horas = 180 minutos
SR_RETENTION_MINUTES=$((48 * 60))  # 48 horas = 2880 minutos
OTHER_RETENTION_DAYS=30

# Crear directorio de logs si no existe
mkdir -p /home/ubuntu/DICOMReceiver/logs

# Función de logging
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_message "=== Iniciando limpieza de archivos DICOM ==="

# Obtener espacio usado antes de la limpieza
SPACE_BEFORE=$(du -sh "$STORAGE_PATH" 2>/dev/null | cut -f1)
log_message "Espacio usado antes: $SPACE_BEFORE"

# Contar archivos antes
FILES_BEFORE=$(find "$STORAGE_PATH" -type f 2>/dev/null | wc -l)
log_message "Archivos totales antes: $FILES_BEFORE"

# ========== LIMPIEZA DE ARCHIVOS US (3 horas) ==========
log_message "--- Limpieza de archivos US (> 3 horas) ---"
US_DELETED=$(find "$STORAGE_PATH" -type f -name "US_*" -mmin +$US_RETENTION_MINUTES -delete -print 2>/dev/null | tee -a "$LOG_FILE" | wc -l)
log_message "Archivos US eliminados: $US_DELETED"

# ========== LIMPIEZA DE ARCHIVOS BD (48 horas) ==========
log_message "--- Limpieza de archivos BD (> 48 horas) ---"
BD_DELETED=$(find "$STORAGE_PATH" -type f -name "BD_*" -mmin +$BD_RETENTION_MINUTES -delete -print 2>/dev/null | tee -a "$LOG_FILE" | wc -l)
log_message "Archivos BD eliminados: $BD_DELETED"

# ========== LIMPIEZA DE ARCHIVOS SR (48 horas) ==========
log_message "--- Limpieza de archivos SR (> 48 horas) ---"
SR_DELETED=$(find "$STORAGE_PATH" -type f -name "SR_*" -mmin +$SR_RETENTION_MINUTES -delete -print 2>/dev/null | tee -a "$LOG_FILE" | wc -l)
log_message "Archivos SR eliminados: $SR_DELETED"

# ========== LIMPIEZA DE OTROS ARCHIVOS (30 días) ==========
log_message "--- Limpieza de otros archivos (> 30 días) ---"
OTHER_DELETED=$(find "$STORAGE_PATH" -type f -name "*.dcm" ! -name "US_*" ! -name "BD_*" ! -name "SR_*" -mtime +$OTHER_RETENTION_DAYS -delete -print 2>/dev/null | tee -a "$LOG_FILE" | wc -l)
log_message "Otros archivos eliminados: $OTHER_DELETED"

# ========== ELIMINAR CARPETAS VACÍAS ==========
EMPTY_DIRS=$(find "$STORAGE_PATH" -mindepth 1 -type d -empty -delete -print 2>/dev/null | wc -l)
if [ "$EMPTY_DIRS" -gt 0 ]; then
    log_message "Carpetas vacías eliminadas: $EMPTY_DIRS"
fi

# ========== VERIFICAR LÍMITE DE TAMAÑO ==========
CURRENT_SIZE=$(du -sb "$STORAGE_PATH" 2>/dev/null | awk '{print $1}')
MAX_SIZE_BYTES=$((MAX_SIZE_GB * 1024 * 1024 * 1024))

if [ "$CURRENT_SIZE" -gt "$MAX_SIZE_BYTES" ]; then
    SIZE_GB=$(($CURRENT_SIZE/1024/1024/1024))
    log_message "⚠️  Tamaño excede límite (${SIZE_GB}GB > ${MAX_SIZE_GB}GB)"
    log_message "Eliminando archivos más antiguos..."
    find "$STORAGE_PATH" -type f -printf '%T+ %p\n' | sort | head -n 500 | cut -d' ' -f2- | xargs rm -f
    log_message "500 archivos más antiguos eliminados por límite de espacio"
fi

# Obtener espacio usado después de la limpieza
SPACE_AFTER=$(du -sh "$STORAGE_PATH" 2>/dev/null | cut -f1)
log_message "Espacio usado después: $SPACE_AFTER"

# Contar archivos después
FILES_AFTER=$(find "$STORAGE_PATH" -type f 2>/dev/null | wc -l)
log_message "Archivos totales después: $FILES_AFTER"

# Total de archivos eliminados
TOTAL_DELETED=$((US_DELETED + BD_DELETED + SR_DELETED + OTHER_DELETED))
log_message "=== Resumen de limpieza ==="
log_message "  US eliminados (3h): $US_DELETED"
log_message "  BD eliminados (48h): $BD_DELETED"
log_message "  SR eliminados (48h): $SR_DELETED"
log_message "  Otros eliminados (30d): $OTHER_DELETED"
log_message "  Total eliminados: $TOTAL_DELETED"
log_message "=== Limpieza completada ==="
echo ""  >> "$LOG_FILE"

exit 0
