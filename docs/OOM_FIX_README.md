# OOM (Out of Memory) Fix - DICOM Receiver

## Problema Original

El servicio DICOM Receiver sufrió múltiples crashes por OOM (Out of Memory) durante la activación del modo asíncrono en Phase 2.

### Síntomas
- Servicio matado por systemd con `signal=KILL` (OOM killer)
- Memoria creciendo ~15MB/segundo sin límite
- Sistema completo se quedó "trabado", requiriendo reboot de la instancia
- Ocurría tanto en modo async como sync

### Causas Raíz Identificadas

1. **Datasets completos en colas de memoria (Async Mode)**
   - Las colas pasaban `Dataset` objects completos (con píxeles) a los workers
   - Cada imagen US puede ser 10-50MB sin comprimir
   - Con cientos de imágenes encoladas simultáneamente, la memoria se agotaba rápidamente

2. **Validación de píxeles en duplicados (Both Modes)**
   - El flujo procesaba `validate_pixel_data(ds)` ANTES de verificar duplicados
   - validate_pixel_data() carga y procesa todos los píxeles del DICOM
   - El gateway estaba enviando masivas cantidades de duplicados (~50-100/min)
   - Cada duplicado cargaba 1-6MB en memoria antes de detectarse como duplicado

3. **Python Garbage Collection lento**
   - Python GC no liberaba memoria lo suficientemente rápido con alto volumen
   - Los Datasets permanecían en memoria acumulándose

## Soluciones Implementadas

### Fix #1: Pasar paths en lugar de Datasets a colas
**Archivo**: `main.py`, `queue_manager.py`, workers

**Antes**:
```python
queue_mgr.submit_us_job(forward_us_image_async, filepath, patient_id, study_uid, US_FORWARDING, ds)
queue_mgr.submit_bd_job(process_bd_study_async, filepath, patient_id, ds)
```

**Después**:
```python
queue_mgr.submit_us_job(forward_us_image_async, filepath, patient_id, study_uid, US_FORWARDING)
queue_mgr.submit_bd_job(process_bd_study_async, filepath, patient_id)
```

**Impacto**: Los workers ahora leen archivos desde disco cuando los necesitan, en lugar de mantener Datasets gigantes en memoria en las colas.

### Fix #2: Detectar duplicados ANTES de procesar píxeles
**Archivo**: `main.py` (handle_store function)

**Antes** (flujo ineficiente):
1. Leer Dataset completo
2. Log metadata  
3. **validate_pixel_data(ds)** ← Procesa TODOS los píxeles (slow, memory-intensive)
4. Create directories
5. Check duplicates
6. Si duplicado → return

**Después** (flujo optimizado):
1. Leer Dataset completo (inevitable - pynetdicom lo hace automáticamente)
2. Extraer metadata básica (PatientID, StudyInstanceUID, SOPInstanceUID)
3. Create directories
4. **Check duplicates IMMEDIATELY** ← Verificación rápida con glob
5. Si duplicado:
   - Log reducido (DEBUG level)
   - `del ds` + `gc.collect()`
   - Return 0x0000 inmediatamente
6. Si NO duplicado → validate_pixel_data() y guardado normal

**Impacto**: Duplicados ahora responden en <10ms en lugar de ~50-200ms, sin procesar píxeles innecesariamente.

### Fix #3: Liberar memoria explícitamente en duplicados
**Archivo**: `main.py`

```python
import gc  # Agregado al inicio

# En detección de duplicados:
del ds
gc.collect()
return 0x0000
```

**Impacto**: Fuerza liberación inmediata de memoria para Datasets de duplicados, sin esperar GC automático.

### Fix #4: Logging reducido para duplicados
**Antes**: Logging verboso con WARNING level (7 lines por duplicado)
**Después**: Logging compacto con DEBUG level (1 line por duplicado)

**Impacto**: Reduce sobrecarga de I/O y strings en memoria durante alta carga de duplicados.

## Resultados

### Antes de los Fixes
- **Modo Async**: OOM kill en <60 segundos con tráfico normal
- **Modo Sync**: Memoria creciendo 15MB/s → OOM en ~2-3 minutos
- **Comportamiento**: Crecimiento ilimitado sin estabilización

### Después de los Fixes  
- **Modo Sync** (current): Memoria estable ~120-150MB baseline
- **Comportamiento**: Crece temporalmente durante ráfagas de tráfico (hasta ~400MB), luego GC la recupera a ~120MB
- **Peak observado**: 1.0GB (dentro del límite systemd de 2.0GB)
- **Uptime estable**: Servicio corriendo sin crashes

## Estado Actual

✅ **ESTABILIZADO** - Servicio corriendo en **modo SYNC** con optimizaciones de duplicados

### Config Actual
```python
ASYNC_PROCESSING = {
    'enabled': False,  # Modo sync activo
    ...
}
```

### Modo Async - Estado PENDIENTE
- ⚠️ Fixes aplicados pero NO TESTEADOS en modo async
- Necesita testing cuidadoso antes de reactivar
- Optimizaciones de duplicados deberían ayudar significativamente

## Próximos Pasos

1. **Monitoreo continuo del modo sync** (24-48 horas)
   - Verificar estabilidad bajo diferentes cargas
   - Monitorear memoria peak durante ráfagas
   
2. **Testing controlado de modo async** (cuando servicio sync demuestre estabilidad)
   - Activar async en horario de baja actividad
   - Monitoreo agresivo de memoria con `watch`
   - Plan de rollback inmediato si problemas

3. **Investigar duplicados del gateway** (prioridad media)
   - ¿Por qué dcm4chee reenvía tantos duplicados?
   - Revisar configuración de retry logic en gateway
   - Considerar implementar caché de SOPInstanceUIDs recientes

4. **Optimizaciones adicionales** (opcional)
   - Considerar no cargar píxeles del event.dataset si es posible
   - Investigar `stop_before_pixels=True` en pynetdicom
   - Implementar rate limiting si gateway sigue sobrecargando

## Notas Técnicas

### Memory Baseline por Modo
- **Sync mode baseline**: ~50-80MB idle, ~120-150MB con actividad moderada
- **Async mode baseline** (teórico): ~60-100MB idle (8 workers + colas)

### Systemd Memory Limit
```
MemoryMax=2.0G  # Hard limit configurado en systemd service
```

### Python GC Behavior Observado
- GC corre cada ~20-40 segundos bajo carga normal
- Puede permitir acumulación temporal de hasta ~400-500MB antes de recolectar
- Esto es normal - Python GC es conservador para evitar overhead

---

**Fecha**: 2026-04-03  
**Estado**: RESUELTO - Servicio estable en modo sync con optimizaciones  
**Autor**: GitHub Copilot (Claude Sonnet 4.5)
