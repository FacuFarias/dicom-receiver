#!/bin/bash

# Script de instalación para el servicio de limpieza automática de archivos DICOM

echo "🔧 Instalando servicio de limpieza de archivos DICOM..."

# Copiar archivos de servicio a systemd
sudo cp /home/ubuntu/DICOMReceiver/dicom-cleanup.service /etc/systemd/system/
sudo cp /home/ubuntu/DICOMReceiver/dicom-cleanup.timer /etc/systemd/system/

# Recargar configuración de systemd
sudo systemctl daemon-reload

# Habilitar el timer para que se inicie automáticamente
sudo systemctl enable dicom-cleanup.timer

# Iniciar el timer
sudo systemctl start dicom-cleanup.timer

# Verificar estado
echo ""
echo "✓ Servicio instalado correctamente"
echo ""
echo "Estado del timer:"
sudo systemctl status dicom-cleanup.timer --no-pager | head -10
echo ""
echo "Próximas ejecuciones:"
systemctl list-timers dicom-cleanup.timer --no-pager
echo ""
echo "📝 Para ver logs: sudo journalctl -u dicom-cleanup.service -f"
echo "📝 Archivo de log: /home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log"
echo ""
echo "Comandos útiles:"
echo "  - Ver estado: sudo systemctl status dicom-cleanup.timer"
echo "  - Detener: sudo systemctl stop dicom-cleanup.timer"
echo "  - Iniciar: sudo systemctl start dicom-cleanup.timer"
echo "  - Ejecutar ahora: sudo systemctl start dicom-cleanup.service"
echo "  - Desinstalar: sudo systemctl stop dicom-cleanup.timer && sudo systemctl disable dicom-cleanup.timer"
