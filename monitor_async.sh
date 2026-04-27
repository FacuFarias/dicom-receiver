#!/bin/bash
#
# Monitor DICOM Receiver en modo Async
# Muestra métricas en tiempo real: memoria, CPU, colas, stats
#
# Uso: ./monitor_async.sh [intervalo_segundos]
#

INTERVAL=${1:-2}  # Default: 2 segundos

echo "======================="
echo "DICOM Receiver Monitor"
echo "======================="
echo "Intervalo: ${INTERVAL}s"
echo "Presiona Ctrl+C para salir"
echo "======================="
echo ""

# Colores
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para obtener métricas del servicio
get_metrics() {
    # Proceso Python
    PROC_INFO=$(ps aux | grep "[p]ython.*main.py" | awk '{print $6/1024 "," $3}')
    if [ -z "$PROC_INFO" ]; then
        echo -e "${RED}❌ Servicio NO corriendo${NC}"
        return 1
    fi
    
    RSS_MB=$(echo $PROC_INFO | cut -d',' -f1)
    CPU_PCT=$(echo $PROC_INFO | cut -d',' -f2)
    
    # Memoria del sistema
    MEM_AVAIL=$(free -h | grep Mem | awk '{print $7}')
    
    # Status del servicio
    SERVICE_STATUS=$(systemctl is-active dicom-receiver.service 2>/dev/null || echo "unknown")
    
    # Logs recientes - buscar stats async
    RECENT_STATS=$(sudo journalctl -u dicom-receiver.service --since "10 seconds ago" --no-pager 2>/dev/null | grep "ASYNC STATS\|QUEUE DEPTHS\|BACKPRESSURE\|SATURADA" | tail -5)
    
    # Timestamp
    TIMESTAMP=$(date '+%H:%M:%S')
    
    # Mostrar header cada 20 iteraciones
    if [ $((COUNTER % 20)) -eq 0 ]; then
        echo ""
        printf "%-10s | %-12s | %-8s | %-14s | %-10s\n" "Tiempo" "Memoria" "CPU" "Memoria Disp" "Estado"
        echo "-----------|--------------|----------|----------------|------------"
    fi
    
    # Color por nivel de memoria
    MEM_COLOR=$GREEN
    if (( $(echo "$RSS_MB > 500" | bc -l 2>/dev/null || echo 0) )); then
        MEM_COLOR=$YELLOW
    fi
    if (( $(echo "$RSS_MB > 1000" | bc -l 2>/dev/null || echo 0) )); then
        MEM_COLOR=$RED
    fi
    
    # Color por estado
    STATUS_COLOR=$GREEN
    if [ "$SERVICE_STATUS" != "active" ]; then
        STATUS_COLOR=$RED
    fi
    
    # Mostrar línea de métricas
    printf "%-10s | ${MEM_COLOR}%10.1f MB${NC} | %6.1f%% | %-14s | ${STATUS_COLOR}%-10s${NC}\n" \
        "$TIMESTAMP" "$RSS_MB" "$CPU_PCT" "$MEM_AVAIL" "$SERVICE_STATUS"
    
    # Mostrar stats recientes si existen
    if [ -n "$RECENT_STATS" ]; then
        echo ""
        echo -e "${BLUE}📊 Stats Recientes:${NC}"
        echo "$RECENT_STATS" | while IFS= read -r line; do
            if echo "$line" | grep -q "BACKPRESSURE\|SATURADA"; then
                echo -e "  ${RED}⚠️  $line${NC}"
            elif echo "$line" | grep -q "ASYNC STATS"; then
                echo -e "  ${GREEN}$line${NC}"
            else
                echo "  $line"
            fi
        done
        echo ""
    fi
    
    COUNTER=$((COUNTER + 1))
}

# Contador para headers
COUNTER=0

# Loop principal
while true; do
    clear
    echo "======================="
    echo "DICOM Receiver Monitor"
    echo "$(date '+%Y-%m-%d %H:%M:%S')"
    echo "======================="
    echo ""
    
    get_metrics
    
    sleep $INTERVAL
done
