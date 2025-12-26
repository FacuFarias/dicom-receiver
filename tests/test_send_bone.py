#!/usr/bin/env python3
"""Test C-STORE of bone density image with detailed logging"""

from pynetdicom import AE
from pynetdicom.sop_class import SecondaryCaptureImageStorage
from pydicom import dcmread
from pydicom.uid import JPEG2000Lossless, ExplicitVRLittleEndian
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Read the image
ds = dcmread('/home/ubuntu/DICOMReceiver/test_bone_density.dcm')
print(f"\nFile info:")
print(f"  SOP Class: {ds.SOPClassUID}")
print(f"  Transfer Syntax: {ds.file_meta.TransferSyntaxUID}")
print(f"  Modality: {getattr(ds, 'Modality', 'UNKNOWN')}")

# Create client AE
ae = AE(ae_title="ECHO_CLIENT")

# Add Secondary Capture context with the same transfer syntaxes as the server
ae.add_requested_context(SecondaryCaptureImageStorage, [
    ExplicitVRLittleEndian,
    JPEG2000Lossless
])

# Request association
print(f"\nRequesting association...")
assoc = ae.associate('localhost', 5665, ae_title='DICOM_RECEIVER')

if assoc.is_established:
    print(f"✓ Association established!")
    print(f"Accepted contexts: {len(assoc.accepted_contexts)}")
    for context in assoc.accepted_contexts:
        print(f"  - {context.abstract_syntax.name}: {context.transfer_syntax}")
    
    # Try to send
    print(f"\nSending DICOM...")
    status_ds = assoc.send_c_store(ds)
    print(f"C-STORE returned: {status_ds}")
    if hasattr(status_ds, 'Status'):
        print(f"C-STORE Status: 0x{status_ds.Status:04X}")
    
    assoc.release()
    print(f"Association released")
else:
    print(f"✗ Failed to establish association")
    print(f"Association rejected reason: {assoc.assoc_rj_reason}")

ae.shutdown()
