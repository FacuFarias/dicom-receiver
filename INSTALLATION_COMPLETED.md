# ✓ DICOM Receiver Service - Installation Completed

## Current Status

The **DICOM Receiver** service is **running and operational** ✅

```
Loaded: loaded (/etc/systemd/system/dicom-receiver.service; enabled)
Active: active (running) since Wed 2025-12-24 14:26:11 UTC
Memory: 24.8M
Port: 5665
```

---

## 🚀 Quick Commands

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

### Check current status
```bash
sudo systemctl status dicom-receiver
```

### View real-time logs
```bash
sudo journalctl -u dicom-receiver -f
```

### View last 50 logs
```bash
sudo journalctl -u dicom-receiver -n 50
```

---

## 📊 Service Information

**Service file:** `/etc/systemd/system/dicom-receiver.service`

**User:** ubuntu

**Working directory:** `/home/ubuntu/DICOMReceiver`

**Executable:** `/home/ubuntu/DICOMReceiver/venv/bin/python /home/ubuntu/DICOMReceiver/main.py`

**Port:** 5665 (DICOM)

**AET (Application Entity Title):** `DICOM_RECEIVER`

**Storage directory:** `/home/ubuntu/DICOMReceiver/dicom_storage/`

---

## 🔧 Configuration

The service runs automatically on system startup (enabled).

To disable auto-start:
```bash
sudo systemctl disable dicom-receiver
```

To enable again:
```bash
sudo systemctl enable dicom-receiver
```

---

## 📝 Supported DICOM Services

The server supports the following types of DICOM images:

- ✅ CT (Computed Tomography)
- ✅ MR (Magnetic Resonance)
- ✅ US (Ultrasound)
- ✅ XRA (X-Ray)
- ✅ CR (Computed Radiography)
- ✅ DX (Digital Radiography)
- ✅ MG (Mammography)

---

## 📤 Sending DICOM Images

### Option 1: With DCMTK
```bash
# Install DCMTK (if not already installed)
sudo apt-get install dcmtk

# Send an image
storescu -aet CLIENT_AET -aec DICOM_RECEIVER localhost 5665 imagen.dcm
```

### Option 2: With Python
```bash
cd /home/ubuntu/DICOMReceiver
source venv/bin/activate
python test.py send imagen.dcm
```

### Option 3: Programmatically with Python
```python
from pynetdicom import AE

ae = AE(ae_title='MY_CLIENT')
ae.add_requested_context('1.2.840.10008.5.1.4.1.1.2')  # CT Storage

assoc = ae.associate('localhost', 5665, ae_title='DICOM_RECEIVER')
if assoc.is_established:
    assoc.send_c_store('imagen.dcm')
    assoc.release()
```

---

## 📂 Storage Structure

DICOM files are automatically organized in:

```
dicom_storage/
├── PATIENT_ID_1/
│   ├── STUDY_UID_1/
│   │   ├── CT_20251224_142611_000_1.2.840...dcm
│   │   └── CT_20251224_142612_000_1.2.840...dcm
│   └── STUDY_UID_2/
│       └── MR_20251224_143000_000_1.2.840...dcm
└── PATIENT_ID_2/
    └── STUDY_UID_3/
        └── US_20251224_144000_000_1.2.840...dcm
```

---

## 🔍 Monitoring

### Verify that the service is running
```bash
sudo systemctl is-active dicom-receiver
```

### View the process PID
```bash
sudo systemctl show -p MainPID dicom-receiver
```

### Check resource usage
```bash
ps aux | grep "dicom-receiver" | grep -v grep
```

### View active ports
```bash
sudo lsof -i :5665
```

---

## 🆘 Troubleshooting

### Service won't start
```bash
sudo journalctl -u dicom-receiver -n 30
```

### Service consuming too much memory
Review logs for errors and consider restarting:
```bash
sudo systemctl restart dicom-receiver
```

### Change the port
Edit `/home/ubuntu/DICOMReceiver/config.py`:
```python
DICOM_SERVER = {
    'port': 104,  # Change here
    ...
}
```

Then restart:
```bash
sudo systemctl restart dicom-receiver
```

---

## 📚 Complete Documentation

For detailed information about service management, see:
- [SERVICE.md](SERVICE.md) - Complete systemd service guide
- [README.md](README.md) - General DICOM Receiver documentation

---

## ✅ Final Verification

To confirm everything is working:

```bash
# 1. Verify the service is running
sudo systemctl status dicom-receiver

# 2. Verify it's listening on port 5665
sudo lsof -i :5665

# 3. View service logs
sudo journalctl -u dicom-receiver -n 10
```

**If you see these results, your DICOM service is ready to receive images!** 🎉

---

Last updated: December 24, 2025
