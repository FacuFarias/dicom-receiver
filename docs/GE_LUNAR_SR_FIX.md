# Fix: Procesamiento Automático de SR de GE Lunar

## Fecha: 2026-04-02

## Problema Identificado

Los estudios de **GE Lunar Prodigy** de Memorial estaban **fallando al procesar** con error "0 archivos procesados".

### Causa Raíz

Los equipos GE Lunar envían archivos en **dos fases separadas**:

1. **Fase 1**: Archivos **BD** (imágenes - Modality='BD') llegan primero
2. **Fase 2**: Archivos **SR** (datos estructurados - Modality='SR') llegan después (~24 horas después)

El código anterior:
- ❌ Intentaba procesar cuando llegaban los **BD** (sin SR todavía → fallaba)
- ❌ No detectaba los **SR** cuando llegaban → nunca se procesaban

## Solución Implementada

### Cambios en `/home/ubuntu/DICOMReceiver/main.py`

#### 1. Cuando llega **Modality='BD'** de GE Lunar (línea ~770):
```python
# ANTES: Ejecutaba bd_extract_ge.py inmediatamente (fallaba)
# AHORA: Solo guarda el archivo y espera a que lleguen los SR

if 'GE' in manufacturer:
    log_bd_processing(patient_id, "DETECCION", "INFO", 
                    "Archivo BD recibido - esperando archivos SR para procesar")
    extraction_script = None  # NO procesar todavía
```

#### 2. Cuando llega **Modality='SR'** de GE Lunar (NUEVO - línea ~640):
```python
# NUEVO: Detecta SR de GE y ejecuta procesamiento automáticamente
elif modality.upper() == 'SR':
    if 'GE' in manufacturer:
        logger.info("📊 SR de GE Lunar detectado - procesando BD")
        
        # Ejecutar bd_extract_ge.py
        result = subprocess.run(['python3', extraction_script, str(patient_id)])
        
        if result.returncode == 0:
            log_bd_processing(patient_id, "BD_INSERT", "SUCCESS", 
                            "Reporte BD generado e insertado correctamente (GE LUNAR SR)")
```

## Flujo Corregido

```
┌─────────────────────────────────────────────────────────────────┐
│ Día 1: Llegan archivos BD (imágenes)                           │
├─────────────────────────────────────────────────────────────────┤
│ 1. Equipo GE Lunar envía 10-20 archivos con Modality='BD'      │
│ 2. main.py detecta: "GE HEALTHCARE" en Manufacturer            │
│ 3. main.py guarda archivos en dicom_storage/                   │
│ 4. Log: "Archivo BD recibido - esperando archivos SR"          │
│ 5. NO ejecuta bd_extract_ge.py (espera SR)                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Día 2: Llegan archivos SR (datos estructurados)                │
├─────────────────────────────────────────────────────────────────┤
│ 1. Equipo envía 5-15 archivos con Modality='SR'                │
│ 2. main.py detecta: Modality='SR' + "GE HEALTHCARE"            │
│ 3. main.py guarda archivos SR en dicom_storage/                │
│ 4. ✅ EJECUTA bd_extract_ge.py automáticamente                  │
│ 5. bd_extract_ge.py lee TODOS los archivos (BD + SR)           │
│ 6. Extrae datos de SR: BMD, T-scores, Z-scores, FRAX           │
│ 7. Genera reporte y guarda en PostgreSQL                        │
│ 8. Log: "BD_INSERT SUCCESS - Reporte generado"                 │
└─────────────────────────────────────────────────────────────────┘
```

## Verificación del Fix

### 1. Servicio Reiniciado
```bash
sudo systemctl restart dicom-receiver
sudo systemctl status dicom-receiver
# Estado: ✅ active (running)
```

### 2. Prueba Manual con Paciente Existente
```bash
cd /home/ubuntu/DICOMReceiver
python3 algorithms/bd_extracts/bd_extract_ge.py MMD1878574000
```

**Resultado:**
```
✅ 10 archivos SR procesados
✅ Lumbar BMD: 1.134, Left Hip: 0.688, Right Hip: 0.738
✅ Guardado en PostgreSQL (ACC: 6638932)
```

### 3. Verificar Logs en Tiempo Real
```bash
tail -f logs/bd_processing.log | grep -E "GE|SR|BD_INSERT"
```

Cuando llegue el próximo estudio GE, deberías ver:
```
[DETECCION] [INFO] Archivo BD recibido - esperando archivos SR
[RECEPCION] [SUCCESS] SR recibido - Fabricante: GE HEALTHCARE
[BD_INSERT] [SUCCESS] Reporte BD generado e insertado correctamente (GE LUNAR SR)
```

## Estadísticas Pre-Fix

- **309 intentos** de procesar estudios GE Lunar
- **0 exitosos** (todos fallaron con "0 archivos procesados")
- **256 pacientes GE** afectados

## Estadísticas Esperadas Post-Fix

- ✅ Archivos BD: Se guardan sin error (no intentan procesar)
- ✅ Archivos SR: Disparan procesamiento automático
- ✅ Tasa de éxito: 100% (cuando SR están presentes)

## Archivos Modificados

1. `/home/ubuntu/DICOMReceiver/main.py`
   - Línea ~640: Agregado handler para Modality='SR'
   - Línea ~770: Modificado GE Lunar para NO procesar en BD

## Pendiente: Reprocesamiento Masivo

Para reprocesar los 256 pacientes GE existentes que fallaron:

```bash
cd /home/ubuntu/DICOMReceiver

# Buscar pacientes GE con SR
for patient_dir in dicom_storage/MMD*/; do
    patient_id=$(basename "$patient_dir")
    
    # Verificar si tiene archivos SR
    if ls "$patient_dir"/*/SR_* 2>/dev/null | grep -q .; then
        echo "Procesando: $patient_id"
        python3 algorithms/bd_extracts/bd_extract_ge.py "$patient_id"
    fi
done
```

**Nota:** Actualmente solo 1 paciente tiene SR (MMD1878574000). Los demás 255 pacientes tienen solo BD, esperando que lleguen sus SR.

## Contacto Técnico

Si los SR no llegan para pacientes antiguos, verificar:
1. Configuración del equipo GE Lunar para exportar SR
2. Configuración DICOM del equipo (debe enviar SOP Class Enhanced SR Storage)
3. Firewall/red permite tráfico SR al puerto 5665
