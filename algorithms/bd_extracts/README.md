# Estructura de Procesamiento BD - DICOMReceiver

## 📂 Organización de Carpetas

```
DICOMReceiver/
├── main.py                          # Servidor DICOM con handle_store refactorizado
├── algorithms/                      # Paquete de algoritmos de procesamiento
│   ├── __init__.py
│   └── bd_extracts/                # Algoritmos específicos de BD
│       ├── __init__.py
│       ├── bd_extract_hologic.py   # Procesamiento HOLOGIC (XML estructurado)
│       └── bd_extract_ge.py        # Procesamiento GE Lunar (OCR - pendiente)
├── dicom_storage/                  # Archivos DICOM recibidos
├── pixel_extraction/               # Imágenes JPEG extraídas
└── logs/                           # Logs de procesamiento
    └── bd_processing.log
```

---

## 🔄 Flujo de Procesamiento en `handle_store()`

### 1. **Recepción DICOM**
- Se recibe archivo via C-STORE
- Se guarda en `dicom_storage/{PatientID}/{StudyInstanceUID}/`

### 2. **Detección de Modalidad**
```python
if modality == 'BD':
    # Procesamiento de Bone Density
```

### 3. **Detección de Fabricante**
```python
manufacturer = ds.Manufacturer.upper()
model = ds.ManufacturerModelName

if 'HOLOGIC' in manufacturer:
    script = 'algorithms/bd_extracts/bd_extract_hologic.py'
elif 'GE' in manufacturer and 'LUNAR' in model.upper():
    script = 'algorithms/bd_extracts/bd_extract_ge.py'
else:
    # Fabricante no soportado
```

### 4. **Extracción de Pixel Map**
- Se extrae imagen JPEG del DICOM
- Se guarda en `pixel_extraction/BD/{PatientID}/`

### 5. **Procesamiento Específico por Fabricante**

#### **HOLOGIC** (80% de archivos - 471 files)
- ✅ **Implementado**
- Usa tag XML privado `(0x0019, 0x1000)`
- Extrae datos estructurados:
  - BMD (Bone Mineral Density)
  - T-score
  - Z-score
  - Hip laterality (Left/Right)
  - Forearm data (si existe)
- **Condición:** Solo procesa archivos HIP
- Script: `bd_extract_hologic.py`

#### **GE Lunar** (20% de archivos - 117 files)
- ⚠️ **Pendiente de implementación**
- Archivos tipo "DXA Reports" (reportes encapsulados)
- Requiere OCR (Optical Character Recognition)
- Script placeholder: `bd_extract_ge.py`

---

## 📊 Estadísticas de Equipos

| Fabricante | Archivos | Porcentaje | Script | Estado |
|------------|----------|------------|--------|--------|
| **HOLOGIC** | 471 | 79.56% | `bd_extract_hologic.py` | ✅ Implementado |
| **GE Healthcare Lunar** | 117 | 19.76% | `bd_extract_ge.py` | ⚠️ Pendiente OCR |
| **Sin datos** | 4 | 0.68% | N/A | N/A |

---

## 🔍 Logs de Procesamiento

Todos los pasos se registran en `/logs/bd_processing.log`:

```
[2026-01-22 16:30:00] [Patient: 209909] [RECEPCION] [SUCCESS] BD recibido - Fabricante: HOLOGIC, Modelo: Horizon Ci
[2026-01-22 16:30:00] [Patient: 209909] [DETECCION] [INFO] Equipo HOLOGIC detectado - Modelo: Horizon Ci
[2026-01-22 16:30:01] [Patient: 209909] [PIXEL_MAP] [SUCCESS] Pixel map extraído exitosamente
[2026-01-22 16:30:01] [Patient: 209909] [ANALISIS] [SUCCESS] Iniciando procesamiento con bd_extract_hologic.py
[2026-01-22 16:30:02] [Patient: 209909] [BD_INSERT] [SUCCESS] Reporte BD generado e insertado correctamente
```

---

## 🚀 Próximos Pasos

### Implementación GE Lunar (OCR)
1. Extraer imagen del reporte desde PixelData
2. Aplicar OCR (tesseract, pytesseract)
3. Parsing de texto para extraer valores clínicos
4. Generar reporte estructurado
5. Guardar en base de datos

### Mejoras Futuras
- [ ] Soporte para otros fabricantes (Norland, etc.)
- [ ] Procesamiento paralelo de múltiples archivos
- [ ] API REST para consultar reportes
- [ ] Dashboard de monitoreo de procesamiento

---

## 📝 Notas Técnicas

- **HOLOGIC:** 84% de archivos tienen XML con datos útiles
- **GE Lunar:** Todos son "DXA Reports" encapsulados
- **Compatibilidad:** Sistema modular permite agregar nuevos fabricantes fácilmente
