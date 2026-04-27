# Documentación Técnica de Algoritmos de Extracción
## Bone Densitometry Processing System

---

## INTRODUCCIÓN

Este documento detalla la lógica específica de cada algoritmo de extracción de datos 
para densitometría ósea. Los cuatro scripts principales son:

1. **bd_extract_ge.py** - Para equipos GE Healthcare Lunar
2. **bd_extract_hologic.py** - Para equipos Hologic (general)
3. **bd_extract_hologic_desert.py** - Para equipos Hologic en Desert Radiology
4. **bd_extract_hologic_memorial.py** - Para equipos Hologic en Memorial Hermann

---

## ALGORITMO 1: bd_extract_ge.py (GE HEALTHCARE LUNAR)

### Características del Formato de Datos

GE Lunar envía datos en formato **Enhanced Structured Report (Enhanced SR)**:
- Múltiples archivos SR por estudio (típicamente 15-20 archivos)
- Estructura jerárquica tipo árbol (ContentSequence)
- Datos distribuidos en diferentes archivos SR

### Lógica del Algoritmo

#### FASE 1: Identificación y Lectura de Archivos

```
ENTRADA: Patient MRN
PROCESO:
1. Buscar directorio: /dicom_storage/{MRN}/
2. Para cada subdirectorio (Study):
   a. Buscar todos los archivos DICOM
   b. Leer header DICOM de cada archivo
   c. Si Modality == "SR":
      - Agregar a lista de archivos_SR
   d. Si no:
      - Saltar (es imagen, no datos)
3. Ordenar archivos_SR por tamaño (más grandes primero)
SALIDA: Lista de archivos SR a procesar
```

**Rationale**: Los archivos SR más grandes generalmente contienen más datos de medición, 
los más pequeños solo metadata. Procesar por tamaño optimiza la extracción.

#### FASE 2: Parseo de Estructura Jerárquica

```
ENTRADA: Archivo SR individual
PROCESO:
1. Leer dataset DICOM completo
2. Verificar existencia de ContentSequence
3. Si no existe ContentSequence:
   - Retornar datos vacíos (es SR de metadata)
   - Continuar con siguiente archivo
4. Inicializar contenedores de datos vacíos:
   - lumbar_bmd, lumbar_tscore, lumbar_zscore
   - left_hip_bmd, left_hip_tscore, left_hip_zscore
   - right_hip_bmd, right_hip_tscore, right_hip_zscore
   - (etc. para todas las regiones)
```

**Estructura del ContentSequence de GE**:
```
ContentSequence (nivel 0)
├── [0] Language
├── [1] Observer Type
├── [2] Person Observer Name
├── [3] CONTAINER: "History"
├── [4] CONTAINER: "AP Spine"
│   └── [0] CONTAINER: "L1-L4"
│       ├── [0] NUM: BMD
│       ├── [1] NUM: BMC
│       ├── [2] NUM: Area
│       ├── [3] NUM: T-score
│       └── [4] NUM: Z-score
└── [5] CONTAINER: "DualFemur"
    ├── [0] CONTAINER: "Neck Left"
    │   ├── [0] NUM: BMD
    │   ├── [3] NUM: T-score
    │   └── [4] NUM: Z-score
    ├── [1] CONTAINER: "Neck Right"
    │   ├── [0] NUM: BMD
    │   ├── [3] NUM: T-score
    │   └── [4] NUM: Z-score
    ├── [2] CONTAINER: "Neck Mean"
    └── [3] CONTAINER: "Neck Diff."
```

#### FASE 3: Extracción Recursiva por Región

```
FUNCIÓN: process_container(container_item)
ENTRADA: Item de ContentSequence con ValueType="CONTAINER"
PROCESO:
1. Obtener nombre del container:
   concept_name = container.ConceptNameCodeSequence[0].CodeMeaning

2. Identificar tipo de región anatómica:
   
   SI concept_name contiene "AP Spine" O "Lumbar":
      - Buscar sub-container "L1-L4" (o similar)
      - Extraer valores de ese sub-container
      - Almacenar en: lumbar_bmd, lumbar_tscore, lumbar_zscore
   
   SI concept_name contiene "DualFemur" O "Femur":
      - Buscar sub-container "Neck Left"
        * Extraer y almacenar: left_hip_bmd, left_hip_tscore, left_hip_zscore
      - Buscar sub-container "Neck Right"
        * Extraer y almacenar: right_hip_bmd, right_hip_tscore, right_hip_zscore
   
   SI concept_name contiene "Forearm":
      - Similar a hip, pero para forearm
      - Identificar lateralidad (Left/Right)
   
   SI concept_name contiene "FRAX":
      - Buscar valores numéricos
      - Distinguir entre "Major" y "Hip" fracture risk
      - Distinguir entre "without prior" y "with prior"

3. Para cada valor numérico en el container:
   a. Obtener concept_name del valor
   b. SI contiene "BMD" o "Bone Mineral Density":
      - Extraer NumericValue de MeasuredValueSequence
      - Convertir a float
      - Almacenar en campo correspondiente
   c. SI contiene "T-score" o "T score":
      - Extraer NumericValue
      - Convertir a float
      - Almacenar en campo correspondiente
   d. SI contiene "Z-score" or "Z score":
      - Extraer NumericValue
      - Convertir a float
      - Almacenar en campo correspondiente

4. Si el container tiene ContentSequence:
   - Recursión: process_container() para cada sub-item CONTAINER
```

**Rationale**: La estructura jerárquica de GE requiere parsing recursivo. Un container 
puede contener sub-containers, y los valores numéricos están en el nivel más profundo.

#### FASE 4: Acumulación de Múltiples SR

```
PROCESO: Combinar datos de múltiples archivos SR
NECESIDAD: GE distribuye datos en ~20 archivos diferentes:
- Algunos SR contienen solo datos lumbares
- Otros solo datos de cadera izquierda
- Otros solo datos de cadera derecha
- Algunos solo metadata

ALGORITMO:
1. Inicializar: accumulated_data = None
2. Para cada archivo SR procesado:
   a. Extraer datos del SR actual
   b. SI accumulated_data es None:
      - accumulated_data = datos_actuales
   c. SI NO:
      - Para cada campo en datos_actuales:
        * SI campo no es None:
          - Sobrescribir en accumulated_data
          - (Datos más completos reemplazan None)

3. RESULTADO: accumulated_data contiene todos los datos de todas las regiones
```

**Ejemplo**:
```
SR #1: lumbar_bmd=1.126, lumbar_tscore=-0.6, left_hip=None, right_hip=None
SR #2: lumbar=None, left_hip_bmd=0.848, left_hip_tscore=-1.4, right_hip=None
SR #3: lumbar=None, left_hip=None, right_hip_bmd=0.941, right_hip_tscore=-0.7

RESULTADO ACUMULADO:
lumbar_bmd=1.126, lumbar_tscore=-0.6, 
left_hip_bmd=0.848, left_hip_tscore=-1.4,
right_hip_bmd=0.941, right_hip_tscore=-0.7
```

#### FASE 5: Comparación con Estudios Previos

```
ENTRADA: datos_acumulados, MRN, Accession_Number_actual
PROCESO:
1. Consultar base de datos:
   SQL: SELECT studydate, lumbar_bmd, left_hip_bmd, right_hip_bmd, ...
        FROM reports.bd
        WHERE mrn = {MRN} AND acc != {ACC_actual}
        ORDER BY studydate DESC
        LIMIT 1

2. SI hay resultado:
   a. Extraer fecha y valores BMD previos
   b. Para cada región (lumbar, left_hip, right_hip, forearms):
      
      SI existe BMD_actual Y BMD_previo:
         - Calcular: cambio_pct = ((BMD_actual - BMD_previo) / BMD_previo) * 100
         
         - Formatear: cambio_str = sprintf("%+.1f%%", cambio_pct)
           Ejemplos: "+4.7%", "-2.3%", "+0.0%"
         
         - Almacenar:
           * {region}_prev_date = fecha_formateada (MM/DD/YYYY)
           * {region}_prev_bmd = BMD_previo
           * {region}_change_percent = cambio_str
         
         - Imprimir para log:
           "Region: BMD_previo → BMD_actual (cambio_pct%)"

3. SI no hay estudio previo:
   - Campos de comparación permanecen None
   - Reporte indicará "[None available]"
```

**Rationale**: GE no incluye datos de comparación en el SR, por lo que el sistema 
debe calcularlo consultando estudios previos en la base de datos.

#### FASE 6: Generación del Reporte

```
ENTRADA: datos_acumulados (con comparaciones agregadas)
PROCESO:
1. Convertir valores float a string:
   - generate_report() espera strings, no floats
   - Para cada campo numérico: str(valor)

2. Determinar regiones disponibles:
   has_lumbar = (lumbar_bmd != None) OR (lumbar_tscore != None)
   has_left_hip = (left_hip_bmd != None) OR (left_hip_tscore != None)
   has_right_hip = (right_hip_bmd != None) OR (right_hip_tscore != None)
   has_left_forearm = ...
   has_right_forearm = ...

3. Construir sección Technique:
   regions = []
   SI has_lumbar: agregar "the lumbar spine"
   SI has_left_forearm Y has_right_forearm: agregar "both forearms"
   SI has_left_hip Y has_right_hip: agregar "both hips"
   ... (lógica para combinaciones)
   
   Formatear: "Bone density study was performed to evaluate {regions}"

4. Construir sección Comparison:
   SI hay múltiples fechas de comparación diferentes:
      - Listar todas: "04/24/2025; 03/15/2024"
   SI hay una sola fecha:
      - Mostrar: "04/24/2025"
   SI no hay:
      - Mostrar: "[None available]"

5. Construir sección Findings:
   Para cada región donde has_{region} == True:
      a. Generar texto estándar:
         "{REGION}: The bone mineral density in the {anatomical_name}
          is {BMD} g/cm² with a T-score of {T} and a Z-score of {Z}."
      
      b. SI hay datos de comparación para esta región:
         - Extraer año de fecha: "04/24/2025" → "2025"
         - Calcular si cambio > 3% en valor absoluto
         
         SI cambio <= 3%:
            texto_comp = "The bone mineral density remained stable since {year}."
         SI cambio > 3% positivo:
            texto_comp = "The bone mineral density [increased] by {pct} since {year}."
         SI cambio > 3% negativo:
            texto_comp = "The bone mineral density [decreased] by {pct} since {year}."
         
         Agregar texto_comp al final del párrafo de la región

6. Construir sección FRAX (si disponible):
   SI major_fracture_risk O hip_fracture_risk existen:
      SI major_fracture_risk_prior O hip_fracture_risk_prior existen:
         - Formato de dos columnas:
           "Without prior fracture: Major={X}%, Hip={Y}%
            With prior fracture: Major={X'}%, Hip={Y'}%"
      SI NO:
         - Formato simple:
           "Major osteoporotic fracture: {X}%
            Hip fracture: {Y}%"

7. Construir sección Impression:
   a. Encontrar peor T-score de todas las regiones
   b. Aplicar clasificación WHO:
      SI peor_tscore >= -1.0: clasificacion = "normal"
      SI -2.5 < peor_tscore < -1.0: clasificacion = "osteopenic"
      SI peor_tscore <= -2.5: clasificacion = "osteoporotic"
   
   c. Generar texto por clasificación:
      Para cada región:
         SI clasificacion == "osteopenic":
            "... is osteopenic. Moderately increased risk of fracture. 
             Treatment is advised."
         SI clasificacion == "osteoporotic":
            "... is osteoporotic. High risk of fracture. 
             Treatment is strongly advised."
         SI clasificacion == "normal":
            "... is within a normal range. Low risk of fracture."
   
   d. Agregar recomendación de seguimiento:
      "Follow-up bone mineral density exam is recommended in 24 months."

8. Combinar todas las secciones en formato final
9. Retornar texto completo del reporte

SALIDA: String con reporte médico formateado
```

#### FASE 7: Almacenamiento

```
PROCESO:
1. Guardar archivo de texto:
   ruta = /reports/bd_report_{MRN}_{ACC}.txt
   escribir(reporte_texto)

2. Insertar/Actualizar en PostgreSQL:
   
   VERIFICAR si ya existe:
   SQL: SELECT guid FROM reports.bd 
        WHERE mrn={MRN} AND acc={ACC}
   
   SI existe:
      - UPDATE con nuevos valores
      - Campos None no sobrescriben existentes
      - Permite combinar datos de múltiples recepciones
   
   SI NO existe:
      - INSERT nuevo registro
      - Generar GUID único
      - studydate = CURRENT_TIMESTAMP

   CAMPOS GUARDADOS:
   - Identificación: guid, mrn, acc, pat_name
   - Lumbar: lumbar_bmd, lumbar_tscore, lumbar_zscore, lumbar_vertebrae_range
   - Left Hip: left_hip_bmd, left_hip_tscore, left_hip_zscore
   - Right Hip: right_hip_bmd, right_hip_tscore, right_hip_zscore
   - Forearms: left_forearm_*, right_forearm_*
   - FRAX: major_fracture_risk, hip_fracture_risk, *_prior
   - Comparación: *_prev_date, *_prev_bmd, *_change_percent
   - Clasificación: WHO_Classification
   - Reporte: bd_report (texto completo)
   - Fechas: studydate

3. Commit transaction
4. Cerrar conexión

RESULTADO: Datos persistidos en archivo y base de datos
```

---

## ALGORITMO 2: bd_extract_hologic.py (HOLOGIC GENERAL)

### Características del Formato de Datos

Hologic envía datos de manera diferente a GE:
- **Imágenes**: Secondary Capture (Modality="OT")
- **Datos estructurados**: Archivo XML embebido en DICOM
- **Un solo archivo por estudio** (no múltiples como GE)

### Lógica del Algoritmo

#### FASE 1: Extracción del XML

```
ENTRADA: Patient MRN
PROCESO:
1. Buscar directorio: /dicom_storage/{MRN}/
2. Buscar archivo XML:
   OPCIÓN A: Archivo separado con extensión .xml
   OPCIÓN B: XML embebido en tag DICOM "EncapsulatedDocument"
   OPCIÓN C: XML embebido en tag "TextValue" de algún field

3. Leer contenido XML completo
4. Decodificar si está en base64 o comprimido

SALIDA: String con contenido XML completo
```

**Ejemplo de estructura XML de Hologic**:
```xml
<?xml version="1.0"?>
<DXAReport>
  <Patient>
    <ID>MMD752504000</ID>
    <Name>Tadych^Theresa^A^^</Name>
    <DOB>07/16/1958</DOB>
  </Patient>
  <Study>
    <Date>02/26/2026</Date>
    <AccessionNumber>6577082</AccessionNumber>
  </Study>
  <Results>
    <AP_Spine>
      <Region>L1-L4</Region>
      <BMD>1.126</BMD>
      <TScore>-0.6</TScore>
      <ZScore>0.9</ZScore>
      <Comparison>
        <Date>04/24/2025</Date>
        <BMD_Previous>1.126</BMD_Previous>
        <Change>0.0%</Change>
      </Comparison>
    </AP_Spine>
    <LeftHip>
      <BMD>0.848</BMD>
      <TScore>-1.4</TScore>
      ...
    </LeftHip>
    <FRAX>
      <MajorFracture>5.2</MajorFracture>
      <HipFracture>1.8</HipFracture>
    </FRAX>
  </Results>
</DXAReport>
```

#### FASE 2: Parseo mediante Expresiones Regulares

```
NECESIDAD: El XML de Hologic varía entre versiones de software
- Algunos tienen etiquetas HTML (<b>, <p>, etc.)
- Algunos usan nombres de tags diferentes
- Orden de elementos puede variar

SOLUCIÓN: Expresiones regulares robustas

FUNCIÓN: extract_value(xml_string, patterns)
ENTRADA:
- xml_string: Contenido XML completo
- patterns: Lista de regex patterns alternativos

ALGORITMO:
Para cada pattern en patterns:
   match = regex.search(pattern, xml_string, flags=IGNORECASE)
   SI match:
      valor = match.group(1)
      SI valor no está vacío:
         limpiar_html(valor)  # Remover tags HTML si existen
         return valor
   
SI ningún pattern coincide:
   return None

EJEMPLO DE PATTERNS para BMD lumbar:
patterns = [
   r'<AP_Spine>.*?<BMD>([\d.]+)</BMD>',
   r'Spine.*?BMD:?\s*([\d.]+)',
   r'L1-L4.*?BMD.*?([\d.]+)',
   r'LUMBAR.*?(\d\.\d+)\s*g/cm',
]
```

**Rationale**: Regex permite manejar variaciones en el formato XML sin requerir 
parser XML estricto que fallaría con HTML embebido.

#### FASE 3: Extracción por Región

```
DEFINIR: Diccionario de campos a extraer

campos = {
   'patient_id': ['<ID>(.*?)</ID>', 'Patient.*?ID:?\s*(\w+)'],
   'accession_number': ['<AccessionNumber>(.*?)</AccessionNumber>', ...],
   'pat_name': ['<Name>(.*?)</Name>', ...],
   
   'lumbar_bmd': ['<AP_Spine>.*?<BMD>([\d.]+)</BMD>', ...],
   'lumbar_tscore': ['<AP_Spine>.*?<TScore>([-\d.]+)</TScore>', ...],
   'lumbar_zscore': ['<AP_Spine>.*?<ZScore>([-\d.]+)</ZScore>', ...],
   
   'left_hip_bmd': ['<LeftHip>.*?<BMD>([\d.]+)</BMD>', ...],
   'left_hip_tscore': ['<LeftHip>.*?<TScore>([-\d.]+)</TScore>', ...],
   ... (similar para right_hip, forearms, FRAX)
}

PROCESO:
Para cada (campo, patterns) en campos:
   valor = extract_value(xml_string, patterns)
   SI valor != None:
      data[campo] = valor
```

#### FASE 4: Extracción de Datos de Comparación

```
CARACTERÍSTICA ESPECIAL DE HOLOGIC:
El XML ya incluye datos de comparación con estudios previos

BÚSQUEDA EN XML:
Para cada región (lumbar, left_hip, right_hip, forearms):
   
   1. Buscar fecha previa:
      patterns = [
         '<Comparison>.*?<Date>(.*?)</Date>',
         'Previous.*?Date:?\s*([\d/]+)',
         'Baseline.*?([\d/]+)',
      ]
      fecha_prev = extract_value(xml, patterns)
      data['{region}_prev_date'] = fecha_prev
   
   2. Buscar BMD previo:
      patterns = [
         '<Comparison>.*?<BMD_Previous>([\d.]+)</BMD_Previous>',
         'Previous.*?BMD:?\s*([\d.]+)',
      ]
      bmd_prev = extract_value(xml, patterns)
      data['{region}_prev_bmd'] = bmd_prev
   
   3. Buscar cambio porcentual:
      patterns = [
         '<Change>([-+]?[\d.]+)%?</Change>',
         'Change:?\s*([-+]?[\d.]+)%',
         '\(([-+]?[\d.]+)%\)',  # Formato: "1.126 g/cm² (+2.3%)"
      ]
      cambio = extract_value(xml, patterns)
      SI cambio:
         # Formato puede ser: "+2.3", "2.3%", "-1.5", etc.
         limpiar_formato(cambio)  # Asegurar que incluye signo y %
         data['{region}_change_percent'] = cambio

EJEMPLO DE XML CON COMPARACIÓN:
<AP_Spine>
   <BMD>1.126</BMD>
   <TScore>-0.6</TScore>
   <Comparison>
      <Date>04/24/2025</Date>
      <BMD_Previous>1.126</BMD_Previous>
      <Change>0.0%</Change>
      <Status>Stable</Status>
   </Comparison>
</AP_Spine>
```

**Ventaja**: Hologic ya incluye comparaciones, no necesita cálculo adicional.

#### FASE 5: Detección de Lateralidad

```
PROBLEMA: Algunos estudios Hologic solo incluyen una cadera
- XML puede tener solo <LeftHip> o solo <RightHip>
- O puede tener <Hip> sin especificar lateralidad

ALGORITMO DE DETECCIÓN:
1. Buscar en XML tags específicos:
   tiene_left = '<LeftHip>' in xml
   tiene_right = '<RightHip>' in xml

2. SI tiene_left Y tiene_right:
   - Estudio bilateral normal
   - Extraer ambos lados

3. SI tiene_left XOR tiene_right:
   - Estudio unilateral
   - Extraer el lado que existe
   - Otro lado permanece None

4. SI tiene tag '<Hip>' genérico:
   - Buscar indicadores de lateralidad en texto:
     SI 'left' in xml.lower():
        asignar a left_hip_*
     SI 'right' in xml.lower():
        asignar a right_hip_*
     SI ninguno:
        # Asumir lado por convención institucional
        # O marcar para revisión manual

5. Validar con valores BMD:
   SI left_hip_bmd existe Y right_hip_bmd NO:
      lateralidad_confirmada = 'left'
   SI right_hip_bmd existe Y left_hip_bmd NO:
      lateralidad_confirmada = 'right'
```

**Rationale**: Necesario para manejar pacientes con prótesis o estudios unilaterales.

#### FASE 6: Generación del Reporte

```
PROCESO: Idéntico a GE Lunar
- Utiliza misma función generate_report()
- Mismas secciones y formato
- Diferencia: Algunos datos ya vienen formateados del XML

PASOS:
1. Preparar datos en formato esperado (strings)
2. Llamar generate_report(data)
3. Retornar texto completo

RESULTADO: Reporte idéntico en formato a GE Lunar
```

#### FASE 7: Almacenamiento

```
PROCESO: Idéntico a GE Lunar
1. Guardar archivo de texto en /reports/
2. INSERT o UPDATE en PostgreSQL tabla reports.bd
3. Commit y cerrar

DIFERENCIA: Hologic generalmente no requiere acumulación de múltiples archivos
```

---

## ALGORITMO 3: bd_extract_hologic_desert.py (DESERT RADIOLOGY)

### Adaptaciones Específicas

Desert Radiology tiene configuraciones específicas en sus equipos Hologic.

#### Diferencias con bd_extract_hologic.py General

```
1. FORMATO XML:
   - Desert usa formato XML con estructura ligeramente diferente
   - Algunos tags tienen nombres propietarios
   - Require patterns regex adicionales

2. DETECCIÓN DE LATERALIDAD:
   Desert tiene lógica específica para determinar lateralidad:
   
   ALGORITMO:
   SI XML contiene '<hip_side>left</hip_side>':
      lateralidad = 'left'
   SI XML contiene '<hip_side>right</hip_side>':
      lateralidad = 'right'
   SI XML contiene '<hip_side>bilateral</hip_side>':
      lateralidad = 'both'
   SI NO especificado:
      # Buscar en texto del reporte
      SI 'left hip' aparece antes que 'right hip':
         lateralidad = 'left'
      SI 'right hip' aparece antes que 'left hip':
         lateralidad = 'right'

3. COMPARACIONES:
   Desert incluye comparaciones en formato específico:
   - Fecha: 'Comparison: 04/24/2025'
   - Cambio: '1.126 g/cm² (Stable)' o '0.941 g/cm² (+4.7%)'
   
   EXTRACCIÓN:
   pattern_cambio = r'(\d\.\d+)\s*g/cm²\s*\(([-+\d.%]+|Stable|Increased|Decreased)\)'
   match = regex.search(pattern_cambio, xml)
   SI match:
      bmd = match.group(1)
      cambio = match.group(2)
      SI cambio == 'Stable':
         cambio_pct = '0.0%'
      SI cambio == 'Increased' o 'Decreased':
         # Buscar valor numérico cerca
         buscar_porcentaje_adicional()
      SI NO:
         cambio_pct = cambio  # Ya es formato "+4.7%"

4. FRAX:
   Desert puede incluir FRAX en sección separada del XML:
   <FRAX_Assessment>
      <WithoutPriorFracture>
         <MajorOsteoporotic>5.2</MajorOsteoporotic>
         <Hip>1.8</Hip>
      </WithoutPriorFracture>
      <WithPriorFracture>
         <MajorOsteoporotic>11.0</MajorOsteoporotic>
         <Hip>4.2</Hip>
      </WithPriorFracture>
   </FRAX_Assessment>
   
   Requiere patterns específicos para extraer ambos sets de valores
```

### Resto del Algoritmo

```
Las demás fases son idénticas a bd_extract_hologic.py:
- Generación de reporte usa misma función
- Almacenamiento idéntico
- Clasificación WHO idéntica
```

---

## ALGORITMO 4: bd_extract_hologic_memorial.py (MEMORIAL HERMANN)

### Adaptaciones Específicas

Memorial Hermann tiene su propio formato de XML de Hologic.

#### Diferencias con bd_extract_hologic.py General

```
1. FORMATO XML:
   Memorial usa estructura XML con namespaces:
   
   <dxa:DXAReport xmlns:dxa="http://memorial-hermann.org/dxa">
      <dxa:Patient>...</dxa:Patient>
      <dxa:Results>...</dxa:Results>
   </dxa:DXAReport>
   
   SOLUCIÓN:
   - Ignorar namespaces en regex: 
     pattern = r'<\w+:Patient>.*?<\w+:ID>(.*?)</\w+:ID>'
   - O remover namespaces del XML primero:
     xml_clean = regex.sub(r'<\w+:', '<', xml)
     xml_clean = regex.sub(r'</\w+:', '</', xml_clean)

2. NOMBRES DE CAMPOS:
   Memorial usa nombres ligeramente diferentes:
   
   MAPEO:
   pattern_lumbar_bmd = [
      r'<ApSpine>.*?<BoneDensity>([\d.]+)</BoneDensity>',  # Memorial
      r'<AP_Spine>.*?<BMD>([\d.]+)</BMD>',                 # Estándar
      r'Spine.*?BMD:?\s*([\d.]+)',                         # Fallback
   ]

3. COMPARACIONES:
   Memorial incluye tabla de comparación completa:
   
   <ComparisonTable>
      <Region name="Lumbar Spine">
         <Current>
            <Date>02/26/2026</Date>
            <BMD>1.126</BMD>
         </Current>
         <Previous>
            <Date>04/24/2025</Date>
            <BMD>1.126</BMD>
         </Previous>
         <Change>
            <Absolute>0.000</Absolute>
            <Percent>0.0</Percent>
            <Significant>false</Significant>
         </Change>
      </Region>
      ... (similar para otras regiones)
   </ComparisonTable>
   
   EXTRACCIÓN:
   Para cada región:
      buscar_seccion = f'<Region name="{region_name}">'
      SI encontrado:
         extraer_fecha_prev()
         extraer_bmd_prev()
         extraer_cambio_pct()
         extraer_si_significativo()  # Para marcador en reporte

4. FRAX:
   Memorial separa FRAX en sección dedicada con más detalle:
   
   <FRAX>
      <Input>
         <Age>67</Age>
         <BMI>24.5</BMI>
         <PreviousFracture>false</PreviousFracture>
         ... (otros factores de riesgo)
      </Input>
      <Output>
         <WithoutPriorFx>
            <MajorOsteoporotic>5.2</MajorOsteoporotic>
            <Hip>1.8</Hip>
         </WithoutPriorFx>
         <WithPriorFx>
            <MajorOsteoporotic>11.0</MajorOsteoporotic>
            <Hip>4.2</Hip>
         </WithPriorFx>
      </Output>
   </FRAX>
   
   Permite extraer tanto inputs como outputs de FRAX si es necesario

5. FORMATO DE REPORTE:
   Memorial puede incluir texto de reporte pre-generado:
   
   <GeneratedReport>
      <![CDATA[
         EXAM: BONE DENSITOMETRY
         ...
      ]]>
   </GeneratedReport>
   
   DECISIÓN:
   SI existe GeneratedReport Y parece completo:
      # Opción: Usar como base y solo actualizar valores
      # O: Ignorar y generar desde cero para consistencia
   
   IMPLEMENTACIÓN ACTUAL:
   - Ignora GeneratedReport
   - Genera nuevo reporte usando función estándar
   - Asegura consistencia con otros fabricantes
```

### Resto del Algoritmo

```
Las demás fases son idénticas a bd_extract_hologic.py:
- Generación de reporte usa misma función
- Almacenamiento idéntico
- Clasificación WHO idéntica
```

---

## COMPARACIÓN DE ALGORITMOS

### Similitudes

Todos los algoritmos comparten:
1. **Misma función de generación de reporte**: `generate_report()`
2. **Mismo esquema de base de datos**: tabla `reports.bd`
3. **Misma clasificación clínica**: Criterios WHO
4. **Mismo formato de salida**: Reporte médico estandarizado
5. **Misma lógica de comparación**: Umbral de 3% para cambio significativo

### Diferencias Principales

| Aspecto               | GE Lunar              | Hologic General       | Hologic Desert        | Hologic Memorial      |
|-----------------------|-----------------------|-----------------------|-----------------------|-----------------------|
| **Formato entrada**   | Enhanced SR (múltiple)| XML (único)           | XML (único)           | XML (único)           |
| **Parseo**            | Jerárquico recursivo  | Regex en XML          | Regex custom          | Regex con namespace   |
| **Acumulación**       | Sí (múltiples SR)     | No                    | No                    | No                    |
| **Comparaciones**     | Calcula desde BD      | Incluidas en XML      | Incluidas en XML      | Tabla de comparación  |
| **Lateralidad**       | Explícita en SR       | Detección automática  | Tag específico        | Explícita             |
| **FRAX**              | En SR si disponible   | En XML                | Sección separada      | Sección detallada     |
| **Complejidad**       | Alta                  | Media                 | Media                 | Media-Alta            |

---

## GARANTÍAS DE CALIDAD

### Validaciones Comunes a Todos los Algoritmos

```
1. VALIDACIÓN DE ENTRADA:
   SI patient_id es None O vacío:
      ERROR: "Patient ID is required"
      SALIR
   
   SI no hay archivos DICOM en directorio:
      ERROR: "No DICOM files found for patient"
      SALIR

2. VALIDACIÓN DE DATOS EXTRAÍDOS:
   Para cada valor BMD extraído:
      SI BMD < 0.3 O BMD > 2.0:
         WARNING: "BMD value {BMD} out of physiological range"
         # Aún procesar, pero marcar para revisión
   
   Para cada T-score extraído:
      SI T-score < -6.0 O T-score > 6.0:
         WARNING: "T-score value {T} unusual"
   
   SI NO hay ningún valor BMD extraído:
      ERROR: "No BMD values found in study"
      SALIR

3. VALIDACIÓN DE COMPARACIONES:
   SI cambio_porcentual > 20%:
      WARNING: "Large change detected ({cambio}%). Verify accuracy."
      # Continuar procesamiento normal

4. VALIDACIÓN DE BASE DE DATOS:
   SI falla INSERT/UPDATE:
      ERROR: Log detallado de error SQL
      INTENTAR: Rollback de transaction
      # Pero archivo de reporte ya guardado como backup

5. LOGGING:
   Cada paso crítico genera log:
   - "Procesando archivo X"
   - "Extraídos Y campos"
   - "Lumbar BMD: Z"
   - "Comparación encontrada: fecha"
   - "Reporte generado exitosamente"
   - "Datos guardados en BD"
```

### Manejo de Errores

```
TRY-CATCH en múltiples niveles:

NIVEL 1: Por archivo individual
try:
   leer_dicom(archivo)
   extraer_datos(archivo)
catch Exception as e:
   LOG: "Error en archivo {archivo}: {e}"
   CONTINUAR con siguiente archivo
   # Un archivo malo no detiene todo el procesamiento

NIVEL 2: Por región anatómica
try:
   extraer_lumbar(xml)
catch Exception as e:
   LOG: "Error extrayendo lumbar: {e}"
   lumbar_bmd = None
   # Otras regiones aún se procesan

NIVEL 3: Proceso completo
try:
   main(patient_id)
catch Exception as e:
   LOG: "Error crítico procesando paciente {patient_id}: {e}"
   GUARDAR: Stacktrace completo
   NOTIFICAR: Sistema de alertas
   RETURN: False (indica fallo)
```

---

## OPTIMIZACIONES

### Performance

```
1. PROCESAMIENTO PARALELO (no implementado aún):
   - Múltiples estudios pueden procesarse simultáneamente
   - Cada estudio es independiente
   - Pool de workers: 4-8 procesos paralelos

2. CACHÉ DE ESTUDIOS PREVIOS:
   - Última consulta de comparación en memoria
   - Evita queries repetitivas si llegan múltiples SR del mismo paciente

3. REGEX PRE-COMPILADAS:
   - Compilar patterns al inicio del script
   - Reusar compiled_pattern.search()
   - Ahorra tiempo en estudios con XML grande
```

### Memoria

```
1. LIBERACIÓN DE OBJETOS DICOM:
   Después de extraer datos de un DICOM:
   del ds  # Liberar dataset de memoria
   gc.collect()  # Forzar garbage collection si necesario

2. STREAMING DE ARCHIVOS GRANDES:
   Para XML > 1MB:
   - Leer en chunks
   - Extraer datos incrementalmente
   - No cargar todo el XML en memoria
```

---

## EXTENSIBILIDAD

### Agregar Nuevo Fabricante

```
PASOS:
1. Crear nuevo script: bd_extract_{fabricante}.py
2. Implementar funciones requeridas:
   - extract_from_format(data_source) → dict
   - Puede reusar generate_report() existente
3. Agregar detección en main.py:
   IF manufacturer == "{FABRICANTE}":
      call bd_extract_{fabricante}.py
4. Definir patterns de extracción específicos
5. Testear con múltiples estudios del fabricante
6. Documentar diferencias de formato
```

### Agregar Nueva Región Anatómica

```
PASOS:
1. Actualizar esquema de base de datos:
   ALTER TABLE reports.bd ADD COLUMN {region}_bmd DECIMAL(5,3);
   ALTER TABLE reports.bd ADD COLUMN {region}_tscore DECIMAL(4,1);
   ALTER TABLE reports.bd ADD COLUMN {region}_zscore DECIMAL(4,1);
   ... (prev_date, prev_bmd, change_percent)

2. Actualizar función extract_from_sr() o extract_from_xml():
   - Agregar patterns de búsqueda para nueva región
   - Agregar campos al diccionario de datos

3. Actualizar función generate_report():
   - Agregar has_{region} = bool(...)
   - Agregar sección de texto para nueva región
   - Agregar a lista de regiones en Technique

4. Actualizar función insert_into_database():
   - Agregar campos a INSERT statement
   - Agregar campos a UPDATE statement
   - Agregar a lista de valid_fields

5. Testear con estudios que incluyan nueva región
```

### Agregar Nueva Métrica

```
EJEMPLO: Agregar "Trabecular Bone Score (TBS)"

PASOS:
1. BD: Agregar columnas tbs, tbs_prev, tbs_change
2. Extracción: Buscar en SR/XML patterns para TBS
3. Reporte: Decidir dónde incluir TBS (¿en Findings? ¿sección separada?)
4. Almacenamiento: Incluir en INSERT/UPDATE
5. Comparación: Calcular cambios si hay valores previos
```

---

## CONCLUSIÓN

Los algoritmos de extracción están diseñados para:
- **Robustez**: Manejan variaciones en formato
- **Flexibilidad**: Fácil agregar nuevos fabricantes o regiones
- **Consistencia**: Todos producen mismo formato de reporte
- **Trazabilidad**: Logs detallados de cada paso
- **Calidad**: Validaciones en múltiples niveles

La arquitectura modular permite mantener y extender el sistema según 
necesidades cambiantes del departamento de radiología.

---

**Documento Preparado por**: Sistema de Documentación Técnica  
**Fecha**: 27 de Febrero, 2026  
**Versión**: 1.0 - Documentación de Algoritmos  
**Audiencia**: Equipo técnico y dirección médica
