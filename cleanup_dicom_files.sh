#!/bin/bash

# Script para eliminar archivos DICOM más antiguos de 24 horas
# Mantiene los XML extraídos y reportes generados

LOG_FILE="/home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log"
DICOM_DIR="/home/ubuntu/DICOMReceiver/dicom_storage"
HOURS_OLD=24

# Crear directorio de logs si no existe
mkdir -p /home/ubuntu/DICOMReceiver/logs

# Función de logging
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log_message "=== Iniciando limpieza de archivos DICOM ==="

# Obtener espacio usado antes de la limpieza
SPACE_BEFORE=$(du -sh "$DICOM_DIR" 2>/dev/null | cut -f1)
log_message "Espacio usado antes: $SPACE_BEFORE"

# Contar archivos antes
FILES_BEFORE=$(find "$DICOM_DIR" -type f 2>/dev/null | wc -l)
log_message "Archivos totales antes: $FILES_BEFORE"

# Eliminar archivos DICOM más antiguos de 24 horas
# Solo elimina los archivos DICOM, no los directorios
DELETED=0
while IFS= read -r file; do
    rm -f "$file" 2>/dev/null
    if [ $? -eq 0 ]; then
        ((DELETED++))
    fi
done < <(find "$DICOM_DIR" -type f -mtime +0 -mmin +$((HOURS_OLD * 60)))

log_message "Archivos DICOM eliminados: $DELETED"

# Eliminar directorios vacíos
find "$DICOM_DIR" -type d -empty -delete 2>/dev/null

# Obtener espacio usado después de la limpieza
SPACE_AFTER=$(du -sh "$DICOM_DIR" 2>/dev/null | cut -f1)
log_message "Espacio usado después: $SPACE_AFTER"

# Contar archivos después
FILES_AFTER=$(find "$DICOM_DIR" -type f 2>/dev/null | wc -l)
log_message "Archivos totales después: $FILES_AFTER"

log_message "=== Limpieza completada ==="
echo ""  >> "$LOG_FILE"

# Mostrar estadísticas en consola si se ejecuta manualmente
if [ -t 1 ]; then
    echo "✓ Limpieza de archivos DICOM completada"
    echo "  Archivos eliminados: $DELETED"
    echo "  Espacio antes: $SPACE_BEFORE → después: $SPACE_AFTER"
    echo "  Log: $LOG_FILE"
fi

exit 0
