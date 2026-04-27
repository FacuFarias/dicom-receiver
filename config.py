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
    'enabled': True,
    'aets': [
        # 'CLIENT_AET',
        # 'ANOTHER_CLIENT',
    ]
}

# Maximum file size (in MB, 0 = no limit)
MAX_FILE_SIZE_MB = 0

# Automatic cleanup configuration
AUTO_CLEANUP = {
    'enabled': True,
    'bd_retention_hours': 24,   # BD files: 24 hours retention
    'us_retention_hours': 3,    # US files: 3 hours retention
    'other_retention_days': 30, # Other files: 30 days retention
    'max_storage_gb': 15,       # Maximum storage size in GB
}

# US Forwarding configuration
# Automatically forward US studies to external DICOM server based on criteria
US_FORWARDING = {
    'enabled': True,                      # Enable/disable US forwarding
    'host': '3.148.99.29',                # Destination DICOM server IP
    'port': 11112,                        # Destination DICOM server port
    'aet': 'QII_AI_RECEIVER',             # Destination AE Title
    'calling_aet': 'QII_DICOM_SENDER',    # Our AE Title when sending
    'timeout': 30,                        # Connection timeout in seconds
    'retry_attempts': 3,                  # Number of retry attempts on failure
    
    # Forwarding criteria (all conditions are OR-based)
    'criteria': {
        'study_description_contains': ['Thyroid', 'Testicular', 'Liver', 'Hepatic', 'Carotid', 'Abdomen', 'Abdominal'],  # Forward if StudyDescription contains any of these terms (case-insensitive)
        'body_part_contains': ['Thyroid', 'Testis', 'Testicular', 'Scrotum', 'Liver', 'Hepatic', 'Carotid', 'Abdomen', 'Abdominal'],  # Forward if BodyPartExamined contains any of these terms
        'series_description_contains': ['Thyroid', 'Testicular', 'Liver', 'Hepatic', 'Carotid', 'Abdomen', 'Abdominal'],  # Forward if SeriesDescription contains any of these terms
    }
}

# Async Processing configuration
# High-performance mode: accept DICOM immediately, process in background
ASYNC_PROCESSING = {
    'enabled': True,                   # FEATURE FLAG: Set to True to enable async processing
                                       # When False, uses legacy synchronous processing
    'us_workers': 4,                   # Number of concurrent US forwarding workers (aumentado para aprovechar RAM)
    'bd_workers': 6,                   # Number of concurrent BD processing workers (aumentado para aprovechar RAM)
    'pixel_workers': 3,                # Number of concurrent pixel extraction workers (aumentado para aprovechar RAM)
    'queue_monitor_interval': 30,      # Seconds between queue monitoring and stats logging
    'max_queue_size': 1000,            # Maximum items per queue (hard limit)
    'alert_threshold': 800,            # Log warning when queue reaches this size
    'degradation_threshold': 950,      # Switch to sync mode temporarily if queue exceeds this
    'stats_interval': 30,              # Log performance stats every N seconds
    
    # Reception Priority Mode - Defer processing until study reception completes
    'defer_processing': True,          # PRIORIDAD: Recibir primero, procesar después
                                       # True: Solo recibir durante transmisión activa, procesar cuando termine
                                       # False: Procesar mientras se recibe (modo anterior)
    'study_completion_timeout': 8,     # Segundos sin recibir instancias para considerar estudio completo
                                       # Recomendado: 5-10 segundos (ajustar según red)
    'defer_check_interval': 3,         # Segundos entre verificaciones de estudios completos
}

# Performance configuration
PERFORMANCE = {
    'immediate_response_mode': True,   # Return C-STORE-RSP immediately after disk write
                                       # When True, all heavy processing happens in background
    'log_per_instance': False,         # Log every instance at INFO level (verbose)
                                       # When False, uses DEBUG for per-instance logs
}

