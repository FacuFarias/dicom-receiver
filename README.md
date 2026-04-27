# DICOM Receiver System

Sistema de recepción y procesamiento de archivos DICOM para densitometría ósea (BD) y ultrasonido (US).

## Cambios Desde La Ultima Subida (2026-04-27)

### Nucleo de procesamiento
- `main.py`: ampliacion del receptor DICOM con soporte adicional de SOP classes y transfer syntaxes, integracion de cola asincorna/workers, logging dedicado para recepcion US y nuevas rutas de procesamiento en background.
- `config.py`: activacion de controles de clientes permitidos, nueva configuracion de forwarding US, parametros de modo asincrono y tuning de performance.
- `queue_manager.py` y `workers/`: incorporacion de gestion de colas y workers dedicados para US, BD y extraccion de pixeles.

### Extraccion BD
- `algorithms/bd_extracts/bd_extract_ge.py`: migracion de flujo GE Lunar a extraccion estructurada (SR/XML) con parsing clinico y normalizacion de datos.
- `algorithms/bd_extracts/bd_extract_hologic.py`: mejoras en deteccion de estudios, cache de rango lumbar, logging local y robustez de parseo.
- Nuevos extractores especializados: `algorithms/bd_extracts/bd_extract_hologic_desert.py` y `algorithms/bd_extracts/bd_extract_hologic_memorial.py`.

### Operacion y mantenimiento
- `cleanup_dicom_files.sh` y `dicom-cleanup.service`: nueva politica de retencion por modalidad (US/BD/SR/otros), control por limite de almacenamiento y reporte de limpieza detallado.
- Scripts operativos nuevos para modo asincrono, API US y monitoreo: `activate_async.sh`, `monitor_async.sh`, `rollback_async.sh`, `start-us-api.sh`, `install-us-api-service.sh`, `test_cleanup_policy.sh`.
- Scripts de soporte/analitica: `analyze_frax_sources.py`, `query_ocr_usage.py`, `frax_stats.sh`, `regenerate_report.py`, `cleanup_dicom_storage.sh`.

### Documentacion
- Se agrega y consolida documentacion en `docs/` (despliegue, modo asincrono, limpieza DICOM, forwarding US, API US, algoritmos BD, fixes GE Lunar, etc.).

### Limpieza de repositorio
- Se eliminaron scripts legacy y artefactos historicos que ya no forman parte del flujo actual.
- Se removieron reportes de ejemplo antiguos versionados para mantener el repositorio enfocado en codigo y documentacion.
- Los datos generados en runtime (`xml_extraction/`, `reports/`, `logs/`) quedan fuera de versionado.

## 🚀 Inicio Rápido

```bash
# Iniciar servidor DICOM
./start.sh

# Iniciar API de ultrasonido
./start-us-api.sh
```

## 📂 Estructura del Proyecto

```
DICOMReceiver/
├── main.py              # Servidor DICOM principal
├── config.py            # Configuración del sistema
├── queue_manager.py     # Gestor de colas asíncronas
├── us_api.py           # API REST para ultrasonido
├── regenerate_report.py # Regeneración de reportes
├── workers/            # Workers de procesamiento
├── algorithms/         # Algoritmos de extracción (BD/US)
├── docs/              # 📚 Documentación completa
├── dicom_storage/     # Almacenamiento de archivos DICOM
├── logs/              # Logs del sistema
└── reports/           # Reportes generados
```

## 📚 Documentación

Toda la documentación está en la carpeta [`docs/`](docs/):

### General
- [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) - Guía de despliegue
- [RESUMEN_EJECUTIVO_SISTEMA_BD.md](docs/RESUMEN_EJECUTIVO_SISTEMA_BD.md) - Resumen ejecutivo

### Sistema de Densitometría Ósea (BD)
- [DOCUMENTACION_SISTEMA_BD.md](docs/DOCUMENTACION_SISTEMA_BD.md) - Documentación del sistema BD
- [DOCUMENTACION_ALGORITMOS_BD.md](docs/DOCUMENTACION_ALGORITMOS_BD.md) - Algoritmos de extracción
- [LOGICA_CONSTRUCCION_REPORTES_BD.md](docs/LOGICA_CONSTRUCCION_REPORTES_BD.md) - Lógica de reportes
- [GE_LUNAR_IMPLEMENTATION.md](docs/GE_LUNAR_IMPLEMENTATION.md) - Implementación GE Lunar
- [GE_LUNAR_SR_FIX.md](docs/GE_LUNAR_SR_FIX.md) - Fix para GE Lunar SR

### Sistema de Ultrasonido (US)
- [US_API_README.md](docs/US_API_README.md) - API de ultrasonido
- [US_API_QUICKSTART.md](docs/US_API_QUICKSTART.md) - Guía rápida
- [US_API_CREATE_REPORT_DOC.md](docs/US_API_CREATE_REPORT_DOC.md) - Creación de reportes
- [US_API_DRAFTS_FRONTEND.md](docs/US_API_DRAFTS_FRONTEND.md) - Borradores en frontend
- [US_FORWARDING_README.md](docs/US_FORWARDING_README.md) - Reenvío de ultrasonido
- [US_RECEPTION_README.md](docs/US_RECEPTION_README.md) - Recepción de ultrasonido

### Operación y Mantenimiento
- [ASYNC_MODE_GUIDE.md](docs/ASYNC_MODE_GUIDE.md) - Modo asíncrono
- [CLEANUP_DICOM_README.md](docs/CLEANUP_DICOM_README.md) - Limpieza DICOM
- [CLEANUP_POLICY_README.md](docs/CLEANUP_POLICY_README.md) - Políticas de limpieza
- [OOM_FIX_README.md](docs/OOM_FIX_README.md) - Fix de memoria
- [TRANSFER_SYNTAX_README.md](docs/TRANSFER_SYNTAX_README.md) - Sintaxis de transferencia

## 🔧 Servicios Systemd

```bash
# Instalar servicios
sudo ./install-service.sh         # Servidor DICOM
sudo ./install-us-api-service.sh  # API de ultrasonido
sudo ./install-cleanup-service.sh # Limpieza automática

# Gestionar servicios
sudo systemctl start dicom-receiver
sudo systemctl status dicom-receiver
sudo systemctl stop dicom-receiver
```

## 📦 Dependencias

Ver [requirements.txt](requirements.txt)

## 📝 Logs

Los logs se almacenan en `logs/`:
- `dicom_receiver.log` - Log del servidor DICOM
- `us_api.log` - Log de la API de ultrasonido
- `worker_*.log` - Logs de workers

## 🔄 Modo Asíncrono

```bash
./activate_async.sh   # Activar modo asíncrono
./monitor_async.sh    # Monitorear colas
./rollback_async.sh   # Revertir a modo síncrono
```

## ⚙️ Configuración

Editar `config.py` para ajustar:
- Parámetros del servidor DICOM
- Rutas de almacenamiento
- Configuración de workers
- Endpoints de APIs externas
