# BD Processing - GE Lunar Support (DICOM SR)

## Implementación Completada: 2026-02-24

### ✅ Funcionalidades Implementadas

#### 1. **Soporte para DICOM Structured Report (SR)**
- Agregados SOP Classes SR al servidor DICOM:
  - `BasicTextSRStorage`
  - `EnhancedSRStorage`
  - `ComprehensiveSRStorage`
- El servidor ahora acepta archivos DICOM SR de equipos GE Lunar

#### 2. **Extractor GE Lunar (`bd_extract_ge.py`)**
Implementado extractor completo para leer DICOM SR de GE Healthcare Lunar:

**Datos Extraídos:**
- **Demográficos**: PatientID, Name, Sex, DOB, Age, AccessionNumber, InstitutionName
- **Lumbar Spine**: BMD, T-Score, Z-Score, Vertebrae Range (L1-L4, etc.)
- **Left Hip**: BMD, T-Score, Z-Score
- **Right Hip**: BMD, T-Score, Z-Score
- **Left Forearm**: BMD, T-Score, Z-Score (si disponible)
- **Right Forearm**: BMD, T-Score, Z-Score (si disponible)
- **FRAX**: Major Fracture Risk, Hip Fracture Risk
- **FRAX Prior**: Major y Hip con fractura previa (si disponible)
- **WHO Classification**: Normal/Osteopenia/Osteoporosis

**Mecanismo de Extracción:**
- Recorre recursivamente el `ContentSequence` del SR
- Mapea conceptos (`ConceptNameCodeSequence.CodeMeaning`) a campos de datos
- Soporta valores numéricos (`ValueType=NUM`), texto (`TEXT`) y códigos (`CODE`)
- Extracción inteligente con keywords: "lumbar", "spine", "left", "right", "hip", "femoral", "forearm", "frax", "bmd", "t-score", "z-score"

#### 3. **Generación de Reportes**
- Utiliza la misma función `generate_report()` de Hologic
- Formato estandarizado para todos los fabricantes
- Incluye secciones FRAX "Without prior fracture" y "With prior fracture"
- Reportes guardados en `/home/ubuntu/DICOMReceiver/reports/`

#### 4. **Base de Datos PostgreSQL**
- Inserción/actualización en tabla `reports.bd`
- Merge inteligente de datos de múltiples archivos DICOM del mismo estudio
- Campos soportados: todos los BMD, T-scores, Z-scores, FRAX values, datos previos

#### 5. **Detección Automática de Fabricante**
En `main.py` líneas 544-640:
```python
if 'HOLOGIC' in manufacturer:
    extraction_script = 'bd_extract_hologic.py'
elif 'GE' in manufacturer or 'LUNAR' in manufacturer.upper() or 'LUNAR' in model.upper():
    extraction_script = 'bd_extract_ge.py'
```

### 📋 Archivos Modificados/Creados

1. **`/home/ubuntu/DICOMReceiver/algorithms/bd_extracts/bd_extract_ge.py`**
   - Reescrito completamente (501 líneas)
   - Función `extract_from_sr(ds)`: Parsea ContentSequence del SR
   - Función `insert_into_database(data)`: Guarda en PostgreSQL
   - Función `main(patient_id)`: Orquesta el procesamiento

2. **`/home/ubuntu/DICOMReceiver/main.py`**
   - Líneas 30-32: Agregados imports SR SOP Classes
   - Líneas 626-636: Actualizada detección GE Lunar
   - Líneas 771-773: Agregados contextos SR al servidor

3. **`/home/ubuntu/DICOMReceiver/test_ge_extraction.py`** (NUEVO)
   - Script de test con DICOM SR simulado
   - Crea paciente GETEST001 con datos completos
   - Valida extracción y reporte

### 🧪 Pruebas Realizadas

#### Test Automatizado
```bash
python3 test_ge_extraction.py
```

**Resultados:**
- ✅ DICOM SR creado y guardado
- ✅ 17 campos extraídos correctamente
- ✅ Lumbar BMD: 1.05, T-Score: -0.5, Z-Score: 1.5
- ✅ Left Hip BMD: 0.845, T-Score: -1.2
- ✅ Right Hip BMD: 0.892, T-Score: -0.8
- ✅ FRAX Major: 8.5%, Hip: 1.8%
- ✅ Reporte generado correctamente
- ✅ Datos guardados en PostgreSQL

#### Validación en Base de Datos
```sql
SELECT * FROM reports.bd WHERE mrn='GETEST001';
```
- ✅ Todos los valores coinciden con los esperados

### 📊 Estructura del DICOM SR

**Jerarquía ContentSequence:**
```
ContentSequence[0] → Lumbar Spine BMD
  ├─ RelationshipType: CONTAINS
  ├─ ValueType: NUM
  ├─ ConceptNameCodeSequence[0].CodeMeaning: "Lumbar Spine BMD"
  └─ MeasuredValueSequence[0]
      ├─ NumericValue: 1.050
      └─ MeasurementUnitsCodeSequence[0].CodeMeaning: "g/cm2"

ContentSequence[1] → Lumbar Spine T-Score
  └─ ... (similar structure)

... (recursivo para todos los conceptos)
```

### 🔧 Uso en Producción

#### Cuando llega un estudio GE Lunar:
1. **Recepción**: Servidor DICOM acepta el SR (Modality=SR)
2. **Detección**: main.py identifica "GE" o "LUNAR" en Manufacturer/Model
3. **Procesamiento**: Ejecuta `bd_extract_ge.py <patient_id>`
4. **Extracción**: Lee ContentSequence del SR
5. **Base de Datos**: Inserta/actualiza en reports.bd
6. **Reporte**: Genera archivo .txt en `/reports/`

#### Logs
```
/home/ubuntu/DICOMReceiver/logs/bd_processing.log
```

Formato:
```
[2026-02-24 17:XX:XX] [Patient: GETEST001] [DETECCION] [INFO] Equipo GE Lunar detectado - Modelo: Lunar Prodigy
[2026-02-24 17:XX:XX] [Patient: GETEST001] [BD_INSERT] [SUCCESS] Reporte BD generado e insertado correctamente (GE)
```

### 🆚 Comparación: Hologic vs GE Lunar

| Característica | HOLOGIC | GE Lunar |
|---------------|---------|----------|
| Formato de datos | XML en tag (0x0019, 0x1000) | DICOM SR (ContentSequence) |
| Modalidad DICOM | BD | SR |
| Archivos por estudio | Multiple (1 por región) | 1 archivo SR consolidado |
| Extracción FRAX | XML + opcional OCR | ContentSequence |
| Script extractor | `bd_extract_hologic.py` | `bd_extract_ge.py` |
| Procesamiento | Merge múltiples archivos | Procesar un solo SR |

### ⚙️ Configuración del Sistema

#### Servidor DICOM
- **Puerto**: 5665
- **AE Title**: DICOM_RECEIVER
- **SOP Classes soportados**: 11 (incluye 3 SR)
- **Transfer Syntaxes**: ImplicitVRLittleEndian, ExplicitVRLittleEndian

#### Base de Datos
- **Host**: localhost
- **Database**: qii
- **Schema**: reports
- **Table**: bd
- **User**: facundo
- **Password**: qii123

### 📝 Notas Técnicas

#### Mapeo de Conceptos SR
El sistema usa búsqueda flexible de keywords en `CodeMeaning`:
- "lumbar" + "spine" → Lumbar data
- "left" + "hip"|"femoral" → Left hip data
- "right" + "hip"|"femoral" → Right hip data
- "frax" + "major" → Major fracture risk
- "frax" + "hip" → Hip fracture risk
- "bmd"|"bone mineral density" → BMD values
- "t-score"|"t score" → T-scores
- "z-score"|"z score" → Z-scores

#### Campos Opcionales
Si no están presentes en el SR, se dejan como NULL:
- Forearm data (left/right)
- FRAX prior fracture values
- Datos históricos (prev_date, prev_bmd, change_percent)

### 🚀 Próximos Pasos Sugeridos

1. **Validar con DICOMs reales de GE Lunar** cuando lleguen
2. **Ajustar keywords** si los conceptos usan nombres diferentes
3. **Implementar soporte para datos históricos** si GE los incluye en SR
4. **Agregar validación de unidades** (g/cm2, kg/m2, etc.)
5. **Logs mejorados** con más detalle del parseo SR

### 📞 Soporte

Para problemas o ajustes, revisar:
1. Logs: `/home/ubuntu/DICOMReceiver/logs/bd_processing.log`
2. Reportes: `/home/ubuntu/DICOMReceiver/reports/`
3. Test: `python3 test_ge_extraction.py`
4. Servicio: `sudo systemctl status dicom-receiver.service`

---

**Implementado por**: Sistema
**Fecha**: 2026-02-24
**Versión**: 1.0
