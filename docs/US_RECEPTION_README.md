# Soporte para Recepción de Estudios US (Ultrasound)

## Resumen de Cambios

El DICOMReceiver ahora tiene soporte completo para recibir y almacenar estudios de Ultrasound (US).

## Funcionalidades Implementadas

### 1. **Almacenamiento Dedicado**
Los estudios US se guardan en una estructura dedicada:
```
dicom_storage/US/{PatientID}/{StudyInstanceUID}/
```

Además del almacenamiento estándar en:
```
dicom_storage/{PatientID}/{StudyInstanceUID}/
```

### 2. **Logging Centralizado**
Todas las recepciones de US se registran en:
```
logs/us_reception.log
```

El log incluye:
- Timestamp de recepción
- Patient ID
- Study Instance UID
- Fabricante y modelo del equipo
- Body part examinado
- Descripción de la serie
- Tamaño del archivo
- Nombre del archivo

### 3. **Formato del Log**
```
[YYYY-MM-DD HH:MM:SS] [Patient: {ID}] [Study: {UID}] Recibido - Fabricante: {}, Modelo: {}, BodyPart: {}, Series: {}, Tamaño: {} MB, Archivo: {}
```

### 4. **Optimización de Almacenamiento**
- El sistema intenta crear **enlaces duros** (hard links) para evitar duplicación de datos
- Si los enlaces duros fallan (ej: diferentes filesystems), copia el archivo automáticamente

### 5. **Integración con Sistema de Forwarding**
- El código mantiene compatibilidad con `forward_us_image()` para reenvío opcional a sistemas externos
- El forwarding puede habilitarse/deshabilitarse en `config.py` mediante `US_FORWARDING`

## Ejemplo de Flujo

Cuando llega un estudio US:

1. ✅ Se guarda en ubicación estándar: `dicom_storage/{PatientID}/{StudyInstanceUID}/`
2. ✅ Se crea enlace/copia en: `dicom_storage/US/{PatientID}/{StudyInstanceUID}/`
3. ✅ Se registra en: `logs/us_reception.log`
4. ✅ Se reenvía a sistema externo (si está configurado)

## Logs Disponibles

- **US Reception**: `logs/us_reception.log` - Todos los US recibidos
- **BD Processing**: `logs/bd_processing.log` - Procesamiento de Bone Density
- **Service Logs**: Salida estándar del servicio systemd

## Verificación

Para verificar que un US fue recibido correctamente:

```bash
# Ver últimas recepciones US
tail -f /home/ubuntu/DICOMReceiver/logs/us_reception.log

# Ver archivos US recibidos
ls -la /home/ubuntu/DICOMReceiver/dicom_storage/US/

# Ver para un paciente específico
ls -la /home/ubuntu/DICOMReceiver/dicom_storage/US/{PatientID}/
```

## Notas Técnicas

- El sistema detecta US mediante el campo `Modality` del DICOM
- Se extraen automáticamente metadatos: Manufacturer, Model, BodyPart, SeriesDescription
- Compatible con equipos de diferentes fabricantes (Philips, GE, Siemens, etc.)
- Los enlaces duros ahorran espacio en disco (mismo inode, un solo archivo físico)

## Fecha de Implementación

Marzo 23, 2026
