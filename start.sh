#!/bin/bash

# Script to start the DICOM Receiver service

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================"
echo "DICOM Receiver Service"
echo "================================"
echo ""

# Activate virtual environment
if [ -d "$SCRIPT_DIR/venv" ]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "Error: Virtual environment not found."
    echo "Please run: python3 -m venv venv"
    exit 1
fi

echo "Starting service on port 5665..."
echo "Documentation available at: http://localhost:5665/docs"
echo ""
echo "Press Ctrl+C to stop the service"
echo ""

cd "$SCRIPT_DIR"
python main.py
