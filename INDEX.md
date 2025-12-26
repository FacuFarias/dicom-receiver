# DICOM Receiver Service - Complete Documentation Index

This is your complete DICOM Receiver Service, fully translated to English. Below is an index of all documentation and files.

## 📚 Documentation Files

### [README.md](README.md)
- **Purpose:** General project documentation
- **Content:** 
  - Project overview
  - Installation instructions
  - Features and capabilities
  - DICOM image sending methods
  - Troubleshooting guide
  - Security notes

### [SERVICE.md](SERVICE.md)
- **Purpose:** Complete systemd service management guide
- **Content:**
  - Service installation and setup
  - Basic commands (start, stop, restart, pause)
  - Viewing logs in real-time
  - Uninstallation procedures
  - Troubleshooting common issues
  - Technical information about the service
  - Usage examples

### [INSTALLATION_COMPLETED.md](INSTALLATION_COMPLETED.md)
- **Purpose:** Quick reference for installed service
- **Content:**
  - Current service status
  - Quick command reference
  - Service information
  - Next steps
  - Monitoring instructions

---

## 🐍 Source Code Files

### [main.py](main.py)
- **Purpose:** Main DICOM C-STORE server implementation
- **Features:**
  - DICOM association handling
  - File storage management
  - Event handlers for C-STORE operations
  - Automatic directory structure creation
  - Logging and error handling

### [config.py](config.py)
- **Purpose:** Configuration parameters
- **Configurable:**
  - Server host and port
  - Storage location
  - Logging settings
  - Validation rules
  - Client filtering
  - File size limits

### [test.py](test.py)
- **Purpose:** Test script for DICOM operations
- **Features:**
  - Connection testing to DICOM server
  - Send DICOM files via C-STORE
  - Validate DICOM file format
  - Display detailed file information

---

## 📋 Installation & Setup Files

### [install-service.sh](install-service.sh)
- **Purpose:** Automated service installation script
- **What it does:**
  - Creates systemd service file
  - Enables auto-start on boot
  - Validates virtual environment
  - Provides command reference

### [start.sh](start.sh)
- **Purpose:** Manual service startup script
- **What it does:**
  - Activates Python virtual environment
  - Starts DICOM server on port 5665

### [dicom-receiver.service](dicom-receiver.service)
- **Purpose:** Systemd service configuration
- **Contains:**
  - Service definition
  - Startup configuration
  - Environment variables
  - Restart policies

### [requirements.txt](requirements.txt)
- **Purpose:** Python package dependencies
- **Packages:**
  - `pydicom` - DICOM file handling
  - `pynetdicom` - DICOM network protocol

---

## 📂 Directory Structure

```
DICOMReceiver/
├── README.md                    # Main documentation
├── SERVICE.md                   # Service management guide
├── INSTALLATION_COMPLETED.md    # Quick reference
├── INDEX.md                     # This file
│
├── main.py                      # Main server code
├── config.py                    # Configuration
├── test.py                      # Test script
│
├── start.sh                     # Manual startup
├── install-service.sh           # Service installer
├── dicom-receiver.service       # Service config
│
├── requirements.txt             # Dependencies
├── .gitignore                   # Git ignore rules
│
├── venv/                        # Python virtual environment
└── dicom_storage/               # DICOM files storage
```

---

## 🚀 Quick Start

### 1. View Current Service Status
```bash
sudo systemctl status dicom-receiver
```

### 2. View Service Logs
```bash
sudo journalctl -u dicom-receiver -f
```

### 3. Send a DICOM Image (if you have one)
```bash
python /home/ubuntu/DICOMReceiver/test.py send /path/to/image.dcm
```

### 4. Test Connection
```bash
python /home/ubuntu/DICOMReceiver/test.py test-connection
```

---

## 📖 Documentation Sections

### For Service Management
- Read **[SERVICE.md](SERVICE.md)** for:
  - Starting/stopping the service
  - Viewing logs
  - Troubleshooting
  - Configuration changes

### For First-Time Setup
- Read **[README.md](README.md)** for:
  - System requirements
  - Installation steps
  - Feature overview
  - Sending DICOM images

### For Quick Reference
- Read **[INSTALLATION_COMPLETED.md](INSTALLATION_COMPLETED.md)** for:
  - Service status
  - Common commands
  - Next steps

---

## 🎯 Common Tasks

### Check if service is running
```bash
sudo systemctl status dicom-receiver
```

### Start the service
```bash
sudo systemctl start dicom-receiver
```

### Stop the service
```bash
sudo systemctl stop dicom-receiver
```

### Restart the service
```bash
sudo systemctl restart dicom-receiver
```

### View real-time logs
```bash
sudo journalctl -u dicom-receiver -f
```

### View last 50 log entries
```bash
sudo journalctl -u dicom-receiver -n 50
```

### Send a DICOM file
```bash
cd /home/ubuntu/DICOMReceiver
source venv/bin/activate
python test.py send image.dcm
```

### List all stored DICOM files
```bash
find /home/ubuntu/DICOMReceiver/dicom_storage -name "*.dcm"
```

---

## 🔧 Configuration

The service can be configured by editing:

1. **Port and Server Settings** → `config.py`
2. **Storage Location** → `config.py`
3. **Logging Level** → `config.py`
4. **Systemd Behavior** → `dicom-receiver.service`

### Change Port
Edit `config.py`:
```python
DICOM_SERVER = {
    'port': 104,  # Change from 5665 to 104
    ...
}
```

Then restart:
```bash
sudo systemctl restart dicom-receiver
```

---

## 🔍 Support & Troubleshooting

### Service won't start?
```bash
sudo journalctl -u dicom-receiver -n 20
```
See **[SERVICE.md](SERVICE.md)** for detailed troubleshooting.

### Port already in use?
```bash
sudo lsof -i :5665
```

### Need to uninstall?
See "Uninstall" section in **[SERVICE.md](SERVICE.md)**

---

## 📞 Service Information

- **Status:** Active and running
- **Port:** 5665 (DICOM protocol)
- **AET:** DICOM_RECEIVER
- **Storage:** `/home/ubuntu/DICOMReceiver/dicom_storage/`
- **User:** ubuntu
- **Auto-start:** Enabled

---

## ✅ Next Steps

1. **Verify the service is running:**
   ```bash
   sudo systemctl status dicom-receiver
   ```

2. **Send a test DICOM image (if available):**
   ```bash
   python test.py send test_image.dcm
   ```

3. **Monitor the logs:**
   ```bash
   sudo journalctl -u dicom-receiver -f
   ```

4. **Read the full documentation:**
   - Start with [README.md](README.md)
   - Then read [SERVICE.md](SERVICE.md)

---

**Last Updated:** December 24, 2025

**Language:** English

**Status:** Fully Translated ✅
