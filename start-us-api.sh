#!/bin/bash
# Start US Reports API in foreground (for development/testing)

echo "=========================================="
echo "Starting US Reports API Service"
echo "=========================================="
echo ""
echo "API will be available at: http://localhost:5667"
echo "Press Ctrl+C to stop"
echo ""
echo "Endpoints:"
echo "  POST /api/us/report - Submit US report"
echo "  GET  /api/us/report/<mrn> - Get reports by MRN"
echo "  GET  /api/health - Health check"
echo ""
echo "=========================================="
echo ""

cd /home/ubuntu/DICOMReceiver
python3 us_api.py
