#!/bin/bash
# Installation script for US Reports API Service

set -e  # Exit on error

echo "=========================================="
echo "US Reports API Service Installation"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Error: This script must be run as root (use sudo)"
    exit 1
fi

# Get the actual user who called sudo
ACTUAL_USER=${SUDO_USER:-$USER}
ACTUAL_HOME=$(eval echo ~$ACTUAL_USER)
SERVICE_DIR="$ACTUAL_HOME/DICOMReceiver"

echo "📋 Configuration:"
echo "   User: $ACTUAL_USER"
echo "   Home: $ACTUAL_HOME"
echo "   Service directory: $SERVICE_DIR"
echo ""

# Check if directory exists
if [ ! -d "$SERVICE_DIR" ]; then
    echo "❌ Error: Directory $SERVICE_DIR does not exist"
    exit 1
fi

# Check if us_api.py exists
if [ ! -f "$SERVICE_DIR/us_api.py" ]; then
    echo "❌ Error: us_api.py not found in $SERVICE_DIR"
    exit 1
fi

# Make us_api.py executable
echo "🔧 Making us_api.py executable..."
chmod +x "$SERVICE_DIR/us_api.py"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r "$SERVICE_DIR/requirements.txt" || {
    echo "⚠️  Warning: Failed to install dependencies. Please install manually:"
    echo "    pip3 install -r $SERVICE_DIR/requirements.txt"
}

# Copy service file to systemd
echo "📄 Installing systemd service..."
cp "$SERVICE_DIR/us-api.service" /etc/systemd/system/

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable service to start on boot
echo "✅ Enabling service to start on boot..."
systemctl enable us-api.service

# Start the service
echo "▶️  Starting US Reports API service..."
systemctl start us-api.service

# Wait a moment for service to start
sleep 2

# Check status
echo ""
echo "📊 Service Status:"
systemctl status us-api.service --no-pager || true

echo ""
echo "=========================================="
echo "✅ Installation Complete!"
echo "=========================================="
echo ""
echo "Service Management Commands:"
echo "  Start:   sudo systemctl start us-api"
echo "  Stop:    sudo systemctl stop us-api"
echo "  Restart: sudo systemctl restart us-api"
echo "  Status:  sudo systemctl status us-api"
echo "  Logs:    sudo journalctl -u us-api -f"
echo ""
echo "API Endpoints:"
echo "  Health Check: http://localhost:5667/api/health"
echo "  Create Report: POST http://localhost:5667/api/us/report"
echo "  Get Reports: GET http://localhost:5667/api/us/report/<mrn>"
echo ""
