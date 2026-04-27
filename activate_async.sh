#!/bin/bash
#
# Activación de Modo Async
# Habilita async mode con verificaciones de seguridad
#
# Uso: sudo ./activate_async.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.py"

echo "===================================="
echo "DICOM Receiver - Activar Modo Async"
echo "===================================="
echo ""

# Verificar permisos
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Error: Este script debe ejecutarse con sudo"
    echo "   Uso: sudo ./activate_async.sh"
    exit 1
fi

# Pre-checks: Verificar que servicio está estable
echo "🔍 Verificando estado actual del servicio..."
STATUS=$(systemctl is-active dicom-receiver.service 2>/dev/null || echo "inactive")

if [ "$STATUS" != "active" ]; then
    echo "   ❌ Servicio no está corriendo (status: $STATUS)"
    echo "   Inicia el servicio primero con: sudo systemctl start dicom-receiver.service"
    exit 1
fi
echo "   ✓ Servicio activo"

# Verificar memoria disponible
MEM_AVAIL_GB=$(free -g | grep Mem | awk '{print $7}')
if [ "$MEM_AVAIL_GB" -lt 1 ]; then
    echo "   ⚠️  ADVERTENCIA: Memoria disponible baja (${MEM_AVAIL_GB}GB)"
    echo "   Se recomienda al menos 1GB libre antes de activar async"
    read -p "   ¿Continuar de todos modos? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Operación cancelada"
        exit 0
    fi
else
    echo "   ✓ Memoria disponible: ${MEM_AVAIL_GB}GB"
fi

# Verificar estado actual de config
CURRENT_STATE=$(grep "'enabled':" "$CONFIG_FILE" | head -1 | grep -o "True\|False")
echo "   Estado actual: enabled = $CURRENT_STATE"

if [ "$CURRENT_STATE" = "True" ]; then
    echo "   ⚠️  Async ya está habilitado"
    read -p "   ¿Reiniciar servicio de todos modos? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Operación cancelada"
        exit 0
    fi
    ALREADY_ENABLED=true
else
    ALREADY_ENABLED=false
fi

# Backup de config
echo ""
echo "📁 Creando backup de config.py..."
cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
echo "   ✓ Backup creado"

# Habilitar async mode si no estaba habilitado
if [ "$ALREADY_ENABLED" = false ]; then
    echo ""
    echo "🔧 Habilitando modo async..."
    sed -i "s/'enabled': False/'enabled': True/g" "$CONFIG_FILE"
    
    # Verificar cambio
    NEW_STATE=$(grep "'enabled':" "$CONFIG_FILE" | head -1 | grep -o "True\|False")
    if [ "$NEW_STATE" = "True" ]; then
        echo "   ✓ Async mode habilitado en config"
    else
        echo "   ❌ Error: No se pudo cambiar la configuración"
        exit 1
    fi
fi

# Advertencia final
echo ""
echo "⚠️  IMPORTANTE:"
echo "   - Monitorea el servicio activamente durante los próximos 5-10 minutos"
echo "   - Usa: ./monitor_async.sh"
echo "   - Si hay problemas, ejecuta: sudo ./rollback_async.sh"
echo ""
read -p "¿Proceder con restart del servicio? (y/n): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operación cancelada"
    echo "Config ya fue modificado, puedes reiniciar manualmente con:"
    echo "  sudo systemctl restart dicom-receiver.service"
    exit 0
fi

# Reiniciar servicio
echo ""
echo "🔄 Reiniciando servicio dicom-receiver..."
systemctl restart dicom-receiver.service

# Esperar que inicie
echo "   Esperando inicio del servicio..."
sleep 4

# Verificar estado
STATUS=$(systemctl is-active dicom-receiver.service 2>/dev/null || echo "failed")

echo ""
echo "===================================="
if [ "$STATUS" = "active" ]; then
    echo "✅ ACTIVACIÓN EXITOSA"
    echo ""
    echo "Estado: $STATUS"
    echo "Modo: ASYNC"
    echo ""
    
    # Mostrar primeras líneas del log
    echo "📋 Verificando logs de inicio..."
    journalctl -u dicom-receiver.service --since "30 seconds ago" --no-pager | grep -i "modo\|async\|worker\|queue" | tail -8
    
    echo ""
    echo "📊 Inicia monitoreo con:"
    echo "   ./monitor_async.sh"
    echo ""
    echo "🔙 Si hay problemas, rollback con:"
    echo "   sudo ./rollback_async.sh"
else
    echo "❌ ERROR: Servicio no inició correctamente"
    echo "Estado: $STATUS"
    echo ""
    echo "Ejecutando rollback automático..."
    sed -i "s/'enabled': True/'enabled': False/g" "$CONFIG_FILE"
    systemctl restart dicom-receiver.service
    echo ""
    echo "Revisa los logs con:"
    echo "  sudo journalctl -u dicom-receiver.service -n 50"
fi
echo "===================================="
