#!/bin/bash
# Script de prueba (DRY RUN) para verificar qué archivos se eliminarían
# NO elimina nada, solo muestra qué se haría

STORAGE_PATH="/home/ubuntu/DICOMReceiver/dicom_storage"

# Tiempos de retención en minutos
BD_RETENTION_MINUTES=$((24 * 60))  # 24 horas = 1440 minutos
US_RETENTION_MINUTES=$((3 * 60))   # 3 horas = 180 minutos
OTHER_RETENTION_DAYS=30

echo "════════════════════════════════════════════════════════════"
echo "  ANÁLISIS DE LIMPIEZA (DRY RUN - NO ELIMINA NADA)"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "📋 Política de retención configurada:"
echo "  • BD (Bone Density): 24 horas"
echo "  • US (Ultrasound): 3 horas"
echo "  • Otros archivos (SR, etc): 30 días"
echo ""

# Contar archivos US que se eliminarían (> 3 horas)
US_COUNT=$(find "$STORAGE_PATH" -type f -name "US_*" -mmin +$US_RETENTION_MINUTES 2>/dev/null | wc -l)
echo "🔵 Archivos US > 3 horas: $US_COUNT"
if [ "$US_COUNT" -gt 0 ]; then
    echo "   Ejemplos (primeros 5):"
    find "$STORAGE_PATH" -type f -name "US_*" -mmin +$US_RETENTION_MINUTES -printf '   %p (%.16TY-%.16Tm-%.16Td %.16TH:%.16TM)\n' 2>/dev/null | head -5
fi
echo ""

# Contar archivos BD que se eliminarían (> 24 horas)
BD_COUNT=$(find "$STORAGE_PATH" -type f -name "BD_*" -mmin +$BD_RETENTION_MINUTES 2>/dev/null | wc -l)
echo "🟢 Archivos BD > 24 horas: $BD_COUNT"
if [ "$BD_COUNT" -gt 0 ]; then
    echo "   Ejemplos (primeros 5):"
    find "$STORAGE_PATH" -type f -name "BD_*" -mmin +$BD_RETENTION_MINUTES -printf '   %p (%.16TY-%.16Tm-%.16Td %.16TH:%.16TM)\n' 2>/dev/null | head -5
fi
echo ""

# Contar otros archivos que se eliminarían (> 30 días)
OTHER_COUNT=$(find "$STORAGE_PATH" -type f \( -name "SR_*" -o -name "*.dcm" \) ! -name "US_*" ! -name "BD_*" -mtime +$OTHER_RETENTION_DAYS 2>/dev/null | wc -l)
echo "🟡 Otros archivos > 30 días: $OTHER_COUNT"
if [ "$OTHER_COUNT" -gt 0 ]; then
    echo "   Ejemplos (primeros 5):"
    find "$STORAGE_PATH" -type f \( -name "SR_*" -o -name "*.dcm" \) ! -name "US_*" ! -name "BD_*" -mtime +$OTHER_RETENTION_DAYS -printf '   %p (%.16TY-%.16Tm-%.16Td)\n' 2>/dev/null | head -5
fi
echo ""

# Estadísticas generales
TOTAL_FILES=$(find "$STORAGE_PATH" -type f 2>/dev/null | wc -l)
US_TOTAL=$(find "$STORAGE_PATH" -type f -name "US_*" 2>/dev/null | wc -l)
BD_TOTAL=$(find "$STORAGE_PATH" -type f -name "BD_*" 2>/dev/null | wc -l)
STORAGE_SIZE=$(du -sh "$STORAGE_PATH" 2>/dev/null | awk '{print $1}')

echo "════════════════════════════════════════════════════════════"
echo "📊 ESTADÍSTICAS DEL ALMACENAMIENTO"
echo "════════════════════════════════════════════════════════════"
echo "  Total de archivos: $TOTAL_FILES"
echo "  Archivos US: $US_TOTAL"
echo "  Archivos BD: $BD_TOTAL"
echo "  Tamaño total: $STORAGE_SIZE"
echo ""
echo "  📊 Se eliminarían: $((US_COUNT + BD_COUNT + OTHER_COUNT)) archivos"
echo "════════════════════════════════════════════════════════════"
