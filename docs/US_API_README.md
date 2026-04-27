# US Reports API

API REST para recibir y almacenar reportes de estudios de Ultrasonido (US) procesados por sistemas externos.

## 📋 Descripción

Esta API permite que sistemas externos de procesamiento de imágenes US envíen reportes estructurados que se almacenan en la base de datos PostgreSQL (`reports.us`).

## 🚀 Instalación

### Opción 1: Como Servicio Systemd (Producción)

```bash
# Instalar dependencias y configurar el servicio
sudo bash install-us-api-service.sh

# El servicio se iniciará automáticamente y permanecerá activo
```

### Opción 2: Manualmente (Desarrollo/Testing)

```bash
# Instalar dependencias
pip3 install -r requirements.txt

# Iniciar la API
bash start-us-api.sh
```

## 🔧 Configuración

### Base de Datos
La API se conecta a PostgreSQL con las siguientes credenciales (configurables en `us_api.py`):

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'facundo',
    'password': 'qii123',
    'database': 'qii'
}
```

### Tabla de Base de Datos

Tabla: `reports.us`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| guid | character varying(45) | Primary Key, auto-generado (gen_uuid) |
| mrn | character varying(45) | Medical Record Number, NOT NULL |
| acc | character varying | Accession Number, opcional |
| report | text | Contenido del reporte, NOT NULL |
| createdon | timestamp | Fecha de creación, default NOW() |
| updatedon | timestamp | Fecha de última actualización, default NOW() |

## 📡 Endpoints de la API

### Base URL
```
http://localhost:5667/api
```

### 1. Health Check
Verifica el estado de la API y la conexión a la base de datos.

**Endpoint:** `GET /api/health`

**Respuesta Exitosa:**
```json
{
    "status": "healthy",
    "service": "US Reports API",
    "database": "connected",
    "timestamp": "2026-02-24T10:30:00.123456"
}
```

**Ejemplo:**
```bash
curl http://localhost:5667/api/health
```

---

### 2. Crear/Actualizar Reporte US
Crea un nuevo reporte o actualiza uno existente si ya existe con el mismo MRN y ACC.

**Endpoint:** `POST /api/us/report`

**Content-Type:** `application/json`

**Body (JSON):**
```json
{
    "mrn": "12345678",
    "acc": "ACC001234",
    "report": "REPORTE DE ULTRASONIDO\n\nPaciente: John Doe\nEstudio: Ultrasonido Abdominal\n\nHALLAZGOS:\n- Hígado de tamaño normal\n- Vesícula biliar sin litiasis\n- Riñones sin alteraciones\n\nCONCLUSIÓN:\nEstudio dentro de límites normales."
}
```

**Campos:**
- `mrn` *(requerido)*: Medical Record Number del paciente
- `acc` *(opcional)*: Accession Number del estudio
- `report` *(requerido)*: Contenido del reporte en texto plano

**Respuesta Exitosa (Creación):**
```json
{
    "success": true,
    "action": "created",
    "guid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "mrn": "12345678",
    "acc": "ACC001234",
    "createdon": "2026-02-24T10:30:00.123456",
    "updatedon": "2026-02-24T10:30:00.123456",
    "message": "US report created successfully"
}
```

**Respuesta Exitosa (Actualización):**
```json
{
    "success": true,
    "action": "updated",
    "guid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "mrn": "12345678",
    "acc": "ACC001234",
    "createdon": "2026-02-24T10:30:00.123456",
    "updatedon": "2026-02-24T11:45:00.654321",
    "message": "US report updated successfully"
}
```

**Errores Posibles:**
```json
// Campo requerido faltante
{
    "success": false,
    "error": "Field \"mrn\" is required and cannot be empty"
}

// Error de base de datos
{
    "success": false,
    "error": "Database error",
    "details": "..."
}
```

**Ejemplo:**
```bash
curl -X POST http://localhost:5667/api/us/report \
  -H "Content-Type: application/json" \
  -d '{
    "mrn": "12345678",
    "acc": "ACC001234",
    "report": "Reporte de ultrasonido completo aquí..."
  }'
```

---

### 3. Obtener Reportes por MRN
Obtiene todos los reportes de un paciente específico.

**Endpoint:** `GET /api/us/report/<mrn>`

**Parámetros:**
- `mrn`: Medical Record Number del paciente

**Respuesta Exitosa:**
```json
{
    "success": true,
    "mrn": "12345678",
    "count": 2,
    "reports": [
        {
            "guid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "mrn": "12345678",
            "acc": "ACC001234",
            "report": "Contenido del reporte...",
            "createdon": "2026-02-24T10:30:00.123456",
            "updatedon": "2026-02-24T10:30:00.123456"
        },
        {
            "guid": "b2c3d4e5-f6g7-8901-bcde-fg2345678901",
            "mrn": "12345678",
            "acc": "ACC001235",
            "report": "Otro reporte...",
            "createdon": "2026-02-23T09:15:00.123456",
            "updatedon": "2026-02-23T09:15:00.123456"
        }
    ]
}
```

**Ejemplo:**
```bash
curl http://localhost:5667/api/us/report/12345678
```

---

### 4. Obtener Reporte Específico
Obtiene un reporte específico por MRN y Accession Number.

**Endpoint:** `GET /api/us/report/<mrn>/<acc>`

**Parámetros:**
- `mrn`: Medical Record Number del paciente
- `acc`: Accession Number del estudio

**Respuesta Exitosa:**
```json
{
    "success": true,
    "report": {
        "guid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "mrn": "12345678",
        "acc": "ACC001234",
        "report": "Contenido del reporte...",
        "createdon": "2026-02-24T10:30:00.123456",
        "updatedon": "2026-02-24T10:30:00.123456"
    }
}
```

**Respuesta (No encontrado):**
```json
{
    "success": false,
    "error": "Report not found",
    "mrn": "12345678",
    "acc": "ACC999999"
}
```

**Ejemplo:**
```bash
curl http://localhost:5667/api/us/report/12345678/ACC001234
```

---

### 5. Estadísticas
Obtiene estadísticas sobre los reportes en el sistema.

**Endpoint:** `GET /api/us/stats`

**Respuesta Exitosa:**
```json
{
    "success": true,
    "stats": {
        "total_reports": 1523,
        "reports_today": 45,
        "reports_this_week": 287
    },
    "timestamp": "2026-02-24T10:30:00.123456"
}
```

**Ejemplo:**
```bash
curl http://localhost:5667/api/us/stats
```

## 🔌 Integración con Sistema de Procesamiento US

El sistema que procesa las imágenes US debe enviar los reportes a través del endpoint POST una vez completado el análisis.

### Flujo de Trabajo:

1. **DICOMReceiver** recibe imágenes US del equipo de ultrasonido
2. **DICOMReceiver** reenvía las imágenes al sistema de procesamiento (configurado en `config.py`)
3. **Sistema de procesamiento** analiza las imágenes y genera el reporte
4. **Sistema de procesamiento** envía el reporte a esta API usando POST `/api/us/report`
5. **API** almacena el reporte en PostgreSQL (`reports.us`)

### Ejemplo de Integración (Python):

```python
import requests
import json

def send_us_report(mrn, accession, report_text):
    """
    Envía un reporte US a la API.
    
    Args:
        mrn: Medical Record Number
        accession: Accession Number
        report_text: Contenido del reporte
    
    Returns:
        dict: Respuesta de la API
    """
    url = "http://localhost:5667/api/us/report"
    
    payload = {
        "mrn": mrn,
        "acc": accession,
        "report": report_text
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error enviando reporte: {e}")
        return None

# Ejemplo de uso
if __name__ == "__main__":
    report = """
    REPORTE DE ULTRASONIDO ABDOMINAL
    
    Paciente: Juan Pérez
    MRN: 12345678
    Accession: ACC001234
    Fecha: 2026-02-24
    
    HALLAZGOS:
    - Hígado de tamaño normal, contornos regulares
    - Vesícula biliar sin litiasis
    - Riñones de morfología normal
    - Bazo sin alteraciones
    
    CONCLUSIÓN:
    Estudio dentro de límites normales.
    """
    
    result = send_us_report("12345678", "ACC001234", report)
    
    if result and result.get('success'):
        print(f"✓ Reporte guardado exitosamente")
        print(f"  GUID: {result['guid']}")
        print(f"  Acción: {result['action']}")
    else:
        print(f"✗ Error guardando reporte")
```

## 🔍 Gestión del Servicio

### Ver Estado
```bash
sudo systemctl status us-api
```

### Iniciar Servicio
```bash
sudo systemctl start us-api
```

### Detener Servicio
```bash
sudo systemctl stop us-api
```

### Reiniciar Servicio
```bash
sudo systemctl restart us-api
```

### Ver Logs en Tiempo Real
```bash
sudo journalctl -u us-api -f
```

### Ver Logs Históricos
```bash
# Últimas 100 líneas
sudo journalctl -u us-api -n 100

# Logs de hoy
sudo journalctl -u us-api --since today

# Logs de las últimas 2 horas
sudo journalctl -u us-api --since "2 hours ago"
```

## 🧪 Testing

### Test Manual con curl

```bash
# 1. Health check
curl http://localhost:5667/api/health

# 2. Crear reporte
curl -X POST http://localhost:5667/api/us/report \
  -H "Content-Type: application/json" \
  -d '{
    "mrn": "TEST12345",
    "acc": "TESTACC001",
    "report": "Este es un reporte de prueba"
  }'

# 3. Obtener reportes por MRN
curl http://localhost:5667/api/us/report/TEST12345

# 4. Obtener reporte específico
curl http://localhost:5667/api/us/report/TEST12345/TESTACC001

# 5. Ver estadísticas
curl http://localhost:5667/api/us/stats
```

### Test con Python

```python
import requests

# Health check
response = requests.get('http://localhost:5667/api/health')
print(response.json())

# Crear reporte
data = {
    "mrn": "TEST12345",
    "acc": "TESTACC001",
    "report": "Este es un reporte de prueba"
}
response = requests.post('http://localhost:5667/api/us/report', json=data)
print(response.json())

# Obtener reportes
response = requests.get('http://localhost:5667/api/us/report/TEST12345')
print(response.json())
```

## 🔒 Seguridad

### Consideraciones:
- La API actualmente **no tiene autenticación** - está diseñada para uso en red interna
- Si necesitas exponerla públicamente, considera agregar:
  - API Keys
  - JWT Authentication
  - Rate limiting
  - HTTPS/TLS

### Firewall:
```bash
# Permitir solo conexiones internas
sudo ufw allow from 192.168.1.0/24 to any port 5667

# O permitir solo desde IP específica
sudo ufw allow from 192.168.1.100 to any port 5667
```

## 📊 Monitoreo

### Ver actividad en tiempo real:
```bash
# Logs de la API
sudo journalctl -u us-api -f

# Conexiones al puerto
sudo netstat -tulpn | grep 5667
```

## ❓ Troubleshooting

### La API no inicia
```bash
# Ver logs detallados
sudo journalctl -u us-api -n 50 --no-pager

# Verificar que el puerto no esté en uso
sudo lsof -i :5667

# Verificar permisos del archivo
ls -l /home/ubuntu/DICOMReceiver/us_api.py
```

### Error de conexión a base de datos
```bash
# Verificar que PostgreSQL esté corriendo
sudo systemctl status postgresql

# Verificar credenciales en us_api.py
grep DB_CONFIG /home/ubuntu/DICOMReceiver/us_api.py

# Test de conexión manual
psql -h localhost -U facundo -d qii -c "SELECT 1"
```

### Error 500 al crear reporte
```bash
# Verificar que la tabla existe
psql -h localhost -U facundo -d qii -c "\dt reports.*"

# Verificar estructura de la tabla
psql -h localhost -U facundo -d qii -c "\d reports.us"
```

## 📝 Logs

Los logs se almacenan en el journal del sistema. Para acceder:

```bash
# Ver logs en tiempo real
sudo journalctl -u us-api -f

# Buscar errores
sudo journalctl -u us-api | grep ERROR

# Exportar logs a archivo
sudo journalctl -u us-api --since today > us-api-logs.txt
```

## 🔄 Actualización

Para actualizar la API:

```bash
# 1. Detener el servicio
sudo systemctl stop us-api

# 2. Hacer cambios en us_api.py

# 3. Reiniciar el servicio
sudo systemctl start us-api

# 4. Verificar que funciona
curl http://localhost:5667/api/health
```

## 📞 Soporte

Para problemas o dudas:
- Revisar logs: `sudo journalctl -u us-api -f`
- Verificar estado: `sudo systemctl status us-api`
- Revisar este README

---

**Versión:** 1.0.0  
**Última actualización:** 2026-02-24
