# Guía de Deployment - DICOM Receiver Optimizado

## Resumen de Cambios

Se ha transformado el DICOMReceiver de arquitectura síncrona bloqueante a modelo asíncrono fire-and-forget, eliminando cuellos de botella en el gateway dcm4chee.

### ¿Qué se cambió?

1. **Nuevo sistema de colas** (`queue_manager.py`)
   - Pools de ThreadPoolExecutor para US forwarding (2 workers), BD processing (4 workers), pixel extraction (2 workers)
   - Monitoreo automático de tamaños de cola
   - Graceful shutdown (finaliza trabajos en vuelo)

2. **Workers asíncronos** (carpeta `workers/`)
   - `us_worker.py` - Reenvío US con reintentos (hasta 90s) en background
   - `bd_worker.py` - Procesamiento BD (subprocess + DB) en background
   - `pixel_worker.py` - Extracción de píxeles JPEG en background

3. **Configuración extendida** (`config.py`)
   - `ASYNC_PROCESSING` - Control de workers y feature flag
   - `PERFORMANCE` - Control de modo de respuesta y logging

4. **Refactorización de main.py**
   - Respuesta C-STORE-RSP inmediata (<1s) cuando async habilitado
   - Transfer Syntax mejorado: agregado JPEG Lossless
   - SOP Class agregado: Ultrasound Multi-frame Image Storage
   - Logging reducido en hot path (DEBUG vs INFO configurable)
   - Graceful shutdown del sistema de colas

5. **Documentación** (`TRANSFER_SYNTAX_README.md`)
   - Detalles de Transfer Syntaxes soportados
   - Troubleshooting para problemas comunes
   - Explicación de JPEG2000 (comentado temporalmente)

## Estado Actual

**Modo actual: DESHABILITADO (Backward Compatible)**

```python
# config.py
ASYNC_PROCESSING = {
    'enabled': False,  # ← DESHABILITADO por defecto
    ...
}
```

El sistema funciona **exactamente como antes** hasta que habilites el modo asíncrono. Esto permite:
- Deployment sin downtime
- Testing exhaustivo antes de activar
- Rollback instantáneo si hay problemas

## Plan de Deployment (Zero Downtime)

### Fase 1: Deployment con Async Deshabilitado (✅ COMPLETADO)

**Ya realizado - Archivos actualizados:**
- ✅ `queue_manager.py` creado
- ✅ `workers/` creados (us_worker.py, bd_worker.py, pixel_worker.py)
- ✅ `config.py` extendido (ASYNC_PROCESSING, PERFORMANCE)
- ✅ `main.py` refactorizado (soporte async + backward compatibility)
- ✅ `TRANSFER_SYNTAX_README.md` documentado

**Sistema actual:** Funciona en modo legacy (síncrono), sin cambios de comportamiento.

### Fase 2: Testing Pre-Activación

**Verificar que el código funciona en modo legacy:**

```bash
# 1. Verificar que no hay errores de sintaxis
cd /home/ubuntu/DICOMReceiver
python3 -c "import main; import queue_manager; print('✓ Imports OK')"

# 2. Verificar configuración actual
grep "'enabled':" config.py | head -1
# Debe mostrar: 'enabled': False

# 3. Restart del servicio (usa código nuevo pero modo legacy)
sudo systemctl restart dicom-receiver.service

# 4. Verificar que inició correctamente
sudo systemctl status dicom-receiver.service --no-pager | head -20

# 5. Ver logs - debe mostrar "Modo SÍNCRONO (legacy)"
sudo journalctl -u dicom-receiver.service -n 50 --no-pager | grep -i "modo"
```

**Salida esperada:**
```
⚠️  Modo SÍNCRONO (legacy) - procesamiento bloqueante
```

**Testing funcional:**
- Enviar 5-10 estudios de prueba (CT, BD, US) desde dcm4chee
- Verificar que se guardan correctamente en `./dicom_storage/`
- Verificar que BD se procesa (logs en `logs/bd_processing.log`)
- Verificar que US se reenvía si cumple criterios (logs en `logs/us_reception.log`)

**Criterio de éxito Fase 2:**
- ✅ Servicio inicia sin errores
- ✅ Procesa estudios normalmente (legacy mode)
- ✅ No hay regresiones vs. versión anterior

### Fase 3: Activación de Modo Asíncrono

**⚠️ REALIZAR EN VENTANA DE BAJO TRÁFICO (ej: noche, fin de semana)**

```bash
# 1. Backup de configuración actual
cp /home/ubuntu/DICOMReceiver/config.py /home/ubuntu/DICOMReceiver/config.py.backup

# 2. Habilitar modo asíncrono
sed -i "s/'enabled': False/'enabled': True/g" /home/ubuntu/DICOMReceiver/config.py

# 3. Verificar cambio
grep "'enabled':" /home/ubuntu/DICOMReceiver/config.py | head -1
# Debe mostrar: 'enabled': True

# 4. Restart del servicio
sudo systemctl restart dicom-receiver.service

# 5. Verificar inicio en modo ASYNC
sudo journalctl -u dicom-receiver.service -n 50 --no-pager | grep -i "modo"
```

**Salida esperada:**
```
✅ Modo ASÍNCRONO habilitado - respuesta inmediata C-STORE-RSP
   US workers: 2
   BD workers: 4
   Pixel workers: 2
✓ QueueManager inicializado - US workers: 2, BD workers: 4, Pixel workers: 2
```

### Fase 4: Monitoreo Post-Activación

**Monitorear durante las primeras 2-4 horas:**

```bash
# 1. Ver logs en tiempo real
sudo journalctl -u dicom-receiver.service -f

# 2. Buscar alertas de colas llenas (cada 5 min)
watch -n 300 'sudo journalctl -u dicom-receiver.service -n 200 --no-pager | grep -i "cola"'

# 3. Verificar estadísticas de workers
sudo journalctl -u dicom-receiver.service -n 500 --no-pager | grep "📊"

# 4. Verificar que US forwarding funciona (async)
tail -f /home/ubuntu/DICOMReceiver/logs/us_forwarding_failed.log
# Debe estar vacío o con pocos errores

# 5. Verificar procesamiento BD (async)
tail -f /home/ubuntu/DICOMReceiver/logs/bd_processing.log
```

**Métricas clave a observar:**

1. **Latencia C-STORE-RSP:** Debe ser <1-2 segundos
2. **Tamaños de cola:** Deben permanecer <100 items
3. **Fallos de forwarding US:** Deben registrarse en log pero no bloquear gateway
4. **Procesamiento BD:** Debe completarse en background sin fallos

**Alertas críticas a buscar:**
```bash
# Buscar alertas CRITICAL
sudo journalctl -u dicom-receiver.service -n 500 --no-pager | grep "CRITICAL"

# Típicas alertas:
# "🚨 Cola US casi llena: 850/1000" ← Aumentar us_workers si persiste
# "🚨 Cola BD casi llena: 900/1000" ← Aumentar bd_workers si persiste
```

### Fase 5: Ajuste de Performance (Si Necesario)

**Si las colas se llenan constantemente:**

```bash
# Editar config.py - aumentar workers
nano /home/ubuntu/DICOMReceiver/config.py

# Ejemplo: duplicar workers
ASYNC_PROCESSING = {
    'enabled': True,
    'us_workers': 4,      # Era 2
    'bd_workers': 8,      # Era 4
    'pixel_workers': 4,   # Era 2
    ...
}

# Restart
sudo systemctl restart dicom-receiver.service
```

**Si hay problemas con US forwarding:**

```bash
# Ver log de fallos
cat /home/ubuntu/DICOMReceiver/logs/us_forwarding_failed.log

# Típicos problemas:
# - Destino AI no responde (3.148.99.29:11112)
# - Timeout en reintentos
# - Archivo faltante (race condition)

# Solución temporal: desactivar forwarding si no es crítico
nano /home/ubuntu/DICOMReceiver/config.py
# US_FORWARDING['enabled'] = False
```

## Rollback Plan

**Si hay problemas críticos, rollback es inmediato:**

```bash
# 1. Deshabilitar modo async
sed -i "s/'enabled': True/'enabled': False/g" /home/ubuntu/DICOMReceiver/config.py

# 2. O restaurar backup
cp /home/ubuntu/DICOMReceiver/config.py.backup /home/ubuntu/DICOMReceiver/config.py

# 3. Restart
sudo systemctl restart dicom-receiver.service

# 4. Verificar modo legacy
sudo journalctl -u dicom-receiver.service -n 50 --no-pager | grep "Modo SÍNCRONO"
```

**Sistema vuelve a comportamiento original en <30 segundos.**

## Verificación de Impacto en Gateway

**Objetivo:** Gateway dcm4chee NO debe experimentar timeouts ni retrasos hacia ONEPACS_WEB.

```bash
# En servidor dcm4chee, monitorear logs:
# (ajustar rutas según instalación dcm4chee 2)

# Buscar timeouts hacia DICOM_RECEIVER
grep -i "timeout.*DICOM_RECEIVER" /opt/dcm4chee/server/default/log/server.log

# Buscar fallos de asociación
grep -i "association.*failed.*DICOM_RECEIVER" /opt/dcm4chee/server/default/log/server.log

# Buscar retrasos en envío a ONEPACS_WEB
grep -i "ONEPACS_WEB" /opt/dcm4chee/server/default/log/server.log | grep -i "delay\|timeout\|fail"
```

**Criterios de éxito:**
- ✅ Sin timeouts hacia DICOM_RECEIVER
- ✅ Sin fallos de asociación con DICOM_RECEIVER
- ✅ Sin retrasos en envío a ONEPACS_WEB
- ✅ Throughput general del gateway no disminuye

## Configuración Avanzada

### Ajustar Timeouts

Si hay timeouts frecuentes en US forwarding:

```python
# config.py
US_FORWARDING = {
    'timeout': 60,  # Aumentar de 30 a 60 segundos
    'retry_attempts': 5,  # Aumentar reintentos
    ...
}
```

### Ajustar Logging

Reducir aún más verbosidad para alto tráfico:

```python
# config.py
PERFORMANCE = {
    'immediate_response_mode': True,
    'log_per_instance': False,  # DEBUG en lugar de INFO por instancia
}

# Y en logging básico
LOGGING = {
    'level': 'WARNING',  # Solo warnings y errors
    ...
}
```

### Monitoreo de Queue Sizes

El sistema loguea tamaños de cola cada 60s si >10 items pendientes:

```bash
# Ver monitoreo de colas
sudo journalctl -u dicom-receiver.service -n 1000 --no-pager | grep "📊 Colas pendientes"

# Ejemplo de salida normal:
# 📊 Colas pendientes - US: 3, BD: 12, Pixel: 5 (Total: 20)

# Salida preocupante (colas creciendo):
# 📊 Colas pendientes - US: 450, BD: 320, Pixel: 180 (Total: 950)
# ← Aumentar workers o investigar por qué procesan lento
```

## Testing de Carga

**Antes de Fase 3, realizar test de carga:**

```bash
# Usar herramienta de testing DICOM (ej: dcmtk storescu)
# Enviar 50 CT + 50 US + 50 BD concurrentemente

# Con modo async habilitado, medir:
# 1. Latencia C-STORE-RSP (debe ser <2s)
# 2. Tamaño máximo de colas (debe ser <100)
# 3. Tiempo total de procesamiento background

# Script ejemplo (ajustar rutas):
for i in {1..50}; do
    storescu -aec DICOM_RECEIVER localhost 5665 test_ct_$i.dcm &
    storescu -aec DICOM_RECEIVER localhost 5665 test_us_$i.dcm &
    storescu -aec DICOM_RECEIVER localhost 5665 test_bd_$i.dcm &
done
wait

# Verificar que todos se procesaron
ls -lh dicom_storage/*/  # Deben estar todos los archivos
tail -n 200 logs/bd_processing.log  # Verificar BD procesados
tail -n 200 logs/us_reception.log  # Verificar US recibidos
```

## Preguntas Frecuentes

### ¿Qué pasa con peticiones en vuelo durante restart?

- Asociaciones DICOM activas se cierran gracefully
- Gateway reintenta envío automáticamente
- Workers background finalizan trabajos en vuelo (hasta 30s timeout)

### ¿Se pierden trabajos si se crashea el servicio?

- Sí, colas son en memoria (by design)
- Archivos DICOM ya están guardados en disco
- Trabajos fallidos se pueden reprocesar manualmente desde logs

### ¿Cómo reprocesar estudios BD que fallaron?

```bash
# Ver fallos en log
grep "ERROR" /home/ubuntu/DICOMReceiver/logs/bd_processing.log

# Reprocesar manualmente por Patient ID
cd /home/ubuntu/DICOMReceiver
python3 algorithms/bd_extracts/bd_extract_hologic.py <PATIENT_ID>
# o
python3 algorithms/bd_extracts/bd_extract_ge.py <PATIENT_ID>
```

### ¿Cómo reenviar US que fallaron forwarding?

```bash
# Ver fallos
cat /home/ubuntu/DICOMReceiver/logs/us_forwarding_failed.log

# Extraer archivo y Patient ID de log, luego usar script:
# (TBD: crear script de reenvío manual)
```

## Contacto y Soporte

Para problemas o preguntas:
1. Revisar logs: `sudo journalctl -u dicom-receiver.service -n 500`
2. Revisar logs específicos: `logs/bd_processing.log`, `logs/us_reception.log`
3. Verificar configuración: `cat config.py | grep -A 10 ASYNC_PROCESSING`
4. Rollback si es crítico (ver sección Rollback Plan)

## Changelog

### 2026-04-03 - v2.0 Async Processing
- ✅ Agregado sistema de colas asíncronas (queue_manager.py)
- ✅ Creados workers para US/BD/Pixel processing
- ✅ Refactorizado main.py con soporte async + backward compatibility
- ✅ Agregado JPEG Lossless transfer syntax
- ✅ Agregado Ultrasound Multi-frame SOP class
- ✅ Documentado TRANSFER_SYNTAX_README.md
- ✅ Modo default: DESHABILITADO (backward compatible)
- ⚠️  Deployment pending: Activar async en Fase 3 después de testing
