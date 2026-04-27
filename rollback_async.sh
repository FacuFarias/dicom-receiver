#!/bin/bash
#
# Rollback de Modo Async a Modo Sync
# Deshabilita async mode y reinicia el servicio
#
# Uso: sudo ./rollback_async.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.py"

echo "================================"
echo "DICOM Receiver - Rollback Async"
echo "================================"
echo ""

# Verificar permisos
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Error: Este script debe ejecutarse con sudo"
    echo "   Uso: sudo ./rollback_async.sh"
    exit 1
fi

# Backup de config
echo "📁 Creando backup de config.py..."
cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
echo "   ✓ Backup creado"

# Verificar estado actual
CURRENT_STATE=$(grep "'enabled':" "$CONFIG_FILE" | head -1 | grep -o "True\|False")
echo ""
echo "📊 Estado actual: enabled = $CURRENT_STATE"

if [ "$CURRENT_STATE" = "False" ]; then
    echo "   ⚠️  Async ya está deshabilitado"
    read -p "   ¿Continuar de todos modos? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Operación cancelada"
        exit 0
    fi
fi

# Deshabilitar async mode
echo ""
echo "🔧 Deshabilitando modo async..."
sed -i "s/'enabled': True/'enabled': False/g" "$CONFIG_FILE"

# Verificar cambio
NEW_STATE=$(grep "'enabled':" "$CONFIG_FILE" | head -1 | grep -o "True\|False")
if [ "$NEW_STATE" = "False" ]; then
    echo "   ✓ Async mode deshabilitado en config"
else
    echo "   ❌ Error: No se pudo cambiar la configuración"
    exit 1
fi

# Reiniciar servicio
echo ""
echo "🔄 Reiniciando servicio dicom-receiver..."
systemctl restart dicom-receiver.service

# Esperar que inicie
echo "   Esperando inicio del servicio..."
sleep 3

# Verificar estado
STATUS=$(systemctl is-active dicom-receiver.service 2>/dev/null || echo "failed")

echo ""
echo "================================"
if [ "$STATUS" = "active" ]; then
    echo "✅ ROLLBACK EXITOSO"
    echo ""
    echo "Estado: $STATUS"
    echo "Modo: SYNC (legacy)"
    echo ""
    
    # Mostrar primeras líneas del log
    echo "📋 Últimos logs:"
    journalctl -u dicom-receiver.service --since "30 seconds ago" --no-pager | grep -i "modo\|sync\|async" | tail -5
else
    echo "❌ ERROR: Servicio no inició correctamente"
    echo "Estado: $STATUS"
    echo ""
    echo "Revisa los logs con:"
    echo "  sudo journalctl -u dicom-receiver.service -n 50"
fi
echo "================================"
