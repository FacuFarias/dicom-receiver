# Sistema de Logging Implementado - BD Processing

## Fecha de Implementación
2026-01-07

## Cambios Realizados

### 1. Logging Detallado en Archivos TXT
- **Directorio**: `/home/ubuntu/DICOMReceiver/logs/`
- **Formato**: `bd_processing_{patient_id}.txt`
- **Contenido**: Log completo de todos los pasos del procesamiento BD

### 2. Función de Logging en main.py
```python
def log_bd_processing(patient_id, step, status, message):
    """
    Guarda un log detallado del procesamiento de BD en archivo TXT
    
    Args:
        patient_id: ID del paciente
        step: RECEPCION, ANALISIS, PIXEL_MAP, REPORTE, BD_INSERT
        status: SUCCESS, ERROR, WARNING
        message: Mensaje descriptivo
    """
```

### 3. Pasos Registrados

#### RECEPCION
- Archivo DICOM recibido
- BodyPartExamined detectado
- Tamaño del archivo

#### ANALISIS  
- Verificación de BodyPartExamined (HIP vs LSPINE)
- Decisión de procesamiento

#### PIXEL_MAP
- Extracción de imagen JPEG del DICOM
- Estado: éxito o advertencia

#### REPORTE
- Inicio de script extract_bd_hybrid.py
- Comando ejecutado
- Salida del script (STDOUT/STDERR hasta 2000 caracteres)

#### BD_INSERT
- Inserción exitosa en PostgreSQL
- Errores si los hay
- Timeouts si ocurren

### 4. Ruta Completa de Tesseract
- **Archivo**: `extract_bd_hybrid.py` línea 149
- **Ruta**: `/usr/bin/tesseract`
- **Razón**: El servicio systemd no tiene /usr/bin en PATH por defecto

### 5. Integración en handle_store()
El proceso BD ahora:
1. Recibe archivo DICOM → Log RECEPCION
2. Analiza BodyPartExamined → Log ANALISIS  
3. Extrae pixel map → Log PIXEL_MAP
4. Ejecuta extract_bd_hybrid.py → Log REPORTE
5. Captura resultado del script → Log BD_INSERT
6. Si hay error, captura STDERR/STDOUT completo

## Ejemplo de Log Generado

```
[2026-01-07 16:57:31] [RECEPCION] [SUCCESS] BD recibido - BodyPartExamined: HIP, Tamaño: 2.28 MB
[2026-01-07 16:57:31] [ANALISIS] [SUCCESS] Iniciando procesamiento de BD - Archivo: BD_20260107_165731_899_1.2.840...
[2026-01-07 16:57:31] [PIXEL_MAP] [SUCCESS] Pixel map extraído exitosamente como JPEG
[2026-01-07 16:57:31] [REPORTE] [SUCCESS] Ejecutando: python3 /home/ubuntu/DICOMReceiver/extract_bd_hybrid.py 1271388
[2026-01-07 16:57:36] [BD_INSERT] [SUCCESS] Reporte BD generado e insertado en PostgreSQL correctamente
```

## Beneficios

### Troubleshooting
- Ver exactamente dónde falla el proceso
- Capturar errores de tesseract, PIL, psycopg2
- Saber si el problema es en recepción, extracción o base de datos

### Auditoría
- Historial completo de procesamiento por paciente
- Timestamps precisos de cada paso
- Trazabilidad de errores pasados

### Monitoreo
- Ver qué estudios BD fueron rechazados (LSPINE)
- Detectar timeouts en procesamiento
- Identificar estudios con pixel map corrupto

## Servicio Actualizado
- Estado: ✓ Corriendo
- PID: 849689
- Logging: ✓ Activo
- Tesseract: ✓ Ruta completa configurada
- Última reiniciación: 2026-01-07 17:05:34 UTC

## Próximos Pasos

Al recibir el siguiente estudio BD:
1. Se creará automáticamente `/home/ubuntu/DICOMReceiver/logs/bd_processing_{patient_id}.txt`
2. Cada paso del procesamiento se registrará con timestamp
3. Si hay error, STDERR completo estará en el log
4. El reporte se generará y guardará en PostgreSQL (si es HIP)

## Archivos Modificados
- `/home/ubuntu/DICOMReceiver/main.py` - Agregado logging en handle_store()
- `/home/ubuntu/DICOMReceiver/extract_bd_hybrid.py` - Ruta completa tesseract (ya estaba)

## Testing
Para probar el sistema, enviar un estudio BD HIP a:
- IP: (tu servidor)
- Puerto: 5665
- AE Title: DICOMRECEIVER

El log se generará automáticamente en `/home/ubuntu/DICOMReceiver/logs/bd_processing_{patient_id}.txt`
