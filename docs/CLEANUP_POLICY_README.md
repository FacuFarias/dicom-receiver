# Sistema de Limpieza Automática de Archivos DICOM

## Resumen

El sistema elimina automáticamente archivos DICOM antiguos según políticas de retención diferenciadas por tipo de modalidad.

## 📋 Políticas de Retención

| Tipo de Archivo | Retención | Ubicación |
|-----------------|-----------|-----------|
| **US (Ultrasound)** | 3 horas | `dicom_storage/US/` |
| **BD (Bone Density)** | 48 horas (2 días) | `dicom_storage/{PatientID}/` |
| **SR (Structured Reports)** | 48 horas (2 días) | `dicom_storage/{PatientID}/` |
| **Otros (CT, MR, etc)** | 30 días | `dicom_storage/{PatientID}/` |

## ⚙️ Configuración

### Script de Limpieza
Ubicación: [cleanup_dicom_files.sh](cleanup_dicom_files.sh)

Variables configurables:
```bash
US_RETENTION_MINUTES=180   # US: 3 horas
BD_RETENTION_MINUTES=2880  # BD: 48 horas
SR_RETENTION_MINUTES=2880  # SR: 48 horas
OTHER_RETENTION_DAYS=30    # Otros: 30 días
```

### Timer de Ejecución Automática
Ubicación: `/etc/systemd/system/dicom-cleanup.timer`

Configuración:
- **Inicio tras boot**: 10 minutos después del arranque
- **Frecuencia**: Cada 1 hora
- **Persistente**: Sí (ejecuta si el sistema estuvo apagado)

## 🔄 Operación Automática

### Ver Estado del Timer
```bash
# Estado del timer
systemctl status dicom-cleanup.timer

# Ver próxima ejecución programada
systemctl list-timers | grep dicom-cleanup

# Ver últimas ejecuciones
journalctl -u dicom-cleanup.service --since "1 day ago"
```

### Logs de Limpieza

Log de operaciones: `logs/cleanup_dicom.log`

Formato:
```
[2026-03-23 14:00:00] === Iniciando limpieza de archivos DICOM ===
[2026-03-23 14:00:00] Espacio usado antes: 15G
[2026-03-23 14:00:00] Archivos totales antes: 523
[2026-03-23 14:00:00] --- Limpieza de archivos US (mayores a 3 horas) ---
[2026-03-23 14:00:00] Archivos US eliminados: 12
[2026-03-23 14:00:00] --- Limpieza de archivos BD (mayores a 48 horas) ---
[2026-03-23 14:00:00] Archivos BD eliminados: 8
[2026-03-23 14:00:00] --- Limpieza de archivos SR (mayores a 48 horas) ---
[2026-03-23 14:00:00] Archivos SR eliminados: 3
[2026-03-23 14:00:00] --- Limpieza de otros archivos DICOM (mayores a 30 días) ---
[2026-03-23 14:00:00] Archivos DICOM (no-US) eliminados: 8
[2026-03-23 14:00:00] Espacio usado después: 14G
[2026-03-23 14:00:00] Archivos totales después: 503
[2026-03-23 14:00:00] === Resumen de limpieza ===
[2026-03-23 14:00:00]   US eliminados (3h): 12
[2026-03-23 14:00:00]   BD eliminados (48h): 8
[2026-03-23 14:00:00]   SR eliminados (48h): 3
[2026-03-23 14:00:00]   Otros eliminados (30d): 8
[2026-03-23 14:00:00]   Total eliminados: 31
[2026-03-23 14:00:00] === Limpieza completada ===
```

Ver log en tiempo real:
```bash
tail -f /home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log
```

## 🧪 Testing y Verificación

### Dry Run (Sin Eliminar)
```bash
# Ver qué archivos se eliminarían sin eliminar realmente
bash /home/ubuntu/DICOMReceiver/test_cleanup_dry_run.sh
```

Ejemplo de salida:
```
==========================================
TEST DE LIMPIEZA DICOM (DRY RUN)
==========================================

📋 Configuración:
  Retención US: 3 horas
  Retención BD: 48 horas (2 días)
  Retención SR: 48 horas (2 días)
  Retención otros: 30 días

🔍 Archivos US que se eliminarían (mayores a 3 horas):
  Total: 5 archivos
  
  Primeros 10 archivos:
    - US_20260321_130956_477_1.2.840.113619.jpg (3d, 1.2M)
    - US_20260321_145230_123_1.2.840.113619.jpg (3d, 850K)

🔍 Archivos BD que se eliminarían (mayores a 48 horas):
  Total: 3 archivos

🔍 Archivos SR que se eliminarían (mayores a 48 horas):
  Total: 2 archivos

🔍 Archivos DICOM no-US/no-BD/no-SR que se eliminarían (mayores a 30 días):
  Total: 1 archivo

==========================================
📊 RESUMEN
==========================================
  Archivos US a eliminar: 5
  Archivos BD a eliminar: 3
  Archivos SR a eliminar: 2
  Archivos otros a eliminar: 1
  Total a eliminar: 11
  Espacio a liberar: 15 MB
```

### Ejecución Manual
```bash
# Ejecutar limpieza manualmente (elimina archivos)
bash /home/ubuntu/DICOMReceiver/cleanup_dicom_files.sh
```

Salida:
```
✓ Limpieza de archivos DICOM completada
  US eliminados (48h): 5
  Otros eliminados (72h): 3
  Total eliminados: 8
  Espacio antes: 15G → después: 15G
  Log: /home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log
```

## 🔧 Gestión del Servicio

### Habilitar/Deshabilitar Timer
```bash
# Habilitar (activar al boot)
sudo systemctl enable dicom-cleanup.timer

# Deshabilitar (no ejecutar automáticamente)
sudo systemctl disable dicom-cleanup.timer

# Detener temporalmente
sudo systemctl stop dicom-cleanup.timer

# Iniciar
sudo systemctl start dicom-cleanup.timer
```

### Ejecutar Servicio Inmediatamente
```bash
# Ejecutar limpieza ahora (sin esperar al timer)
sudo systemctl start dicom-cleanup.service

# Ver resultado
journalctl -u dicom-cleanup.service -n 50
```

### Modificar Frecuencia del Timer

Editar `/etc/systemd/system/dicom-cleanup.timer`:
```ini
[Timer]
OnBootSec=10min
OnUnitActiveSec=2h    # Cambiar a 2 horas en vez de 1 hora
Persistent=true
```

Aplicar cambios:
```bash
sudo systemctl daemon-reload
sudo systemctl restart dicom-cleanup.timer
```

## 📊 Monitoreo

### Espacio en Disco
```bash
# Espacio usado en dicom_storage
du -sh /home/ubuntu/DICOMReceiver/dicom_storage

# Espacio por modalidad
du -sh /home/ubuntu/DICOMReceiver/dicom_storage/US
du -sh /home/ubuntu/DICOMReceiver/dicom_storage/*/

# Archivos más antiguos
find /home/ubuntu/DICOMReceiver/dicom_storage -type f -mtime +2 | head -10
```

### Estadísticas de Archivos
```bash
# Total de archivos DICOM
find /home/ubuntu/DICOMReceiver/dicom_storage -type f | wc -l

# Archivos US
find /home/ubuntu/DICOMReceiver/dicom_storage/US -type f | wc -l

# Archivos por edad
echo "Archivos < 24h: $(find /home/ubuntu/DICOMReceiver/dicom_storage -type f -mtime -1 | wc -l)"
echo "Archivos 24-48h: $(find /home/ubuntu/DICOMReceiver/dicom_storage -type f -mtime -2 -mtime +1 | wc -l)"
echo "Archivos 48-72h: $(find /home/ubuntu/DICOMReceiver/dicom_storage -type f -mtime -3 -mtime +2 | wc -l)"
echo "Archivos > 72h: $(find /home/ubuntu/DICOMReceiver/dicom_storage -type f -mtime +3 | wc -l)"
```

## ⚠️ Consideraciones Importantes

### ¿Qué SE elimina?
- ✅ Archivos DICOM brutos en `dicom_storage/`
- ✅ Enlaces/copias en `dicom_storage/US/`

### ¿Qué NO se elimina?
- ❌ XML extraídos en `xml_extraction/` (permanentes)
- ❌ Imágenes JPEG en `pixel_extraction/` (permanentes)
- ❌ Reportes en base de datos (permanentes)
- ❌ Logs en `logs/` (permanentes)

### Recuperación

**No hay recuperación automática**. Los archivos eliminados no se pueden recuperar.

**Estrategia de respaldo**:
1. Los estudios importantes deberían estar en el servidor destino (para US con forwarding)
2. Los datos procesados (XML, reportes BD) se mantienen permanentemente
3. Para retención extendida, configurar backup externo antes de la eliminación

## 🔄 Cambiar Políticas de Retención

### Ejemplo: Cambiar US a 24 horas

Editar [cleanup_dicom_files.sh](cleanup_dicom_files.sh):
```bash
HOURS_OLD_US=24     # Cambiar de 48 a 24
```

### Ejemplo: Cambiar BD a 7 días

```bash
HOURS_OLD_OTHER=168  # 7 días * 24 horas = 168 horas
```

**Aplicar cambios**: No requiere reinicio, el timer ejecutará el script actualizado automáticamente.

## 📅 Implementación

**Fecha**: Marzo 23, 2026

**Archivos**:
- [cleanup_dicom_files.sh](cleanup_dicom_files.sh) - Script de limpieza actualizado
- [dicom-cleanup.service](dicom-cleanup.service) - Servicio systemd actualizado
- [dicom-cleanup.timer](dicom-cleanup.timer) - Timer de ejecución
- [test_cleanup_dry_run.sh](test_cleanup_dry_run.sh) - Test sin eliminación

**Estado**: ✅ Activo y ejecutándose cada hora
