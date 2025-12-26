#!/usr/bin/env python3
"""
Simple C-ECHO test for DICOM server
This is a basic connectivity test without sending files
"""

import sys
from pynetdicom import AE
from pynetdicom.sop_class import Verification


def test_echo(host="localhost", port=5665, aet="DICOM_RECEIVER"):
    """
    Test C-ECHO connectivity to DICOM server
    """
    print("=" * 60)
    print("DICOM C-ECHO Test")
    print("=" * 60)
    print()
    
    try:
        print(f"Connecting to {host}:{port}")
        print(f"Server AET: {aet}")
        print()
        
        # Create AE
        ae = AE(ae_title="ECHO_CLIENT")
        
        # Add Verification context (for C-ECHO)
        ae.add_requested_context(Verification)
        
        # Try to associate
        print("Requesting association...")
        assoc = ae.associate(host, port, ae_title=aet)
        
        if not assoc.is_established:
            print("✗ Association failed!")
            return False
        
        print("✓ Association established")
        print()
        
        # Send C-ECHO
        print("Sending C-ECHO...")
        status = assoc.send_c_echo()
        
        # Extract status code
        status_code = status.get('Status', None) if hasattr(status, 'get') else getattr(status, 'Status', None)
        
        if status_code == 0 or status_code == 0x0000:
            print("✓ C-ECHO successful!")
            print(f"  Status: {status_code}")
        else:
            print("✗ C-ECHO failed!")
            print(f"  Status: {status_code}")
        
        # Release
        assoc.release()
        print()
        print("✓ Association released")
        
        # Extract status code
        status_code = status.get('Status', None) if hasattr(status, 'get') else getattr(status, 'Status', None)
        return status_code == 0 or status_code == 0x0000
    
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5665
    aet = sys.argv[3] if len(sys.argv) > 3 else "DICOM_RECEIVER"
    
    success = test_echo(host, port, aet)
    sys.exit(0 if success else 1)
