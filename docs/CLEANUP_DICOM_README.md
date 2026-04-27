# Sistema de Limpieza Automática de Archivos DICOM

## Descripción
Sistema automatizado que elimina archivos DICOM más antiguos de 24 horas del directorio `dicom_storage/` para evitar saturación del servidor.

**IMPORTANTE**: Solo elimina los archivos DICOM. Los archivos XML extraídos y reportes generados se mantienen intactos.

## Archivos del Sistema

### Scripts
- **cleanup_dicom_files.sh**: Script principal que realiza la limpieza
- **install-cleanup-service.sh**: Script de instalación del servicio systemd

### Archivos de Servicio
- **dicom-cleanup.service**: Definición del servicio systemd
- **dicom-cleanup.timer**: Timer que ejecuta la limpieza cada hora

## Configuración Actual

- **Frecuencia**: Cada 1 hora
- **Edad de eliminación**: 24 horas
- **Directorio**: `/home/ubuntu/DICOMReceiver/dicom_storage`
- **Log**: `/home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log`

## Comandos Útiles

### Ver estado del timer
```bash
sudo systemctl status dicom-cleanup.timer
```

### Ver próximas ejecuciones
```bash
systemctl list-timers dicom-cleanup.timer
```

### Ejecutar limpieza manualmente (ahora)
```bash
sudo systemctl start dicom-cleanup.service
```

### Ver logs del servicio
```bash
# Logs de systemd
sudo journalctl -u dicom-cleanup.service -f

# Log del script
cat /home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log
tail -f /home/ubuntu/DICOMReceiver/logs/cleanup_dicom.log
```

### Detener el servicio automático
```bash
sudo systemctl stop dicom-cleanup.timer
sudo systemctl disable dicom-cleanup.timer
```

### Reiniciar el servicio
```bash
sudo systemctl restart dicom-cleanup.timer
```

## Modificar Configuración

### Cambiar frecuencia de ejecución
Editar `/etc/systemd/system/dicom-cleanup.timer`:
```ini
[Timer]
OnBootSec=10min        # Ejecutar 10 min después del arranque
OnUnitActiveSec=1h     # Ejecutar cada 1 hora (cambiar aquí)
Persistent=true
```

Opciones comunes:
- `OnUnitActiveSec=30min` - Cada 30 minutos
- `OnUnitActiveSec=2h` - Cada 2 horas
- `OnUnitActiveSec=6h` - Cada 6 horas
- `OnCalendar=daily` - Una vez al día

Después de modificar:
```bash
sudo systemctl daemon-reload
sudo systemctl restart dicom-cleanup.timer
```

### Cambiar edad de archivos a eliminar
Editar `/home/ubuntu/DICOMReceiver/cleanup_dicom_files.sh`:
```bash
HOURS_OLD=24  # Cambiar este valor (en horas)
```

Ejemplos:
- `HOURS_OLD=12` - Eliminar archivos más antiguos de 12 horas
- `HOURS_OLD=48` - Eliminar archivos más antiguos de 48 horas (2 días)

## Estadísticas Primera Ejecución

**Fecha**: 2026-01-30 15:38:39 UTC

- Archivos antes: 2,075
- Archivos eliminados: 1,606
- Archivos restantes: 469
- Espacio liberado: 2.5 GB (de 3.8GB a 1.3GB)

## Seguridad

✅ **NO se eliminan**:
- Archivos XML extraídos (en `xml_extraction/`)
- Reportes generados (en `reports/`)
- Datos en base de datos PostgreSQL
- Archivos recientes (menos de 24 horas)

❌ **SÍ se eliminan**:
- Archivos DICOM en `dicom_storage/` con más de 24 horas
- Directorios vacíos resultantes

## Troubleshooting

### El timer no se ejecuta
```bash
# Verificar que esté habilitado
sudo systemctl is-enabled dicom-cleanup.timer

# Ver logs de errores
sudo journalctl -u dicom-cleanup.timer -n 50
```

### Verificar espacio en disco
```bash
df -h
du -sh /home/ubuntu/DICOMReceiver/dicom_storage
```

### Desinstalar completamente
```bash
sudo systemctl stop dicom-cleanup.timer
sudo systemctl disable dicom-cleanup.timer
sudo rm /etc/systemd/system/dicom-cleanup.service
sudo rm /etc/systemd/system/dicom-cleanup.timer
sudo systemctl daemon-reload
```

## Reinstalación

Si necesitas reinstalar el servicio:
```bash
cd /home/ubuntu/DICOMReceiver
./install-cleanup-service.sh
```

## Manejo de Servicios

### Servicios Relacionados

Este sistema trabaja en conjunto con otros servicios. A continuación, los comandos útiles para gestionar todos los servicios:

#### Backend API (qii-tools)
```bash
# Ver estado del servicio backend
sudo systemctl status qii-tools-backend

# Iniciar el servicio
sudo systemctl start qii-tools-backend

# Detener el servicio
sudo systemctl stop qii-tools-backend

# Reiniciar el servicio
sudo systemctl restart qii-tools-backend

# Ver logs en tiempo real
sudo journalctl -u qii-tools-backend -f

# Ver últimos 100 logs
sudo journalctl -u qii-tools-backend -n 100
```

#### Frontend (qii-tools)
```bash
# Ver estado del servicio frontend
sudo systemctl status qii-tools-frontend

# Iniciar el servicio
sudo systemctl start qii-tools-frontend

# Detener el servicio
sudo systemctl stop qii-tools-frontend

# Reiniciar el servicio
sudo systemctl restart qii-tools-frontend

# Ver logs en tiempo real
sudo journalctl -u qii-tools-frontend -f
```

#### Receptor DICOM
```bash
# Ver estado del servicio receptor DICOM
sudo systemctl status dicom-receiver

# Iniciar el servicio
sudo systemctl start dicom-receiver

# Detener el servicio
sudo systemctl stop dicom-receiver

# Reiniciar el servicio
sudo systemctl restart dicom-receiver

# Ver logs
sudo journalctl -u dicom-receiver -f
```

### Gestión de Todos los Servicios

#### Ver estado de todos los servicios
```bash
# Ver todos los servicios relacionados
sudo systemctl status qii-tools-backend qii-tools-frontend dicom-receiver dicom-cleanup.timer

# Ver solo si están activos o no
systemctl is-active qii-tools-backend qii-tools-frontend dicom-receiver dicom-cleanup.timer
```

#### Reiniciar todos los servicios
```bash
# Reiniciar backend, frontend y receptor DICOM
sudo systemctl restart qii-tools-backend qii-tools-frontend dicom-receiver

# Verificar que estén corriendo
sudo systemctl is-active qii-tools-backend qii-tools-frontend dicom-receiver
```

#### Habilitar/Deshabilitar inicio automático
```bash
# Habilitar inicio automático al arranque del sistema
sudo systemctl enable qii-tools-backend
sudo systemctl enable qii-tools-frontend
sudo systemctl enable dicom-receiver
sudo systemctl enable dicom-cleanup.timer

# Deshabilitar inicio automático
sudo systemctl disable qii-tools-backend
sudo systemctl disable qii-tools-frontend
sudo systemctl disable dicom-receiver
sudo systemctl disable dicom-cleanup.timer
```

### Base de Datos PostgreSQL
```bash
# Ver estado de PostgreSQL
sudo systemctl status postgresql

# Reiniciar PostgreSQL
sudo systemctl restart postgresql

# Conectarse a la base de datos
sudo -u postgres psql -d qii_tools
```

### Nginx (Servidor Web)
```bash
# Ver estado de Nginx
sudo systemctl status nginx

# Reiniciar Nginx (después de cambios de configuración)
sudo systemctl restart nginx

# Recargar configuración sin detener el servicio
sudo systemctl reload nginx

# Verificar configuración antes de aplicar
sudo nginx -t
```

### Orden Recomendado para Reinicio Completo

Si necesitas reiniciar todo el sistema:

```bash
# 1. Detener servicios de aplicación
sudo systemctl stop qii-tools-frontend
sudo systemctl stop qii-tools-backend
sudo systemctl stop dicom-receiver

# 2. Reiniciar servicios de infraestructura
sudo systemctl restart postgresql
sudo systemctl restart nginx

# 3. Iniciar servicios de aplicación
sudo systemctl start dicom-receiver
sudo systemctl start qii-tools-backend
sudo systemctl start qii-tools-frontend

# 4. Verificar estado
sudo systemctl status qii-tools-backend qii-tools-frontend dicom-receiver
```

### Monitoreo de Recursos

```bash
# Ver uso de CPU y memoria de los servicios
systemctl status qii-tools-backend --no-pager
systemctl status qii-tools-frontend --no-pager

# Ver procesos Python (backend)
ps aux | grep python

# Ver procesos Node (frontend)
ps aux | grep node

# Ver todos los servicios activos del sistema
systemctl list-units --type=service --state=running
```

### Scripts de Inicio Manual (sin systemd)

Si los servicios systemd no están configurados, usar los scripts directamente:

```bash
# Desde el directorio del proyecto
cd /var/www/qii-tools

# Iniciar backend manualmente
./start-backend.sh

# Iniciar frontend manualmente
./start-frontend.sh
```

**Nota**: Los scripts manuales son útiles para desarrollo, pero en producción se recomienda usar systemd para gestión automática de servicios.
