#!/usr/bin/env python3
"""
DICOM C-STORE Server using pynetdicom
Simplified version with proper event handling
"""

import logging
from pathlib import Path
import sys
from datetime import datetime

from pynetdicom import AE, events
from pynetdicom.sop_class import (
    CTImageStorage,
    MRImageStorage,
    UltrasoundImageStorage,
    XRayAngiographicImageStorage,
    ComputedRadiographyImageStorage,
    DigitalXRayImageStorageForPresentation,
    DigitalXRayImageStorageForProcessing,
    SecondaryCaptureImageStorage,
    Verification,
)
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    JPEG2000Lossless,
    JPEG2000,
)
import pydicom

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Storage
STORAGE = Path("./dicom_storage")
STORAGE.mkdir(exist_ok=True, parents=True)


def handle_store(event):
    """Handle C-STORE request"""
    try:
        ds = event.dataset
        patient_id = getattr(ds, 'PatientID', 'UNKNOWN')
        study_uid = getattr(ds, 'StudyInstanceUID', 'UNKNOWN')
        modality = getattr(ds, 'Modality', 'UNKNOWN')
        sop_uid = getattr(ds, 'SOPInstanceUID', 'UNKNOWN')
        
        # Ensure file_meta is properly created
        from pydicom.dataset import FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian as EVRL
        
        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
        file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        file_meta.ImplementationClassUID = '1.2.826.0.1.3680043.9.3811.2.1.0'
        file_meta.TransferSyntaxUID = ds.file_meta.TransferSyntaxUID if hasattr(ds, 'file_meta') and hasattr(ds.file_meta, 'TransferSyntaxUID') else EVRL
        
        # Assign file_meta
        ds.file_meta = file_meta
        ds.is_little_endian = True
        ds.is_implicit_VR = (str(file_meta.TransferSyntaxUID) == '1.2.840.10008.1.2')
        
        # Create directory
        patient_dir = STORAGE / str(patient_id)
        study_dir = patient_dir / str(study_uid)
        study_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{modality}_{timestamp}_{sop_uid}.dcm"
        filepath = study_dir / filename
        
        ds.save_as(str(filepath), write_like_original=False)
        logger.info(f"Saved DICOM: {patient_id}/{study_uid}/{filename}")
        
        # Return 0x0000 for success
        return 0x0000
    
    except Exception as e:
        logger.error(f"Error handling C-STORE: {e}", exc_info=True)
        return 0x0110


def handle_release(event):
    """Handle association release"""
    logger.info("Association released")


def handle_requested(event):
    """Handle association request"""
    logger.debug(f"Association requested from {event.assoc.remote_ae.ae_title}")
    # Accept all proposed contexts as-is
    for context in event.assoc.requested_contexts:
        event.assoc.add_negotiated_context(
            context.abstract_syntax,
            context.transfer_syntax
        )


def main():
    """Start server"""
    logger.info("="*70)
    logger.info("DICOM Receiver Service")
    logger.info("="*70)
    
    # Create AE
    ae = AE(ae_title="DICOM_RECEIVER")
    
    # Add contexts with ALL transfer syntaxes (JPEG2000 first)
    all_ts = [JPEG2000Lossless, JPEG2000, ImplicitVRLittleEndian, ExplicitVRLittleEndian]
    
    ae.add_supported_context(CTImageStorage, all_ts)
    ae.add_supported_context(MRImageStorage, all_ts)
    ae.add_supported_context(UltrasoundImageStorage, all_ts)
    ae.add_supported_context(XRayAngiographicImageStorage, all_ts)
    ae.add_supported_context(ComputedRadiographyImageStorage, all_ts)
    ae.add_supported_context(DigitalXRayImageStorageForPresentation, all_ts)
    ae.add_supported_context(DigitalXRayImageStorageForProcessing, all_ts)
    ae.add_supported_context(SecondaryCaptureImageStorage, all_ts)
    ae.add_supported_context(Verification)
    
    # Bind handlers
    handlers = [
        (events.EVT_REQUESTED, handle_requested),
        (events.EVT_C_STORE, handle_store),
        (events.EVT_RELEASED, handle_release),
    ]
    
    logger.info(f"Storage: {STORAGE.absolute()}")
    logger.info(f"Listening on 0.0.0.0:5665")
    logger.info(f"AET: DICOM_RECEIVER")
    logger.info(f"Supported contexts: {len(ae.supported_contexts)}")
    logger.info("="*70)
    
    try:
        ae.start_server(("0.0.0.0", 5665), block=True, evt_handlers=handlers)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
