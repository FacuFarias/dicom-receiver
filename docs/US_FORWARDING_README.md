# Sistema de Forwarding Selectivo de Estudios US (Ultrasound)

## Resumen

El DICOMReceiver ahora cuenta con un sistema de forwarding automático y selectivo de estudios US basado en criterios configurables. Solo los estudios que cumplan con los criterios especificados serán reenviados automáticamente al servidor DICOM destino.

## 🎯 Criterio Actual

**Estudios US que contengan "Thyroid" en StudyDescription** se reenvían automáticamente a:
- **IP**: 3.148.99.29
- **Puerto**: 11112
- **AET**: DICOM_RECEIVER

## ⚙️ Configuración

La configuración se encuentra en: [config.py](config.py)

```python
US_FORWARDING = {
    'enabled': True,                      # Activar/desactivar forwarding
    'host': '3.148.99.29',                # IP del servidor destino
    'port': 11112,                        # Puerto del servidor destino
    'aet': 'DICOM_RECEIVER',              # AE Title destino
    'calling_aet': 'QII_DICOM_SENDER',    # Nuestro AE Title
    'timeout': 30,                        # Timeout en segundos
    'retry_attempts': 3,                  # Intentos de reenvío
    
    # Criterios de forwarding (condiciones OR)
    'criteria': {
        'study_description_contains': ['Thyroid'],  # Case-insensitive
        # 'body_part_contains': [],
        # 'series_description_contains': [],
    }
}
```

## 📋 Cómo Funciona

### Flujo de Recepción US

1. **Recepción del DICOM US**
   - Se guarda en `dicom_storage/{PatientID}/{StudyInstanceUID}/`
   - Se crea enlace/copia en `dicom_storage/US/{PatientID}/{StudyInstanceUID}/`
   - Se registra en `logs/us_reception.log`

2. **Evaluación de Criterios**
   - Se verifica el `StudyDescription` del DICOM
   - Búsqueda **case-insensitive** de términos configurados
   - Variantes aceptadas: `Thyroid`, `thyroid`, `THYROID`, `ThYrOiD`, etc.

3. **Decisión de Forwarding**
   
   **Si cumple criterios** (ej: contiene "Thyroid"):
   ```
   🎯 US cumple criterios de forwarding: StudyDescription contiene 'Thyroid'
   🔄 Forwarding US image to DICOM_RECEIVER@3.148.99.29:11112
   ✓ US study forwarded successfully
   ```
   
   **Si NO cumple criterios**:
   ```
   ℹ️  US no cumple criterios de forwarding: No cumple criterios de forwarding
   ℹ️  File saved locally only
   ```

## 📊 Ejemplos de StudyDescription

### ✅ SE REENVÍAN (contienen "Thyroid")
- `US Thyroid Examination`
- `THYROID ULTRASOUND COMPLETE`
- `ultrasound thyroid bilateral`
- `Thyroid Left Lobe`
- `NECK - THYROID GLAND`

### ❌ NO SE REENVÍAN (sin "Thyroid")
- `US PELVIS COMPLETE`
- `US Abdomen Complete`
- `Ultrasound Carotid Arteries`
- `US Breast Bilateral`

## 🔄 Reintentos y Tolerancia a Fallos

- **3 intentos** de reenvío automático
- **2 segundos** de espera entre intentos
- **30 segundos** de timeout por intento
- Si falla el reenvío: el archivo **siempre se guarda localmente**

## 📝 Logs

### Log de Recepción US
Ubicación: `logs/us_reception.log`

Formato:
```
[2026-03-23 13:00:00] [Patient: {ID}] [Study: {UID}] Recibido - Fabricante: {...}, BodyPart: {...}, Tamaño: {...} MB
[2026-03-23 13:00:01] [Patient: {ID}] [Study: {UID}] FORWARD_SUCCESS - Enviado a 3.148.99.29:11112 (DICOM_RECEIVER) - StudyDescription contiene 'Thyroid'
```

**Entradas del log:**
- `Recibido` - Archivo US recibido y guardado localmente
- `FORWARD_SUCCESS` - Estudio reenviado exitosamente al servidor destino
- `FORWARD_FAILED` - Intento de reenvío falló (archivo guardado localmente)

### Log Principal del Servicio
```bash
journalctl -u dicom-receiver.service -f
```

## 🗑️ Limpieza Automática

Los archivos US se eliminan automáticamente después de **48 horas** de su recepción.

### Políticas de Retención

- **Archivos US**: 48 horas (2 días)
- **Archivos BD y otros**: 72 horas (3 días)

### Timer de Limpieza

El sistema ejecuta limpieza automática cada hora:
```bash
# Ver estado del timer
systemctl status dicom-cleanup.timer

# Ver próxima ejecución
systemctl list-timers dicom-cleanup.timer

# Ver log de limpieza
tail -f /home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log
```

### Limpieza Manual

```bash
# Ver qué se eliminaría (dry run, sin eliminar)
bash /home/ubuntu/DICOMReceiver/test_cleanup_dry_run.sh

# Ejecutar limpieza manualmente
bash /home/ubuntu/DICOMReceiver/cleanup_dicom_files.sh
```

### Por qué 48 horas para US

Los estudios US que cumplen criterios se reenvían automáticamente al servidor destino. Una vez reenviados exitosamente, el servidor local solo mantiene una copia de respaldo por **48 horas** antes de eliminarlos automáticamente para liberar espacio.

Si el reenvío falla, el archivo se mantiene localmente (y se reintentará el reenvío si se vuelve a procesar).

## 🧪 Testing

### Test de Criterios
```bash
cd /home/ubuntu/DICOMReceiver
python3 test_us_criteria.py
```

Verifica que:
- ✅ Configuración se carga correctamente
- ✅ Criterios detectan "Thyroid" (case-insensitive)
- ✅ Estudios sin "Thyroid" no se marcan para forward

### Test de Envío Real
```bash
cd /home/ubuntu/DICOMReceiver
source venv/bin/activate
python3 test_send_us.py
```

Verifica:
- ✅ Conectividad con servidor destino
- ✅ C-STORE funciona correctamente
- ✅ El servidor destino acepta estudios

## ⚡ Agregar Más Criterios

### Ejemplo: Agregar "Carotid" como criterio adicional

Editar [config.py](config.py):
```python
'criteria': {
    'study_description_contains': ['Thyroid', 'Carotid'],
}
```

### Ejemplo: Usar BodyPartExamined en lugar de StudyDescription
```python
'criteria': {
    'body_part_contains': ['NECK', 'THYROID'],
}
```

### Ejemplo: Combinar múltiples criterios (OR)
```python
'criteria': {
    'study_description_contains': ['Thyroid'],
    'body_part_contains': ['NECK'],
    'series_description_contains': ['Doppler'],
}
```
*Nota: Los criterios son OR - si cumple cualquiera, se reenvía*

## 🔧 Deshabilitar Forwarding

Editar [config.py](config.py):
```python
US_FORWARDING = {
    'enabled': False,  # ← Cambiar a False
    ...
}
```

Reiniciar servicio:
```bash
sudo systemctl restart dicom-receiver.service
```

## 📊 Monitoreo en Tiempo Real

```bash
# Ver solo recepciones US
tail -f /home/ubuntu/DICOMReceiver/logs/us_reception.log

# Ver forwarding en tiempo real
journalctl -u dicom-receiver.service -f | grep -E "(Thyroid|FORWARD|🎯|🔄)"

# Ver archivos US recibidos
ls -la /home/ubuntu/DICOMReceiver/dicom_storage/US/
```

## 🚀 Después de Cambios en Configuración

Siempre reiniciar el servicio:
```bash
sudo systemctl restart dicom-receiver.service
systemctl status dicom-receiver.service
```

## 📅 Implementación

**Fecha**: Marzo 23, 2026

**Archivos Modificados**:
- [main.py](main.py) - Funciones `should_forward_us()` y actualización de `forward_us_image()`
- [config.py](config.py) - Configuración `US_FORWARDING` con criterios

**Scripts de Prueba**:
- [test_us_criteria.py](test_us_criteria.py) - Verificación de lógica de criterios
- [test_send_us.py](test_send_us.py) - Test de conectividad y envío DICOM

## ✅ Estado Actual

- ✅ Forwarding habilitado
- ✅ Criterio: StudyDescription contiene "Thyroid" (case-insensitive)
- ✅ Destino verificado: 3.148.99.29:11112 (DICOM_RECEIVER)
- ✅ Servicio reiniciado y activo
- ✅ Tests pasados correctamente
