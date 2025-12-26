#!/usr/bin/env python3
"""
Script de Testing para Bone Density (BD) Pixel Map Processing

Verifica que la extracción de pixel maps BD sea correcta
"""

import sys
from pathlib import Path
import pydicom
import numpy as np
from PIL import Image

def test_bd_extraction():
    """
    Prueba la extracción de pixel map de un archivo BD
    """
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║  TESTING: Bone Density (BD) Pixel Map Extraction" + " " * 30 + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "═" * 78 + "╝")
    
    # Cargar archivo BD
    test_file = Path("/home/ubuntu/DICOMReceiver/test_bone_density.dcm")
    
    if not test_file.exists():
        print(f"✗ Archivo no encontrado: {test_file}")
        return False
    
    print(f"\n1. Leyendo archivo DICOM: {test_file.name}")
    ds = pydicom.dcmread(str(test_file), force=True)
    
    # Verificar propiedades
    print("\n2. Propiedades DICOM:")
    tests = [
        ("Modalidad", ds.get('Modality', 'N/A'), 'BD'),
        ("PhotometricInterpretation", ds.get('PhotometricInterpretation', 'N/A'), 'RGB'),
        ("SamplesPerPixel", int(ds.get('SamplesPerPixel', 0)), 3),
        ("Rows", int(ds.get('Rows', 0)), 1620),
        ("Columns", int(ds.get('Columns', 0)), 1440),
        ("BitsAllocated", int(ds.get('BitsAllocated', 0)), 8),
    ]
    
    all_passed = True
    for name, actual, expected in tests:
        status = "✓" if actual == expected else "✗"
        print(f"   {status} {name}: {actual} (esperado: {expected})")
        if actual != expected:
            all_passed = False
    
    # Verificar pixel array
    print("\n3. Pixel Array:")
    px = ds.pixel_array
    print(f"   Shape: {px.shape}")
    print(f"   Dtype: {px.dtype}")
    print(f"   Rango: min={px.min()}, max={px.max()}")
    print(f"   Media: {px.mean():.2f}")
    
    if px.dtype != np.uint8 or px.shape != (1620, 1440, 3):
        print(f"   ✗ Propiedades de pixel array incorrectas")
        all_passed = False
    else:
        print(f"   ✓ Pixel array válido")
    
    # Probar normalización
    print("\n4. Probando normalización:")
    
    # Importar función de normalización
    import sys
    sys.path.insert(0, '/home/ubuntu/DICOMReceiver')
    from main import normalize_pixel_array
    
    normalized = normalize_pixel_array(px, is_color=True)
    
    print(f"   Entrada: dtype={px.dtype}, min={px.min()}, max={px.max()}")
    print(f"   Salida: dtype={normalized.dtype}, min={normalized.min()}, max={normalized.max()}")
    
    if not np.array_equal(px, normalized):
        print(f"   ⚠ Arrays no son idénticos (esperado: no modificar)")
        # Verificar si la diferencia es mínima
        diff = np.abs(px.astype(float) - normalized.astype(float)).max()
        if diff == 0:
            print(f"   ✓ Diferencia: 0 (perfecto)")
        else:
            print(f"   ✗ Diferencia: {diff}")
            all_passed = False
    else:
        print(f"   ✓ Perfecto: no modificados (ya están en 0-255)")
    
    # Probar creación de JPEG
    print("\n5. Generando JPEG:")
    try:
        image = Image.fromarray(normalized, mode='RGB')
        test_output = Path("/tmp/test_bd_output.jpg")
        image.save(str(test_output), 'JPEG', quality=95)
        
        print(f"   ✓ JPEG creado: {test_output}")
        print(f"   Modo: {image.mode}")
        print(f"   Tamaño: {image.size}")
        
        # Verificar que se puede releer
        test_img = Image.open(test_output)
        print(f"   ✓ JPEG válido y relocalizable")
        
    except Exception as e:
        print(f"   ✗ Error creando JPEG: {e}")
        all_passed = False
    
    # Resultado final
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ TODOS LOS TESTS PASARON")
        return True
    else:
        print("✗ ALGUNOS TESTS FALLARON")
        return False

if __name__ == "__main__":
    success = test_bd_extraction()
    sys.exit(0 if success else 1)
