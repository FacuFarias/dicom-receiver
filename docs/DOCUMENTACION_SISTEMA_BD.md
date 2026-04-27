# Documentación del Sistema de Procesamiento de Densitometría Ósea

## Fecha: 27 de Febrero, 2026
## Sistema: Receptor DICOM y Generación Automática de Reportes

---

## 1. ARQUITECTURA GENERAL DEL SISTEMA

### 1.1 Servidor DICOM (main.py)

El sistema opera como un servidor DICOM que recibe estudios de densitometría ósea desde los equipos de medición en el centro médico.

#### Flujo de Operación Principal:

1. **Inicialización del Servidor**
   - El servidor escucha en el puerto 5665 para conexiones DICOM entrantes
   - Se identifica con el AE Title "DICOM_RECEIVER"
   - Acepta 12 tipos diferentes de clases SOP DICOM, incluyendo:
     * Enhanced Structured Reports (para equipos GE Lunar)
     * Secondary Capture (para equipos Hologic)
     * DICOM SR estándar
     * Otros formatos de imagen médica

2. **Recepción de Estudios**
   - Cuando un equipo de densitometría completa un estudio, envía automáticamente los archivos DICOM al servidor
   - Cada estudio puede contener múltiples archivos:
     * Imágenes de los escaneos (formato Secondary Capture o BD)
     * Reportes estructurados con los valores de medición (SR)
     * Archivos XML con datos adicionales (en equipos Hologic)

3. **Almacenamiento Organizado**
   - Los archivos se organizan por paciente utilizando su MRN (Medical Record Number)
   - Estructura de directorios: `/dicom_storage/{MRN}/{StudyInstanceUID}/archivos`
   - Cada archivo mantiene su nombre único basado en SOP Instance UID

4. **Detección del Fabricante**
   
   El sistema identifica automáticamente el fabricante del equipo que envió el estudio mediante:
   
   - **Análisis del campo "Manufacturer" en el header DICOM**:
     * Si contiene "HOLOGIC" → Procesa como estudio Hologic
     * Si contiene "GE" o "GE MEDICAL" → Procesa como estudio GE Lunar
   
   - **Análisis del campo "Modality"**:
     * Si es "SR" (Structured Report) → Generalmente GE Lunar
     * Si es "OT" (Other) con XML adjunto → Generalmente Hologic
   
   - **Verificación de la institución**:
     * "DESERT" → Utiliza algoritmo específico para Desert Radiology
     * "MEMORIAL" → Utiliza algoritmo específico para Memorial Hermann
     * Otras instituciones → Utiliza algoritmo general

5. **Enrutamiento para Procesamiento**
   
   Una vez identificado el fabricante y la institución, el sistema llama al script de extracción apropiado:
   
   - **GE Lunar** → `bd_extract_ge.py`
   - **Hologic (General)** → `bd_extract_hologic.py`
   - **Hologic (Desert)** → `bd_extract_hologic_desert.py`
   - **Hologic (Memorial)** → `bd_extract_hologic_memorial.py`

---

## 2. PROCESAMIENTO DE ESTUDIOS GE LUNAR

### 2.1 Características de los Datos GE

Los equipos GE Healthcare Lunar envían datos en formato **Enhanced Structured Report (DICOM SR)**:

- Un estudio típico contiene **20+ archivos SR** con diferentes tipos de información
- Cada archivo SR contiene una estructura jerárquica de "containers" (contenedores)
- Los datos numéricos (BMD, T-score, Z-score) están organizados por región anatómica

### 2.2 Proceso de Extracción (bd_extract_ge.py)

#### Fase 1: Lectura y Acumulación de Datos

1. **Búsqueda de Archivos SR**
   - El sistema busca todos los archivos con Modality="SR" en el directorio del paciente
   - Cada archivo SR puede contener datos de diferentes regiones anatómicas

2. **Parseo de la Estructura Jerárquica**
   
   La estructura del SR de GE sigue este patrón:
   ```
   ContentSequence
   ├── Container: "AP Spine"
   │   └── Container: "L1-L4"
   │       ├── BMD (g/cm²)
   │       ├── T-score
   │       ├── Z-score
   │       ├── BMC (Bone Mineral Content)
   │       └── Area (cm²)
   │
   └── Container: "DualFemur"
       ├── Container: "Neck Left"
       │   ├── BMD (g/cm²)
       │   ├── T-score
       │   ├── Z-score
       │   └── ...
       │
       └── Container: "Neck Right"
           ├── BMD (g/cm²)
           ├── T-score
           ├── Z-score
           └── ...
   ```

3. **Extracción por Región Anatómica**
   
   El sistema identifica y extrae datos de las siguientes regiones:
   
   - **Columna Lumbar (L1-L4)**:
     * BMD (Bone Mineral Density)
     * T-score (comparación con adultos jóvenes sanos)
     * Z-score (comparación con adultos de la misma edad)
   
   - **Cadera Izquierda (Cuello Femoral)**:
     * BMD, T-score, Z-score
   
   - **Cadera Derecha (Cuello Femoral)**:
     * BMD, T-score, Z-score
   
   - **Antebrazo Izquierdo** (si está disponible):
     * BMD, T-score, Z-score
   
   - **Antebrazo Derecho** (si está disponible):
     * BMD, T-score, Z-score
   
   - **FRAX** (Fracture Risk Assessment Tool):
     * Riesgo de fractura osteoporótica mayor a 10 años
     * Riesgo de fractura de cadera a 10 años
     * Valores "with prior fracture" si están disponibles

4. **Acumulación de Datos de Múltiples SR**
   
   Debido a que GE Lunar distribuye la información en múltiples archivos SR:
   - El sistema procesa todos los archivos SR del estudio
   - Acumula los datos en un solo conjunto (algunos SR tienen solo lumbar, otros solo cadera)
   - Combina toda la información antes de generar el reporte final

#### Fase 2: Comparación con Estudios Previos

1. **Búsqueda en Base de Datos**
   - El sistema consulta la base de datos PostgreSQL buscando estudios previos del mismo paciente (mismo MRN)
   - Selecciona el estudio más reciente anterior al actual
   - Extrae los valores BMD previos de cada región

2. **Cálculo de Cambios Porcentuales**
   
   Para cada región anatómica donde existen datos actuales y previos:
   ```
   Cambio % = ((BMD_actual - BMD_previo) / BMD_previo) × 100
   ```

3. **Interpretación del Cambio**
   
   - **Cambio ≤ 3%**: Se considera "estable" (sin cambio significativo)
   - **Cambio > 3% positivo**: Se reporta como "aumento"
   - **Cambio > 3% negativo**: Se reporta como "disminución"
   
   Este umbral del 3% está basado en la precisión del equipo y la significancia clínica.

4. **Formato de Fecha**
   - La fecha del estudio previo se convierte a formato MM/DD/YYYY
   - Se incluye en la sección "Comparison" del reporte

#### Fase 3: Generación del Reporte Médico

1. **Construcción de la Sección Technique**
   
   Se genera automáticamente basándose en las regiones disponibles:
   - "the lumbar spine" (si hay datos lumbares)
   - "both hips" / "the right hip" / "the left hip" (según disponibilidad)
   - "both forearms" / "the right forearm" / "the left forearm"
   
   Ejemplo: "Bone density study was performed to evaluate the lumbar spine and both hips."

2. **Construcción de la Sección Findings**
   
   Para cada región anatómica disponible:
   
   - **Formato estándar**:
     * Nombre de la región (LUMBAR SPINE, RIGHT HIP, LEFT HIP, etc.)
     * Valor BMD en g/cm²
     * T-score
     * Z-score (si está disponible)
     * Texto de comparación con estudio previo (si existe)
   
   - **Ejemplo de texto generado**:
     ```
     LUMBAR SPINE: The bone mineral density in the lumbar spine (L1-L4) 
     is 1.126 g/cm² with a T-score of -0.6 and a Z-score of 0.9. 
     The bone mineral density in the lumbar spine remained stable since 2025.
     ```

3. **Construcción de la Sección FRAX** (si está disponible)
   
   Se presenta en formato tabular:
   - Sin fractura previa: Major osteoporotic fracture (%), Hip fracture (%)
   - Con fractura previa: Major osteoporotic fracture (%), Hip fracture (%)

4. **Construcción de la Sección Impression**
   
   Clasificación automática según criterios de la OMS:
   
   - **T-score ≥ -1.0**: Normal (bajo riesgo de fractura)
   - **T-score entre -1.0 y -2.5**: Osteopenia (riesgo moderado, considerar tratamiento)
   - **T-score ≤ -2.5**: Osteoporosis (alto riesgo, tratamiento recomendado)
   
   El sistema evalúa cada región y genera el texto apropiado para el médico.

#### Fase 4: Almacenamiento en Base de Datos

1. **Inserción o Actualización**
   - Si es un estudio nuevo: Se crea un registro con GUID único
   - Si ya existe (mismo MRN y Accession Number): Se actualiza con los nuevos datos

2. **Campos Guardados**
   - Datos demográficos: MRN, Accession Number, nombre del paciente
   - Todas las mediciones BMD, T-scores, Z-scores por región
   - Valores FRAX (con y sin fractura previa)
   - Clasificación WHO
   - Datos de comparación (BMD previo, fecha, porcentaje de cambio)
   - Texto completo del reporte
   - Timestamp del estudio

3. **Generación de Archivo de Reporte**
   - El reporte se guarda también como archivo de texto en `/reports/`
   - Nombre del archivo: `bd_report_{MRN}_{Accession}.txt`

---

## 3. PROCESAMIENTO DE ESTUDIOS HOLOGIC

### 3.1 Características de los Datos Hologic

Los equipos Hologic envían datos en un formato diferente:

- **Imágenes**: Secondary Capture (Modality="OT")
- **Datos estructurados**: Archivo XML embebido en el DICOM
- El XML contiene todos los valores de medición y metadatos del estudio

### 3.2 Proceso de Extracción (bd_extract_hologic.py, bd_extract_hologic_desert.py, bd_extract_hologic_memorial.py)

#### Fase 1: Extracción del XML

1. **Búsqueda del Archivo XML**
   - El sistema busca archivos con extensión `.xml` en el directorio del paciente
   - También busca el tag DICOM "EncapsulatedDocument" que puede contener XML

2. **Parseo del XML**
   
   El XML de Hologic tiene una estructura específica con secciones como:
   ```xml
   <bone_density_report>
     <patient_info>...</patient_info>
     <lumbar_spine>
       <bmd>1.126</bmd>
       <tscore>-0.6</tscore>
       <zscore>0.9</zscore>
     </lumbar_spine>
     <left_hip>...</left_hip>
     <right_hip>...</right_hip>
     <frax>...</frax>
   </bone_density_report>
   ```

3. **Extracción por Expresiones Regulares**
   
   Debido a que el formato XML puede variar entre versiones de software Hologic:
   - El sistema utiliza expresiones regulares robustas para extraer valores
   - Busca patrones como: "BMD.*?(\d+\.\d+)", "T-score.*?(-?\d+\.\d+)"
   - Maneja variaciones en el formato y etiquetas HTML embebidas

#### Fase 2: Manejo de Lateralidad

Las diferentes instituciones tienen configuraciones diferentes:

1. **bd_extract_hologic.py (General)**
   - Maneja estudios con ambas caderas
   - Extrae datos de left_hip y right_hip independientemente

2. **bd_extract_hologic_desert.py (Desert Radiology)**
   - Configurado para detectar automáticamente la lateralidad
   - Si solo hay datos de una cadera, determina si es izquierda o derecha
   - Utiliza lógica específica basada en los campos del XML de Desert

3. **bd_extract_hologic_memorial.py (Memorial Hermann)**
   - Similar a Desert pero con adaptaciones para el formato específico de Memorial
   - Maneja casos donde el XML puede tener estructura ligeramente diferente

#### Fase 3: Extracción de Datos de Comparación

A diferencia de GE, Hologic **incluye datos de comparación en el propio XML**:

1. **Identificación de Valores Previos**
   - El XML contiene secciones como "Previous Exam" o "Comparison"
   - Se extraen:
     * Fecha del estudio previo
     * BMD previo de cada región
     * Cambio porcentual ya calculado por el equipo

2. **Parseo de Cambios**
   - Formato típico: "+2.3%" o "-1.5%" o "2.3% (stable)"
   - El sistema extrae el valor numérico y el signo
   - Identifica si el cambio es marcado como significativo

#### Fase 4: Procesamiento de FRAX

1. **Extracción de Valores FRAX**
   - Major Osteoporotic Fracture Risk (10 años)
   - Hip Fracture Risk (10 años)
   - Valores "with prior fracture" si están disponibles

2. **Formato de Salida**
   - Los valores se almacenan como porcentajes
   - Se eliminan símbolos adicionales (%, paréntesis)

#### Fase 5: Generación del Reporte

El proceso es similar al de GE Lunar:

1. **Reaprovechamiento de la Función de Generación**
   - Los scripts de Hologic utilizan la misma función `generate_report()` que GE
   - Esto asegura consistencia en el formato del reporte final
   - La única diferencia está en cómo se obtienen los datos originales

2. **Inclusión de Datos de Comparación del XML**
   - Si el XML ya incluye comparaciones, se utilizan directamente
   - Si no, se realiza búsqueda en base de datos (similar a GE)

3. **Formato del Reporte**
   - Idéntico al formato de GE Lunar para mantener consistencia
   - El médico recibe el mismo tipo de reporte independientemente del fabricante

---

## 4. LÓGICA DE CLASIFICACIÓN CLÍNICA

### 4.1 Criterios de la Organización Mundial de la Salud (WHO)

El sistema aplica automáticamente los criterios WHO para clasificar la densidad ósea:

#### Para Mujeres Postmenopáusicas y Hombres >50 años:

- **Normal**: T-score ≥ -1.0
  * Densidad ósea dentro del rango normal
  * Bajo riesgo de fractura
  * Texto generado: "within a normal range. Low risk of fracture."

- **Osteopenia**: T-score entre -1.0 y -2.5
  * Densidad ósea reducida pero no osteoporótica
  * Riesgo moderado de fractura
  * Texto generado: "is osteopenic. Moderately increased risk of fracture. Treatment is advised."

- **Osteoporosis**: T-score ≤ -2.5
  * Densidad ósea significativamente reducida
  * Alto riesgo de fractura
  * Texto generado: "is osteoporotic. High risk of fracture. Treatment is strongly advised."

#### Para Mujeres Premenopáusicas, Hombres <50 años, y Niños:

Se utiliza el **Z-score** en lugar del T-score:

- **Normal**: Z-score > -2.0
- **Por debajo del rango esperado**: Z-score ≤ -2.0

### 4.2 Evaluación Multi-regional

Cuando un estudio incluye múltiples regiones anatómicas:

1. **Evaluación Independiente**
   - Cada región se evalúa según sus propios valores
   - El reporte indica específicamente qué regiones son normales, osteopénicas u osteoporóticas

2. **Determinación del Riesgo Global**
   - Se utiliza el **peor T-score** (más negativo) de todas las regiones
   - Ejemplo: Si lumbar es normal (-0.6) pero cadera izquierda es osteopénica (-1.4), el diagnóstico principal es osteopenia

3. **Texto del Reporte**
   - Se genera una frase para cada región con su clasificación específica
   - Se agrupan las regiones con la misma clasificación para brevedad

---

## 5. FLUJO COMPLETO DE UN ESTUDIO

### Cronología de Eventos:

1. **T=0 min**: Paciente completa el escaneo en el equipo GE Lunar o Hologic
2. **T=1 min**: Equipo envía automáticamente archivos DICOM al servidor
3. **T=1-2 min**: Servidor DICOM recibe y almacena archivos organizados por paciente
4. **T=2 min**: Sistema detecta que la recepción está completa e identifica el fabricante
5. **T=2-3 min**: Script de extracción apropiado procesa los archivos:
   - Lee datos de SR (GE) o XML (Hologic)
   - Busca estudios previos en base de datos
   - Calcula cambios porcentuales
   - Aplica clasificación WHO
6. **T=3 min**: Se genera el reporte médico en texto
7. **T=3 min**: Datos se guardan en base de datos PostgreSQL
8. **T=3 min**: Archivo de reporte se guarda en disco
9. **T=3+ min**: Reporte está disponible para revisión médica

**Tiempo total de procesamiento**: ~3 minutos desde que el paciente termina el escaneo hasta que el reporte está disponible.

---

## 6. GARANTÍA DE CALIDAD Y VALIDACIÓN

### 6.1 Verificaciones Automáticas

El sistema incluye múltiples verificaciones para asegurar la calidad de los datos:

1. **Validación de Datos Obligatorios**
   - MRN (Patient ID) debe estar presente
   - Accession Number debe estar presente
   - Al menos una región anatómica debe tener datos BMD válidos

2. **Validación de Rangos**
   - BMD debe estar en rango fisiológico (0.3 - 2.0 g/cm²)
   - T-score debe estar en rango razonable (-5.0 a +5.0)
   - Z-score debe estar en rango razonable (-5.0 a +5.0)

3. **Manejo de Datos Faltantes**
   - Si una región no tiene datos, no se incluye en el reporte
   - Si datos de comparación no están disponibles, se indica "[None available]"
   - Campos opcionales (FRAX, forearm) solo se incluyen si están presentes

4. **Logging de Errores**
   - Todos los errores se registran con timestamp
   - Se genera output detallado durante el procesamiento
   - Los archivos problemáticos se marcan para revisión manual

### 6.2 Consistencia Entre Fabricantes

El sistema asegura que los reportes finales sean consistentes independientemente del fabricante:

1. **Mismo Formato de Reporte**
   - Mismas secciones: History, Technique, Comparison, Findings, Impression
   - Mismo orden de regiones anatómicas
   - Misma terminología médica

2. **Misma Clasificación Clínica**
   - Mismos criterios WHO aplicados
   - Mismos umbrales para cambios significativos (3%)
   - Mismas recomendaciones de seguimiento

3. **Misma Estructura de Base de Datos**
   - Todos los datos se almacenan en el mismo esquema
   - Facilita análisis longitudinal independiente del equipo usado

---

## 7. VENTAJAS DEL SISTEMA AUTOMATIZADO

### 7.1 Para el Departamento de Radiología

- **Eliminación de transcripción manual**: Reduce errores humanos
- **Procesamiento inmediato**: Reporte disponible en minutos
- **Consistencia**: Formato estandarizado para todos los estudios
- **Trazabilidad**: Todos los datos y reportes están archivados
- **Comparaciones automáticas**: No requiere buscar manualmente estudios previos

### 7.2 Para el Médico Radiólogo

- **Información completa**: Todos los valores BMD, T-scores, Z-scores presentes
- **Comparaciones automáticas**: Cambios porcentuales ya calculados
- **Clasificación OMS**: Diagnóstico preliminar según criterios estándar
- **Recomendaciones de seguimiento**: Basadas en guías clínicas
- **Formato familiar**: Similar a reportes tradicionales

### 7.3 Para el Médico Tratante

- **Acceso rápido**: Reporte disponible minutos después del escaneo
- **Formato estandarizado**: Fácil de interpretar
- **Historial incorporado**: Comparación con estudios previos incluida
- **FRAX scores**: Herramienta para decisiones de tratamiento

### 7.4 Para el Paciente

- **Tiempo de espera reducido**: Resultados disponibles el mismo día
- **Continuidad de atención**: Comparaciones automáticas con estudios previos
- **Precisión**: Eliminación de errores de transcripción manual

---

## 8. CONSIDERACIONES TÉCNICAS IMPORTANTES

### 8.1 Base de Datos PostgreSQL

**Tabla principal**: `reports.bd`

**Campos clave almacenados**:
- Identificación: guid, mrn, acc, pat_name
- Fechas: studydate, lumbar_prev_date, left_hip_prev_date, right_hip_prev_date
- Lumbar Spine: lumbar_bmd, lumbar_tscore, lumbar_zscore, lumbar_vertebrae_range
- Hip izquierda: left_hip_bmd, left_hip_tscore, left_hip_zscore
- Hip derecha: right_hip_bmd, right_hip_tscore, right_hip_zscore
- Forearm izquierdo: left_forearm_bmd, left_forearm_tscore, left_forearm_zscore
- Forearm derecho: right_forearm_bmd, right_forearm_tscore, right_forearm_zscore
- FRAX: major_fracture_risk, hip_fracture_risk, major_fracture_risk_prior, hip_fracture_risk_prior
- Comparaciones: lumbar_prev_bmd, lumbar_change_percent, left_hip_change_percent, right_hip_change_percent
- Clasificación: WHO_Classification
- Reporte: bd_report (texto completo)

### 8.2 Mantenimiento del Sistema

**Backups recomendados**:
- Base de datos PostgreSQL: Daily backup
- Archivos DICOM: Backup según políticas de retención institucional
- Reportes generados: Incluidos en backup de base de datos

**Monitoreo**:
- Verificar que el servicio DICOM está corriendo: `systemctl status dicom-receiver`
- Revisar logs en `/home/ubuntu/DICOMReceiver/logs/`
- Verificar espacio en disco para almacenamiento DICOM

**Actualizaciones**:
- Scripts de Python pueden actualizarse sin interrumpir el servicio
- Después de cambios, reiniciar: `systemctl restart dicom-receiver`

---

## 9. CASOS ESPECIALES Y EXCEPCIONES

### 9.1 Estudios con Una Sola Cadera

Algunos pacientes solo pueden escanearse una cadera (prótesis, lesión, etc.):

- Sistema detecta automáticamente qué cadera tiene datos
- Reporte solo incluye la cadera disponible
- Comparaciones funcionan correctamente para una sola cadera

### 9.2 Estudios sin Datos Previos

Para pacientes nuevos sin estudios anteriores:

- Campo "Comparison" indica "[None available]"
- No se muestran cambios porcentuales
- Reporte se genera normalmente con valores actuales
- Este estudio servirá como baseline para futuras comparaciones

### 9.3 Estudios con Regiones Adicionales

Si un equipo está configurado para medir forearm:

- Sistema detecta y procesa automáticamente
- Se incluyen en secciones separadas del reporte
- Comparaciones funcionan igual que para otras regiones

### 9.4 Cambios Significativos en BMD

Si un cambio es muy grande (>15%):

- El sistema lo reporta normalmente
- El médico debe revisar para descartar:
  * Error de medición
  * Cambio de equipo
  * Intervención terapéutica efectiva

---

## 10. CONCLUSIÓN

Este sistema automatizado de procesamiento de densitometría ósea proporciona:

1. **Eficiencia operacional**: Procesamiento automático en ~3 minutos
2. **Precisión**: Eliminación de errores de transcripción manual
3. **Consistencia**: Formato estandarizado independiente del fabricante
4. **Inteligencia clínica**: Comparaciones automáticas y clasificación WHO
5. **Integración completa**: Desde equipo hasta base de datos

El sistema está diseñado para ser:
- **Robusto**: Maneja múltiples fabricantes y formatos
- **Escalable**: Puede procesar estudios de múltiples equipos simultáneamente
- **Mantenible**: Código modular y bien organizado
- **Auditable**: Todos los datos y reportes son rastreables

---

**Preparado por**: Sistema de Documentación Técnica  
**Fecha**: 27 de Febrero, 2026  
**Versión**: 1.0  
**Sistema**: DICOMReceiver - Bone Densitometry Processing
