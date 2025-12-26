# DICOM Receiver Service - Complete Guide

This document explains how to install, manage, and maintain the DICOM server as a systemd service on Linux.

## Table of Contents

1. [Service Installation](#service-installation)
2. [Basic Commands](#basic-commands)
3. [View Logs](#view-logs)
4. [Uninstall](#uninstall)
5. [Troubleshooting](#troubleshooting)
6. [Technical Information](#technical-information)

---

## Service Installation

### Prerequisites

1. Make sure you have Python and pip installed
2. The virtual environment must be created with dependencies installed:

```bash
cd /home/ubuntu/DICOMReceiver
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. You must have `sudo` access to install the service

### Installation Steps

#### Step 1: Run the installer

```bash
cd /home/ubuntu/DICOMReceiver
sudo bash install-service.sh
```

This script:
- ✓ Validates that the virtual environment exists
- ✓ Copies the service file to `/etc/systemd/system/`
- ✓ Reloads the systemd daemon
- ✓ Enables the service to auto-start on boot

#### Step 2: Verify the installation

```bash
sudo systemctl status dicom-receiver
```

You should see something like:
```
● dicom-receiver.service - DICOM Receiver Service - C-STORE Server
     Loaded: loaded (/etc/systemd/system/dicom-receiver.service; enabled; vendor preset: enabled)
     Active: inactive (dead)
```

---

## Basic Commands

### Start the Service

```bash
sudo systemctl start dicom-receiver
```

Verify it's running:
```bash
sudo systemctl status dicom-receiver
```

You should see `Active: active (running)` in green.

### Stop the Service

```bash
sudo systemctl stop dicom-receiver
```

The service will stop immediately. Active DICOM processes will be terminated.

### Restart the Service

```bash
sudo systemctl restart dicom-receiver
```

Useful for reloading configuration changes or after updating code.

### Pause the Service

```bash
sudo systemctl pause dicom-receiver
```

Pauses the service temporarily without stopping it. To resume:

```bash
sudo systemctl resume dicom-receiver
```

### Check Status in Real-Time

```bash
sudo systemctl status dicom-receiver
```

Example output:
```
● dicom-receiver.service - DICOM Receiver Service - C-STORE Server
     Loaded: loaded (/etc/systemd/system/dicom-receiver.service; enabled)
     Active: active (running) since Tue 2025-12-24 10:30:45 UTC; 2h 15min ago
   Main PID: 1234 (python)
      Tasks: 1 (limit: 512)
     Memory: 45.2M
     CGroup: /system.slice/dicom-receiver.service
             └─1234 /home/ubuntu/DICOMReceiver/venv/bin/python /home/ubuntu/DICOMReceiver/main.py
```

### Enable/Disable Auto-Start

By default, the service auto-starts on boot. To change this:

**Disable auto-start (don't start on boot):**
```bash
sudo systemctl disable dicom-receiver
```

**Enable auto-start (start on boot):**
```bash
sudo systemctl enable dicom-receiver
```

---

## View Logs

### Real-Time Logs

View the latest logs as they're generated:

```bash
sudo journalctl -u dicom-receiver -f
```

Press `Ctrl+C` to exit.

### View Last N Logs

View the last 50 logs:
```bash
sudo journalctl -u dicom-receiver -n 50
```

View the last 100 logs:
```bash
sudo journalctl -u dicom-receiver -n 100
```

### Filter Logs by Severity Level

View only errors:
```bash
sudo journalctl -u dicom-receiver -p err
```

Available levels:
- `emerg` - Emergency
- `alert` - Alert
- `crit` - Critical
- `err` - Error
- `warning` - Warning
- `notice` - Notice
- `info` - Information
- `debug` - Debug

### Logs from Specific Date/Time

View logs from the last 2 hours:
```bash
sudo journalctl -u dicom-receiver --since "2 hours ago"
```

View logs from a specific time:
```bash
sudo journalctl -u dicom-receiver --since "2025-12-24 10:00:00"
```

### Save Logs to File

```bash
sudo journalctl -u dicom-receiver -n 1000 > dicom-logs.txt
```

---

## Uninstall

If you need to uninstall the service:

```bash
# 1. Stop the service
sudo systemctl stop dicom-receiver

# 2. Disable on boot
sudo systemctl disable dicom-receiver

# 3. Remove the service file
sudo rm /etc/systemd/system/dicom-receiver.service

# 4. Reload systemd
sudo systemctl daemon-reload

# 5. Verify it was removed
sudo systemctl list-unit-files | grep dicom-receiver
```

The DICOM files stored in `dicom_storage/` **will NOT be deleted**.

---

## Troubleshooting

### Service won't start

**Check status:**
```bash
sudo systemctl status dicom-receiver
```

**View full error:**
```bash
sudo journalctl -u dicom-receiver -n 20
```

**Common causes:**

1. **Port 5665 already in use:**
   ```bash
   sudo lsof -i :5665
   ```
   
   Solution: Change the port in `config.py` or kill the process:
   ```bash
   sudo kill -9 <PID>
   ```

2. **Corrupted virtual environment:**
   ```bash
   cd /home/ubuntu/DICOMReceiver
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   sudo systemctl restart dicom-receiver
   ```

3. **Directory permissions:**
   ```bash
   sudo chown -R ubuntu:ubuntu /home/ubuntu/DICOMReceiver
   sudo chmod -R 755 /home/ubuntu/DICOMReceiver
   ```

### Service uses too much memory

Review logs and consider:
- Reducing the number of simultaneous connections
- Implementing file size limits
- Cleaning up old files regularly

```bash
sudo journalctl -u dicom-receiver --since "1 hour ago"
```

### DICOM images not being saved

1. Check directory permissions:
   ```bash
   ls -la /home/ubuntu/DICOMReceiver/dicom_storage/
   ```

2. Verify the service is running:
   ```bash
   sudo systemctl status dicom-receiver
   ```

3. Check logs for errors:
   ```bash
   sudo journalctl -u dicom-receiver -f
   ```

---

## Technical Information

### Service File

The service file is located at:
```
/etc/systemd/system/dicom-receiver.service
```

You can edit it manually if needed:
```bash
sudo nano /etc/systemd/system/dicom-receiver.service
```

After editing, reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart dicom-receiver
```

### Service Configuration

The service includes:

- **Type=simple**: Simple process running in foreground
- **Restart=on-failure**: Auto-restart on failure
- **RestartSec=10**: Wait 10 seconds before retrying
- **StandardOutput=journal**: Logs to systemd journal
- **TimeoutStartSec=30**: 30-second timeout for startup

### Environment Variables

If you need to pass environment variables, edit the service file:

```bash
sudo nano /etc/systemd/system/dicom-receiver.service
```

Add an `Environment` line in the `[Service]` section:

```ini
Environment="FLASK_ENV=production"
Environment="LOG_LEVEL=DEBUG"
```

### Data Directory

DICOM files are stored in:
```
/home/ubuntu/DICOMReceiver/dicom_storage/
```

To change the location, edit `config.py`:

```python
STORAGE = {
    'base_path': '/custom/path/dicom_storage',
    ...
}
```

### View All Services

To see all services status:
```bash
sudo systemctl list-units --type=service
```

To see only running services:
```bash
sudo systemctl list-units --type=service --state=running
```

---

## Complete Usage Examples

### Example 1: Install and verify

```bash
# 1. Install
cd /home/ubuntu/DICOMReceiver
sudo bash install-service.sh

# 2. Start
sudo systemctl start dicom-receiver

# 3. Verify
sudo systemctl status dicom-receiver

# 4. View logs
sudo journalctl -u dicom-receiver -f
```

### Example 2: Update code and restart

```bash
# 1. Update code (your favorite editor)
nano main.py

# 2. Restart service
sudo systemctl restart dicom-receiver

# 3. Verify it's running
sudo systemctl status dicom-receiver
```

### Example 3: Real-time monitoring

```bash
# Terminal 1: Watch status
watch -n 1 'systemctl status dicom-receiver'

# Terminal 2: View logs
sudo journalctl -u dicom-receiver -f
```

### Example 4: Schedule tasks with cron

Check status every 5 minutes:
```bash
*/5 * * * * systemctl is-active dicom-receiver || systemctl start dicom-receiver
```

---

## Command Summary

| Command | Description |
|---------|-------------|
| `sudo systemctl start dicom-receiver` | Start service |
| `sudo systemctl stop dicom-receiver` | Stop service |
| `sudo systemctl restart dicom-receiver` | Restart service |
| `sudo systemctl pause dicom-receiver` | Pause service |
| `sudo systemctl resume dicom-receiver` | Resume service |
| `sudo systemctl status dicom-receiver` | View status |
| `sudo systemctl enable dicom-receiver` | Enable on boot |
| `sudo systemctl disable dicom-receiver` | Disable on boot |
| `sudo journalctl -u dicom-receiver -f` | Real-time logs |
| `sudo journalctl -u dicom-receiver -n 50` | Last 50 logs |

---

## Frequently Asked Questions

**Q: Does the service auto-start on boot?**
A: Yes, after installing with `install-service.sh`, the service is enabled automatically.

**Q: Can I change the port?**
A: Yes, edit `config.py` in the `DICOM_SERVER` section and change the port. Then restart with `sudo systemctl restart dicom-receiver`.

**Q: How do I backup DICOM files?**
A: Copy the entire `/home/ubuntu/DICOMReceiver/dicom_storage/` directory to your preferred backup location.

**Q: Can I run multiple instances?**
A: Yes, but you'll need to create multiple service files with different ports and names.

**Q: What user runs the service?**
A: By default, the `ubuntu` user. You can change this in the service file (line `User=ubuntu`).

---

## Support

For more information about systemd:
- [systemctl Manual](https://man7.org/linux/man-pages/man1/systemctl.1.html)
- [journalctl Manual](https://man7.org/linux/man-pages/man1/journalctl.1.html)

