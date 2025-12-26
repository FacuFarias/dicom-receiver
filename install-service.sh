#!/bin/bash

# Script to install DICOM Receiver service as a systemd service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="dicom-receiver"
SERVICE_FILE="${SCRIPT_DIR}/dicom-receiver.service"

echo "================================"
echo "DICOM Service Installer"
echo "================================"
echo ""

# Verify if running as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (sudo)"
    echo "Usage: sudo bash install-service.sh"
    exit 1
fi

# Verify that the service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "✗ Error: Service file not found at $SERVICE_FILE"
    exit 1
fi

# Verify that the directory exists
if [ ! -d "$SCRIPT_DIR" ]; then
    echo "✗ Error: Directory not found at $SCRIPT_DIR"
    exit 1
fi

echo "1. Validating environment..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "✗ Error: Virtual environment not found at $SCRIPT_DIR/venv"
    echo "Please first run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
echo "   ✓ Virtual environment found"

# Update paths in the service file
echo ""
echo "2. Configuring systemd service..."
cp "$SERVICE_FILE" "/tmp/dicom-receiver.service.tmp"
sed -i "s|/home/ubuntu/DICOMReceiver|$SCRIPT_DIR|g" "/tmp/dicom-receiver.service.tmp"
cp "/tmp/dicom-receiver.service.tmp" "/etc/systemd/system/${SERVICE_NAME}.service"
rm "/tmp/dicom-receiver.service.tmp"
echo "   ✓ Service file copied to /etc/systemd/system/"

# Reload daemon
echo ""
echo "3. Reloading systemd daemon..."
systemctl daemon-reload
echo "   ✓ Daemon reloaded"

# Enable service to start on boot
echo ""
echo "4. Enabling service on startup..."
systemctl enable "${SERVICE_NAME}.service"
echo "   ✓ Service enabled"

# Display information
echo ""
echo "================================"
echo "✓ Installation completed"
echo "================================"
echo ""
echo "Available commands:"
echo ""
echo "  Start service:"
echo "    sudo systemctl start ${SERVICE_NAME}"
echo ""
echo "  Stop service:"
echo "    sudo systemctl stop ${SERVICE_NAME}"
echo ""
echo "  Restart service:"
echo "    sudo systemctl restart ${SERVICE_NAME}"
echo ""
echo "  Pause service:"
echo "    sudo systemctl pause ${SERVICE_NAME}"
echo ""
echo "  View status:"
echo "    sudo systemctl status ${SERVICE_NAME}"
echo ""
echo "  View logs in real-time:"
echo "    sudo journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "  View last 50 logs:"
echo "    sudo journalctl -u ${SERVICE_NAME} -n 50"
echo ""
echo "  Disable (don't start on boot):"
echo "    sudo systemctl disable ${SERVICE_NAME}"
echo ""
echo "To completely uninstall:"
echo "  sudo systemctl stop ${SERVICE_NAME}"
echo "  sudo systemctl disable ${SERVICE_NAME}"
echo "  sudo rm /etc/systemd/system/${SERVICE_NAME}.service"
echo "  sudo systemctl daemon-reload"
echo ""
