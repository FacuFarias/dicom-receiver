#!/bin/bash
# Script rápido para ver estadísticas de fuentes FRAX

echo "═══════════════════════════════════════════════════════════"
echo "RESUMEN RÁPIDO - Fuentes de Datos FRAX"
echo "═══════════════════════════════════════════════════════════"
echo ""

LOG_FILE="/home/ubuntu/DICOMReceiver/logs/bd_processing.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Archivo de log no encontrado: $LOG_FILE"
    exit 1
fi

# Contar tipos de extracción (asegurar que son números)
XML_COUNT=$(grep -c "Major FRAX extraído de XML" "$LOG_FILE" 2>/dev/null)
OCR_COUNT=$(grep -c "extraído via OCR (fallback)" "$LOG_FILE" 2>/dev/null)
OCR_FAILED=$(grep -c "OCR sin resultados" "$LOG_FILE" 2>/dev/null)
NO_JPEG=$(grep -c "Sin JPEG para OCR" "$LOG_FILE" 2>/dev/null)

# Asegurar valores numéricos
XML_COUNT=${XML_COUNT:-0}
OCR_COUNT=${OCR_COUNT:-0}
OCR_FAILED=${OCR_FAILED:-0}
NO_JPEG=${NO_JPEG:-0}

TOTAL=$((XML_COUNT + OCR_COUNT + OCR_FAILED + NO_JPEG))

if [ "$TOTAL" -eq 0 ]; then
    echo "⚠️  No hay datos de FRAX registrados aún"
    echo ""
    echo "Los logs se generan automáticamente al procesar nuevos estudios BD."
    echo "Ejecuta un procesamiento BD para comenzar a recopilar datos."
    exit 0
fi

echo "📊 CONTADORES:"
echo "───────────────────────────────────────────────────────────"

# Calcular porcentajes
XML_PCT=$(awk "BEGIN {printf \"%.1f\", ($XML_COUNT/$TOTAL)*100}")
OCR_PCT=$(awk "BEGIN {printf \"%.1f\", ($OCR_COUNT/$TOTAL)*100}")
FAILED_PCT=$(awk "BEGIN {printf \"%.1f\", ($OCR_FAILED/$TOTAL)*100}")
NO_JPEG_PCT=$(awk "BEGIN {printf \"%.1f\", ($NO_JPEG/$TOTAL)*100}")

printf "  • Extraído de XML:          %6d (%5s%%)\n" "$XML_COUNT" "$XML_PCT"
printf "  • Extraído via OCR:         %6d (%5s%%)\n" "$OCR_COUNT" "$OCR_PCT"
printf "  • OCR sin resultados:       %6d (%5s%%)\n" "$OCR_FAILED" "$FAILED_PCT"
printf "  • Sin JPEG disponible:      %6d (%5s%%)\n" "$NO_JPEG" "$NO_JPEG_PCT"
echo "───────────────────────────────────────────────────────────"
printf "  TOTAL extracciones:         %6d\n" "$TOTAL"
echo ""

# Calcular tasa de éxito
SUCCESS=$((XML_COUNT + OCR_COUNT))
if [ "$TOTAL" -gt 0 ]; then
    SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($SUCCESS/$TOTAL)*100}")
    echo "✅ Tasa de éxito: $SUCCESS_RATE%"
fi
echo ""

# Uso de OCR como porcentaje del total exitoso
if [ "$SUCCESS" -gt 0 ]; then
    OCR_PERCENTAGE=$(awk "BEGIN {printf \"%.1f\", ($OCR_COUNT/$SUCCESS)*100}")
    echo "🔍 Pixel Extraction (OCR) necesario en: $OCR_PERCENTAGE% de casos exitosos"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "Para análisis detallado ejecuta: python3 analyze_frax_sources.py"
echo "═══════════════════════════════════════════════════════════"
