# Modo Async - Guía de Activación y Monitoreo

## Estado Actual

**✅ PREPARADO** - Todas las mejoras implementadas y listas para activación.

### Mejoras Implementadas

#### 1. Backpressure Detection ✅
El sistema ahora degrada automáticamente a modo sync si las colas se saturan:
- **Threshold de alerta**: 800 items/cola (warning)
- **Threshold de degradación**: 950 items/cola (switch temporal a sync)
- No descarta trabajos - procesa síncronamente cuando hay sobrecarga

#### 2. Métricas Mejoradas ✅
- **Stats logging** cada 30 segundos con:
  - Trabajos Submitted/Completed/Failed por tipo (US, BD, Pixel)
  - Tasa de éxito (%)
  - Queue depths actuales
- **Monitoreo continuo** de saturación con alertas por nivel

#### 3. Configuración Optimizada ✅
```python
ASYNC_PROCESSING = {
    'enabled': False,                  # ← Cambiar a True para activar
    'queue_monitor_interval': 30,      # Monitoreo cada 30s (antes: 60s)
    'stats_interval': 30,              # Stats cada 30s
    'alert_threshold': 800,            # Alerta cuando cola > 800
    'degradation_threshold': 950,      # Degrade a sync cuando > 950
    ...
}
```

#### 4. Scripts de Gestión ✅

**activate_async.sh** - Activación segura con pre-checks
- Verifica servicio activo y memoria disponible
- Backup automático de config
- Confirmación de usuario
- Rollback automático si falla el restart

**rollback_async.sh** - Rollback inmediato a sync
- Desactiva async y reinicia servicio
- Backup de config antes de modificar

**monitor_async.sh** - Monitoreo en tiempo real
- Memoria RSS del proceso
- CPU usage
- Memoria disponible del sistema
- Stats recientes de colas
- Alertas de backpressure

## Procedimiento de Activación

### Preparación

1. **Verificar estabilidad actual**:
```bash
# Servicio debe estar estable en sync mode
sudo systemctl status dicom-receiver.service

# Memoria disponible (mínimo 1GB recomendado)
free -h
```

2. **Tener terminal de monitoreo lista**:
```bash
cd /home/ubuntu/DICOMReceiver
./monitor_async.sh
```

### Activación

**Opción A: Usando script (recomendado)**
```bash
cd /home/ubuntu/DICOMReceiver
sudo ./activate_async.sh
```

El script hace:
- ✅ Pre-checks de seguridad
- ✅ Backup de config
- ✅ Confirmación de usuario
- ✅ Activación + restart
- ✅ Verificación post-restart

**Opción B: Manual**
```bash
# 1. Backup
cp config.py config.py.backup.$(date +%Y%m%d_%H%M%S)

# 2. Activar
sed -i "s/'enabled': False/'enabled': True/g" config.py

# 3. Restart
sudo systemctl restart dicom-receiver.service

# 4. Verificar
sudo journalctl -u dicom-receiver.service -f | grep -i async
```

### Monitoreo Post-Activación

**Monitor en tiempo real** (terminal dedicada):
```bash
./monitor_async.sh
```

**Logs de async en vivo**:
```bash
sudo journalctl -u dicom-receiver.service -f | grep -E "ASYNC|Cola|Queue|BACKPRESSURE"
```

**Ver estadísticas recientes**:
```bash
sudo journalctl -u dicom-receiver.service --since "5 minutes ago" --no-pager | grep "ASYNC STATS"
```

### Criterios de Éxito

✅ **Servicio estable**:
- Status: `active (running)`
- Sin OOM kills
- Memoria estable < 1GB

✅ **Colas funcionando**:
- Workers inicializados (logs: "US workers: 2, BD workers: 4...")
- Stats muestran completed > 0
- Success rate > 95%

✅ **Sin backpressure**:
- No mensajes "BACKPRESSURE DETECTED"
- Queue depths < 800

### Rollback de Emergencia

Si **cualquier problema** (OOM, colas saturadas, errores):

```bash
# Opción A: Script automático
sudo ./rollback_async.sh

# Opción B: Manual rápido
sed -i "s/'enabled': True/'enabled': False/g" /home/ubuntu/DICOMReceiver/config.py
sudo systemctl restart dicom-receiver.service
```

## Análisis: ¿Necesitas Instance Type Upgrade?

### Tu Configuración Actual
- **RAM**: 3.7GB total, ~1GB disponible típicamente
- **CPU**: 2 cores
- **Workload**: ~24 archivos/min en horario normal

### Análisis

#### RAM - Probablemente SUFICIENTE ✅
Con los fixes de OOM implementados:
- **Sync mode**: 120-150MB baseline, peaks ~400MB → ✅ Sobra espacio
- **Async mode** (estimado): 150-300MB baseline, peaks ~600-800MB → ✅ Cabe en 3.7GB
- **Buffer de seguridad**: 1GB+ disponible para picos temporales

**Conclusión RAM**: NO necesitas upgrade para operación normal. Solo considera upgrade si:
- Recibes > 100 archivos/min sostenido
- Archivos US > 50MB promedio
- Necesitas más workers (ej: us_workers: 6)

#### CPU - MARGINAL (puede beneficiar ligeramente) ⚠️
- **2 cores actuales**: Suficiente para 8 workers totales (US:2 + BD:4 + Pixel:2)
- **4 cores**: Permitiría duplicar workers (US:4, BD:8) sin contention
- **Impacto esperado**: ~15-25% mejora en throughput bajo alta carga

**Conclusión CPU**: Upgrade solo útil si experimentas:
- Cola BD frecuentemente > 500 items
- Subprocesos bd_extract_*.py lentos (>10s cada uno)
- Quieres reducir latencia de procesamiento en horarios pico

### Recomendación Final

**NO UPGRADER** el instance type **AHORA**. Razones:

1. ✅ **Fixes de OOM resuelven el problema principal** - Ya no hay riesgo de OOM
2. ✅ **Recursos actuales adecuados** para workload típico
3. ✅ **Métricas nuevas te dirán** si necesitas más tarde
4. 💰 **Ahorro de costos** - No gastes si no es necesario

**CONSIDERAR UPGRADE** solo si después de activar async ves:
- Memoria peak > 1.5GB frecuentemente
- Backpressure activándose (colas > 950)
- CPU usage sostenido > 80%

### Instance Types Recomendados (si fuera necesario)

**Si upgrade RAM**:
- `t3.medium` → `t3.large` (4GB → 8GB RAM, 2→2 cores)
- Costo: ~$30/mes adicional
- Beneficio: 2x RAM buffer

**Si upgrade CPU+RAM**:
- `t3.medium` → `t3.xlarge` (4GB → 16GB RAM, 2→4 cores)
- Costo: ~$60/mes adicional
- Beneficio: 2x cores para workers, 4x RAM buffer

## Timeline Sugerido

**Hoy**: 
- ✅ Mantener sync mode
- ✅ Monitorear estabilidad 2-4 horas

**Mañana** (horario de baja carga):
- 🔄 Activar async mode con `./activate_async.sh`
- 📊 Monitoreo intensivo primera hora
- 📈 Observar métricas y queue depths

**48 horas después**:
- 📊 Revisar logs acumulados
- 📈 Analizar success rates y latencias
- ⚖️ Decisión final: keep async vs instance upgrade

---

**Scripts Disponibles**:
- `./activate_async.sh` - Activación segura
- `./rollback_async.sh` - Rollback inmediato
- `./monitor_async.sh` - Monitoreo en tiempo real

**Documentación**:
- [OOM_FIX_README.md](OOM_FIX_README.md) - Análisis técnico del fix
- Este archivo - Guía operacional async mode
