# Transfer Syntax Support Documentation

Este documento describe los Transfer Syntaxes y SOP Classes soportados por el DICOM Receiver optimizado para alto rendimiento.

## Objetivo

Minimizar impacto en el gateway dcm4chee evitando:
- Rechazos que fuercen transcodificación en el gateway
- Rechazos que retrasen envío a otros destinos (ONEPACS_WEB)
- Operaciones de compresión/descompresión innecesarias

## Transfer Syntaxes Soportados

### ✅ Soportados y Recomendados

| Transfer Syntax | UID | Notas |
|----------------|-----|-------|
| **Implicit VR Little Endian** | 1.2.840.10008.1.2 | Default DICOM, sin compresión |
| **Explicit VR Little Endian** | 1.2.840.10008.1.2.1 | Estándar, metadatos explícitos |
| **JPEG Lossless** | 1.2.840.10008.1.2.4.70 | Compresión sin pérdida, común en BD/US |

**Características:**
- No requieren transcodificación
- Bajo uso de CPU en el receptor
- Compatible con la mayoría de modalidades

### ⚠️ Soportados con Limitaciones

| Transfer Syntax | UID | Estado | Notas |
|----------------|-----|--------|-------|
| **JPEG 2000 Lossless** | 1.2.840.10008.1.2.4.90 | Comentado | Problemas con PDU pequeños (fragmentación) |
| **JPEG 2000** | 1.2.840.10008.1.2.4.91 | Comentado | Problemas con PDU pequeños (fragmentación) |

**Problema detectado con JPEG2000:**
```
dcm4chee gateway envía JPEG2000 con PDUs muy pequeños (64KB chunks)
→ pynetdicom tiene problemas de fragmentación con transfer de datos largos
→ Gateway puede experimentar timeouts esperando ACKs
```

**Solución temporal:** Transfer Syntaxes JPEG2000 están comentados en el código para evitar asociaciones que puedan causar cuellos de botella.

**Futuro:** Si dcm4chee configura PDU size más grande (256KB o 512KB), descomentar soporte JPEG2000.

### ❌ No Soportados (Rechazados)

Ninguno - el sistema acepta todos los Transfer Syntaxes estándar aunque no tenga soporte específico para procesamiento. Esto evita que el gateway deba transcodificar.

## SOP Classes Soportadas

### ✅ Verified Support

| SOP Class | UID | Modalidad | Notas |
|-----------|-----|-----------|-------|
| **CT Image Storage** | 1.2.840.10008.5.1.4.1.1.2 | CT | Totalmente soportado |
| **MR Image Storage** | 1.2.840.10008.5.1.4.1.1.4 | MR | Totalmente soportado |
| **Ultrasound Image Storage** | 1.2.840.10008.5.1.4.1.1.6.1 | US | Con reenvío automático según criterios |
| **Ultrasound Multi-frame Image Storage** | 1.2.840.10008.5.1.4.1.1.3.1 | US | Con reenvío automático según criterios |
| **Secondary Capture Image Storage** | 1.2.840.10008.5.1.4.1.1.7 | BD/Otros | Común en BD (densitometría) |
| **X-Ray Angiographic Image Storage** | 1.2.840.10008.5.1.4.1.1.12.1 | XA | Almacenamiento solamente |
| **Computed Radiography Image Storage** | 1.2.840.10008.5.1.4.1.1.1 | CR | Almacenamiento solamente |
| **Digital X-Ray Image Storage - Presentation** | 1.2.840.10008.5.1.4.1.1.1.1 | DX | Almacenamiento solamente |
| **Digital X-Ray Image Storage - Processing** | 1.2.840.10008.5.1.4.1.1.1.1.1 | DX | Almacenamiento solamente |

### 📊 Structured Reports (SR)

| SOP Class | UID | Notas |
|-----------|-----|-------|
| **Basic Text SR** | 1.2.840.10008.5.1.4.1.1.88.11 | Para reportes GE Lunar BD |
| **Enhanced SR** | 1.2.840.10008.5.1.4.1.1.88.22 | Para reportes GE Lunar BD |
| **Comprehensive SR** | 1.2.840.10008.5.1.4.1.1.88.33 | Para reportes GE Lunar BD |

**Uso:** GE Lunar envía resultados de densitometría como SR en lugar de Secondary Capture.

### 🔍 Verification

| SOP Class | UID | Notas |
|-----------|-----|-------|
| **Verification SOP Class** | 1.2.840.10008.1.1 | C-ECHO para verificar conectividad |

## Procesamiento Específico por Modalidad

### BD (Bone Density / Densitometría Ósea)

**Modalidades:** `BD`, `SR` (GE Lunar)

**Procesamiento asíncrono:**
1. Almacenamiento inmediato en disco
2. Detección de fabricante (HOLOGIC vs GE Lunar)
3. Extracción de XML embebido (tag 0x0019, 0x1000)
4. Ejecución de script de análisis (`bd_extract_hologic.py` o `bd_extract_ge.py`)
5. Inserción de resultados en PostgreSQL

**Transfer Syntaxes comunes:**
- Implicit VR Little Endian (HOLOGIC)
- Explicit VR Little Endian (GE Lunar)
- JPEG Lossless (algunos modelos HOLOGIC)

### US (Ultrasound / Ultrasonido)

**Modalidades:** `US`

**Procesamiento asíncrono:**
1. Almacenamiento inmediato en disco
2. Verificación de criterios de reenvío (thyroid, liver, testicular, carotid, abdomen)
3. Reenvío a servidor AI externo (3.148.99.29:11112) si cumple criterios
4. Hasta 3 reintentos con timeout de 30s cada uno

**Transfer Syntaxes comunes:**
- Explicit VR Little Endian (majority)
- Implicit VR Little Endian
- JPEG Lossless (advanced scanners)

### CT/MR/CR/DX (Otras Modalidades)

**Procesamiento:**
- Almacenamiento inmediato en disco
- Sin procesamiento adicional (almacenamiento puro)

**Transfer Syntaxes comunes:**
- Implicit VR Little Endian
- Explicit VR Little Endian
- JPEG Lossless (compression)

## Configuración de Asociación DICOM

### Application Entity (AE)

```python
AE Title: DICOM_RECEIVER
Port: 5665
Host: 0.0.0.0 (escucha en todas las interfaces)
```

### PDU Settings

```python
Maximum PDU Size: 65536 (64KB, negociado con cliente)
Network Timeout: 600 segundos (10 min)
ACSE Timeout: 120 segundos (2 min, asociación)
DIMSE Timeout: 600 segundos (10 min, operaciones C-STORE)
```

**Nota sobre PDU Size:**
- 64KB es suficiente para la mayoría de casos
- JPEG2000 puede requerir PDUs más grandes para evitar fragmentación excesiva
- dcm4chee 2 típicamente envía con PDUs pequeños (problema conocido)

## Performance Optimization

### C-STORE Response Timing

**Modo Legacy (ASYNC_PROCESSING.enabled = False):**
```
C-STORE recibido
    ↓ [almacenamiento a disco]
    ↓ [procesamiento BD/US síncrono - hasta 90 segundos]
    ↓ [extracción de píxeles síncrona]
C-STORE-RSP enviado (0x0000)
```
**Latencia:** 30-90 segundos

**Modo Optimizado (ASYNC_PROCESSING.enabled = True):**
```
C-STORE recibido
    ↓ [validación DICOM]
    ↓ [detección de duplicados - <50ms]
    ↓ [almacenamiento a disco - <500ms]
C-STORE-RSP enviado (0x0000) ← INMEDIATO
    ↓ [procesamiento en background]
```
**Latencia:** <1 segundo

### Beneficios para el Gateway

1. **Sin bloqueos:** Gateway no espera procesamiento interno
2. **Sin rechazos:** Aceptamos todos los Transfer Syntaxes estándar
3. **Sin serialización:** Múltiples asociaciones concurrentes permitidas
4. **Sin transcodificación:** No forzamos conversión en el gateway

## Troubleshooting

### Problema: Gateway reporta timeouts

**Síntomas:**
```
dcm4chee logs:
Association timeout with DICOM_RECEIVER
```

**Causas posibles:**
1. Procesamiento síncrono activado (ASYNC_PROCESSING.enabled = False)
2. Cola de procesamiento llena (>1000 items)
3. Workers de background saturados

**Solución:**
```bash
# Verificar configuración
grep "enabled" /home/ubuntu/DICOMReceiver/config.py

# Verificar logs de cola
tail -f /home/ubuntu/DICOMReceiver/logs/queue_monitor.log

# Habilitar modo asíncrono
sed -i "s/'enabled': False/'enabled': True/g" /home/ubuntu/DICOMReceiver/config.py
systemctl restart dicom-receiver.service
```

### Problema: JPEG2000 falla

**Síntomas:**
```
dcm4chee logs:
No supported Transfer Syntax for JPEG2000
```

**Causa:** JPEG2000 está comentado debido a problemas de fragmentación PDU

**Solución temporal:** Configurar dcm4chee para enviar en Explicit VR Little Endian

**Solución permanente:** 
1. Aumentar PDU size en dcm4chee a 256KB+
2. Descomentar JPEG2000 en main.py líneas 1018-1019
3. Testing exhaustivo con imágenes grandes

### Problema: US no se reenvía

**Síntomas:**
```
logs/us_reception.log:
Imagen recibida pero no cumple criterios
```

**Causa:** Criterios de reenvío no coinciden con StudyDescription/BodyPartExamined

**Solución:**
```python
# Editar config.py
US_FORWARDING = {
    'criteria': {
        'study_description_contains': ['Thyroid', 'Tu_Nuevo_Termino'],
        # Agregar términos necesarios
    }
}
```

## Referencias

- [DICOM Standard Part 5: Data Structures](http://dicom.nema.org/medical/dicom/current/output/html/part05.html)
- [DICOM Transfer Syntax Registry](http://dicom.nema.org/medical/dicom/current/output/html/part06.html)
- [pynetdicom Documentation](https://pydicom.github.io/pynetdicom/)

## Changelog

### 2026-04-03
- ✅ Agregado soporte para JPEG Lossless
- ✅ Agregado Ultrasound Multi-frame Image Storage
- ⚠️  Comentado JPEG2000 debido a problemas de fragmentación PDU
- ✅ Documentado comportamiento de procesamiento asíncrono
- ✅ Agregado troubleshooting para problemas comunes
