# Sistema de Logging BD - DICOM Receiver

## 📁 Ubicación de Logs
Todos los logs de procesamiento BD se guardan en: `/home/ubuntu/DICOMReceiver/logs/`

## 📝 Formato de Logs

Cada paciente BD tiene su propio archivo de log: `bd_processing_{PATIENT_ID}.txt`

### Ejemplo
- Paciente 1271388: `bd_processing_1271388.txt`
- Paciente 1444058: `bd_processing_1444058.txt`

## 🔍 Pasos Registrados

Cada entrada de log sigue este formato:
```
[FECHA HORA] [PASO] [ESTADO] Detalles
```

### Pasos del Procesamiento:

1. **RECEPCION** - Recepción del archivo DICOM
   - SUCCESS: Archivo recibido correctamente con tamaño

2. **ANALISIS** - Análisis del archivo DICOM
   - SUCCESS: BodyPartExamined identificado
   - WARNING: BD no es HIP (LSPINE, etc.) - se ignora

3. **PIXEL_MAP** - Extracción del mapa de píxeles a JPEG
   - SUCCESS: Pixel map extraído correctamente
   - ERROR: Fallo en extracción

4. **REPORTE** - Generación del reporte (XML + OCR)
   - SUCCESS: Reporte generado y guardado en /reports/
   - ERROR: Error en generación con detalles del error

5. **BD_INSERT** - Inserción en base de datos PostgreSQL
   - SUCCESS: Datos insertados en tabla reports.bd
   - ERROR: Error en inserción

## 📊 Estados Posibles

- **SUCCESS**: Operación completada exitosamente
- **ERROR**: Error durante la operación (incluye detalles)
- **WARNING**: Advertencia (ej: BD no es HIP)

## 🔎 Ejemplo de Log Completo

```
[2026-01-07 16:31:55] [RECEPCION] [SUCCESS] Archivo DICOM recibido: BD_20260107_163155_570_..., Tamaño: 2.28 MB
[2026-01-07 16:31:55] [ANALISIS] [SUCCESS] BodyPartExamined: HIP
[2026-01-07 16:31:55] [ANALISIS] [SUCCESS] BD Femoral detectado - iniciando procesamiento
[2026-01-07 16:31:55] [PIXEL_MAP] [SUCCESS] Pixel map extraído correctamente
[2026-01-07 16:31:55] [REPORTE] [SUCCESS] Iniciando generación de reporte (XML + OCR)
[2026-01-07 16:31:56] [REPORTE] [SUCCESS] Reporte generado: ./reports/bd_report_1444058.txt
[2026-01-07 16:31:56] [BD_INSERT] [SUCCESS] Datos insertados en PostgreSQL tabla reports.bd
```

## 🛠️ Comandos Útiles

### Ver log de un paciente específico
```bash
cat /home/ubuntu/DICOMReceiver/logs/bd_processing_1271388.txt
```

### Ver todos los logs
```bash
ls -lh /home/ubuntu/DICOMReceiver/logs/
```

### Ver solo errores de un paciente
```bash
grep "ERROR" /home/ubuntu/DICOMReceiver/logs/bd_processing_1444058.txt
```

### Ver todos los pacientes con errores
```bash
grep -l "ERROR" /home/ubuntu/DICOMReceiver/logs/*.txt
```

### Listar últimos logs modificados
```bash
ls -lt /home/ubuntu/DICOMReceiver/logs/ | head -10
```

## 🔧 Troubleshooting

Si un paciente BD no tiene reporte:
1. Verificar que existe el log: `ls logs/bd_processing_{PATIENT_ID}.txt`
2. Ver el contenido del log para identificar en qué paso falló
3. Buscar líneas con [ERROR] para ver el problema específico
4. Ejecutar manualmente el script si es necesario:
   ```bash
   cd /home/ubuntu/DICOMReceiver
   source venv/bin/activate
   python3 extract_bd_hybrid.py {PATIENT_ID}
   ```

## 📌 Notas Importantes

- Los logs se crean automáticamente cuando llega un estudio BD
- Cada recepción de archivo HIP genera nuevas entradas en el log
- Si un paciente tiene múltiples imágenes HIP, habrá múltiples secuencias de logs
- Los logs persisten indefinidamente (considerar rotación manual si crecen mucho)
