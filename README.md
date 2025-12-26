# DICOM Receiver Service - C-STORE Server

**Version 1.0.0** (Stable)

Professional-grade DICOM server that receives medical images via C-STORE protocol. Designed for integration with PACS systems for AI-powered image post-processing workflows.

## Features

✓ **C-STORE Protocol** - Receives DICOM files on port 5665  
✓ **Multiple Modalities** - CT, MR, X-Ray, Ultrasound, Secondary Capture, and more  
✓ **Advanced Compression** - Supports JPEG 2000 Lossless, Explicit/Implicit VR  
✓ **Automatic Organization** - Files stored in PatientID/StudyInstanceUID hierarchy  
✓ **Systemd Integration** - Auto-restart service management  
✓ **Comprehensive Logging** - Detailed operation tracking  
✓ **Production Ready** - Tested with real DICOM files  

## Technology Stack

- **Runtime**: Python 3.12
- **DICOM Protocol**: pynetdicom 2.1.0
- **DICOM Toolkit**: pydicom 2.4.4
- **Service Manager**: systemd

## System Requirements

- Python 3.8+
- Linux (systemd-based distribution)
- ~50MB disk for dependencies
- TCP port 5665 available

## Installation

1. Clone or download the project
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Start the service

```bash
python main.py
```

Or using the provided script:

```bash
./start.sh
```

The DICOM server will listen on `0.0.0.0:5665` with the Application Entity Title (AET): `DICOM_RECEIVER`

## Features

- ✅ **DICOM C-STORE Protocol**: Receives DICOM images through the standard DICOM protocol
- ✅ **Port 5665**: Configurable for any port
- ✅ **Organized Storage**: Structure by Patient → Study → File
- ✅ **Automatic Validation**: Verifies that files are valid DICOM
- ✅ **Detailed Logging**: Logs all operations
- ✅ **Support for All Modalities**: CT, MR, XC, US, etc.

## Storage Structure

```
dicom_storage/
├── PAT001/
│   ├── 1.2.3.4.5/
│   │   ├── CT_20251224_103045_000_1.2.840.10008.5.1.4.1.1.2.dcm
│   │   └── CT_20251224_103046_000_1.2.840.10008.5.1.4.1.1.2.dcm
│   └── 1.2.3.4.6/
│       └── MR_20251224_104000_000_1.2.840.10008.5.1.4.1.1.4.dcm
└── PAT002/
    └── 1.2.4.5.6/
        └── XC_20251224_105000_000_1.2.840.10008.5.1.4.1.1.12.dcm
```

## Configuration

### Change listening port

Edit `main.py` and modify the `start_server()` function:

```python
start_server(host="0.0.0.0", port=104, aet="DICOM_RECEIVER")
```

### Change Application Entity Title (AET)

```python
start_server(host="0.0.0.0", port=5665, aet="MY_SERVER")
```

## Sending DICOM images

### Using DCMTK (command-line tool)

```bash
# Install DCMTK if you don't have it
# Ubuntu/Debian: sudo apt-get install dcmtk
# macOS: brew install dcmtk

# Send a DICOM file
storescu -aet CLIENT_AET -aec DICOM_RECEIVER localhost 5665 imagen.dcm
```

### Using pydicom and pynetdicom (Python)

```python
from pynetdicom import AE

ae = AE(ae_title='CLIENT_AET')
ae.add_requested_context('1.2.840.10008.5.1.4.1.1.2')  # CT Storage

# Connect and send
assoc = ae.associate('localhost', 5665, ae_title='DICOM_RECEIVER')
if assoc.is_established:
    assoc.send_c_store('imagen.dcm')
    assoc.release()
```

## Logging

The service generates detailed logs with information about:

- DICOM connections received
- DICOM files processed
- Patient and study information
- Errors and exceptions

Example log:

```
2025-12-24 10:30:45,123 - __main__ - INFO - Association received from 192.168.1.100:50123
2025-12-24 10:30:46,456 - __main__ - INFO - DICOM stored - Patient: PAT001, Study: 1.2.3.4.5, File: CT_20251224_103046_000_1.2.840.10008.5.1.4.1.1.2.dcm
```

## Supported DICOM Services

The server supports all Storage (C-STORE) services including:

- **CT** - Computed Tomography Storage
- **MR** - Magnetic Resonance Storage
- **US** - Ultrasound Image Storage
- **XC** - X-Ray Angiographic Image Storage
- **CR** - Computed Radiography Image Storage
- And more than 100 additional DICOM classes

## Monitor files

To view the stored files:

```bash
# List all DICOM files
find dicom_storage -name "*.dcm"

# Count total files
find dicom_storage -name "*.dcm" | wc -l

# View info of a DICOM file
python3 -c "import pydicom; ds = pydicom.dcmread('path/to/file.dcm'); print(ds)"
```

## Troubleshooting

### Server is not receiving connections

1. Verify that port 5665 is available:
   ```bash
   lsof -i :5665
   ```

2. Check the firewall:
   ```bash
   sudo ufw allow 5665/tcp
   ```

3. Make sure the server is running and listening:
   ```bash
   netstat -tlnp | grep 5665
   ```

### Error: "Address already in use"

Port 5665 is already in use. Change the port in `main.py` or kill the process:

```bash
# Find and kill the process
lsof -i :5665 | awk 'NR!=1 {print $2}' | xargs kill -9
```

### Files are not being saved

Check directory permissions:

```bash
ls -la dicom_storage/
chmod 755 dicom_storage/
```

## Security Notes

For production, consider:

- ✅ Implementing TLS/HTTPS DICOM authentication
- ✅ Configuring client validation (AET)
- ✅ Implementing data backup
- ✅ Configuring file size limits
- ✅ Monitoring disk usage
- ✅ Implementing data retention policies
- ✅ Auditing file access

## License

This project is provided as-is.
