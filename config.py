"""
DICOM Server Configuration
Modify parameters according to your needs
"""

# DICOM Server configuration
DICOM_SERVER = {
    'host': '0.0.0.0',        # Interface to listen on (0.0.0.0 = all)
    'port': 5665,             # DICOM port (default is 104)
    'aet': 'DICOM_RECEIVER',  # Server Application Entity Title
}

# Storage configuration
STORAGE = {
    'base_path': './dicom_storage',  # Base directory for storing DICOMs
    'auto_create_dirs': True,        # Create directories automatically
    'organize_by': 'patient_study',  # Organization: 'patient_study' or 'flat'
}

# Logging configuration
LOGGING = {
    'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': None,  # Change to 'dicom_receiver.log' to save to file
}

# Validation configuration
VALIDATION = {
    'check_dicom': True,           # Validate that it's a valid DICOM
    'require_patient_id': False,   # Require Patient ID (reject without ID if True)
    'require_study_uid': False,    # Require Study Instance UID
}

# Allowed clients configuration (leave empty to allow all)
ALLOWED_CLIENTS = {
    'enabled': False,
    'aets': [
        # 'CLIENT_AET',
        # 'ANOTHER_CLIENT',
    ]
}

# Maximum file size (in MB, 0 = no limit)
MAX_FILE_SIZE_MB = 0

# Automatic cleanup configuration
AUTO_CLEANUP = {
    'enabled': False,
    'max_age_days': 30,  # Delete files older than this
}
