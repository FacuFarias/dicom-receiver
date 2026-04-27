# Sistema de Tracking de Fuentes de Datos FRAX - Reportes BD

## 📋 Descripción

Este sistema permite trackear y analizar de dónde provienen los datos FRAX en los reportes BD:
- **XML embebido**: Datos extraídos directamente del tag DICOM privado
- **OCR (fallback)**: Datos extraídos mediante OCR de imágenes JPEG cuando no están en XML
- **Errores**: Casos donde no se pudo obtener FRAX por falta de datos o JPEG

## 🔧 Implementación

### Archivos Modificados

Los siguientes scripts ahora registran la fuente de datos FRAX:

1. **`algorithms/bd_extracts/bd_extract_hologic.py`**
2. **`algorithms/bd_extracts/bd_extract_hologic_desert.py`**
3. **`algorithms/bd_extracts/bd_extract_hologic_memorial.py`**

### Función de Logging

Cada script ahora incluye:

```python
def log_bd_processing_local(patient_id, step, status, details=""):
    """
    Registra cada paso del procesamiento BD en archivo de log centralizado.
    
    Args:
        patient_id: ID del paciente
        step: Paso del proceso (FRAX_SOURCE, etc.)
        status: Estado (INFO, WARNING, ERROR)
        details: Detalles adicionales
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = Path("/home/ubuntu/DICOMReceiver/logs/bd_processing.log")
    
    log_entry = f"[{timestamp}] [Patient: {patient_id}] [{step}] [{status}] {details}\n"
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(log_entry)
```

### Tipos de Logs Generados

| Evento | Log Entry | Status |
|--------|-----------|--------|
| FRAX extraído de XML | `Major FRAX extraído de XML: 8.3%` | INFO |
| FRAX extraído via OCR | `Major FRAX extraído via OCR (fallback): 12.5%` | INFO |
| OCR sin resultados | `Major FRAX no encontrado - OCR sin resultados` | WARNING |
| Sin JPEG disponible | `Major FRAX no encontrado - Sin JPEG para OCR` | WARNING |
| Hip FRAX de XML | `Hip FRAX extraído de XML: 2.2%` | INFO |

## 📊 Análisis de Estadísticas

### Script de Análisis: `analyze_frax_sources.py`

Ejecutar para obtener estadísticas completas:

```bash
cd /home/ubuntu/DICOMReceiver
python3 analyze_frax_sources.py
```

### Ejemplo de Salida

```
================================================================================
ANÁLISIS DE FUENTES DE DATOS FRAX - Reportes BD
================================================================================
Analizando: /home/ubuntu/DICOMReceiver/logs/bd_processing.log
Tamaño: 276.1 KB

📊 ESTADÍSTICAS GLOBALES
--------------------------------------------------------------------------------
Total de pacientes procesados: 150
Total de extracciones FRAX registradas: 450

🎯 MAJOR FRAX - Fuentes de Datos
--------------------------------------------------------------------------------
  Extraído de XML:              420 ( 93.3%)
  Extraído via OCR (fallback):   15 (  3.3%)
  OCR sin resultados:            10 (  2.2%)
  Sin JPEG para OCR:              5 (  1.1%)
  ────────────────────────────────────────────────────────────────────────────
  Total con FRAX exitoso:       435 ( 96.7%)
  Total sin FRAX:                15 (  3.3%)

🎯 HIP FRAX
--------------------------------------------------------------------------------
  Extraído de XML:              425

💡 INTERPRETACIÓN
--------------------------------------------------------------------------------
  ✓ El 3.3% de reportes requirieron OCR como fallback
    (pixel extraction fue necesario en lugar de XML)
  ⚠️  5 reportes no pudieron usar OCR (sin JPEG disponible)

📋 ÚLTIMOS 10 PACIENTES PROCESADOS
--------------------------------------------------------------------------------
  [2026-04-09 13:45:47] Patient     228047: Major FRAX from XML
  ...
```

## 🔍 Consultas Personalizadas

### Ver todos los casos que usaron OCR

```bash
grep "extraído via OCR (fallback)" /home/ubuntu/DICOMReceiver/logs/bd_processing.log
```

### Contar casos por tipo

```bash
# XML
grep "Major FRAX extraído de XML" logs/bd_processing.log | wc -l

# OCR
grep "extraído via OCR (fallback)" logs/bd_processing.log | wc -l

# Sin FRAX
grep -E "(OCR sin resultados|Sin JPEG)" logs/bd_processing.log | wc -l
```

### Ver pacientes específicos

```bash
grep "Patient: 228047" logs/bd_processing.log | grep FRAX_SOURCE
```

## 📈 Monitoreo Continuo

### Integración con Sistema Existente

El logging se activa automáticamente cuando:
1. Se recibe un estudio BD vía DICOM C-STORE
2. Se ejecuta `handle_store()` en `main.py`
3. Se procesa con los scripts de extracción BD

### Rotación de Logs

Para evitar archivos de log muy grandes, considerar implementar rotación:

```bash
# Rotar log mensualmente
mv logs/bd_processing.log logs/bd_processing_$(date +%Y%m).log
touch logs/bd_processing.log
```

## 🎯 Casos de Uso

### 1. Auditoría de Calidad de Datos

Verificar qué porcentaje de reportes requieren OCR vs XML:

```bash
python3 analyze_frax_sources.py | grep "Extraído via OCR"
```

### 2. Identificar Problemas

Encontrar pacientes sin JPEG disponible:

```bash
grep "Sin JPEG para OCR" logs/bd_processing.log
```

### 3. Validar Mejoras

Antes/después de optimizaciones en extracción XML:

```bash
# Ver tendencia semanal
grep "FRAX_SOURCE" logs/bd_processing.log | grep "$(date +%Y-%m-%d)"
```

## 🚀 Próximos Pasos

### Mejoras Sugeridas

1. **Dashboard en tiempo real**: Integrar con Grafana/Prometheus
2. **Alertas**: Notificar cuando el % de OCR supera umbral
3. **Almacenamiento en BD**: Agregar campo `frax_source` en `reports.bd`
4. **Métricas de rendimiento**: Tiempo de procesamiento XML vs OCR

### Agregar Campo en PostgreSQL (Opcional)

```sql
ALTER TABLE reports.bd ADD COLUMN major_frax_source VARCHAR(20);
ALTER TABLE reports.bd ADD COLUMN hip_frax_source VARCHAR(20);

-- Valores posibles: 'XML', 'OCR', NULL
```

## 📝 Notas Importantes

- Los logs se escriben en **tiempo real** durante el procesamiento
- El archivo de log es **`logs/bd_processing.log`**
- Formato: `[timestamp] [Patient: ID] [FRAX_SOURCE] [STATUS] details`
- Compatible con logging existente en `main.py`

## 🛠️ Troubleshooting

### El logging no aparece

1. Verificar que los scripts modificados se están usando:
   ```bash
   grep "log_bd_processing_local" algorithms/bd_extracts/bd_extract_hologic.py
   ```

2. Verificar permisos del archivo de log:
   ```bash
   ls -la logs/bd_processing.log
   ```

3. Verificar que se está procesando correctamente:
   ```bash
   tail -f logs/bd_processing.log
   ```

### Análisis muestra 0 resultados

- Los datos solo se registran **después** de implementar el logging
- Registros antiguos no tendrán esta información
- Procesar nuevos estudios BD para generar datos

---

**Fecha de Implementación**: 2026-04-09  
**Versión**: 1.0  
**Autor**: Sistema de Tracking FRAX
