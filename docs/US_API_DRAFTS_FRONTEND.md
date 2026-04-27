# US Drafts API - Resumen para Frontend

## Endpoint
- Metodo: `POST`
- URL: `/api/us/draft`
- Content-Type: `application/json`

## Objetivo
Guardar un borrador de reporte US en `reports.drafts`.

Si ya existe un draft para el mismo `mrn` + `acc`, se actualiza.
Si no existe, se crea uno nuevo.

## Request Body
```json
{
  "mrn": "11204810",
  "acc": "3107839",
  "report": "Texto del reporte",
  "notes": "Paciente con antecedentes",
  "author": "Dr. Perez"
}
```

### Campos
- `mrn` (string, requerido)
- `acc` (string, opcional)
- `report` (string, requerido)
- `notes` (string, opcional, admite `null`)
- `author` (string, opcional, admite `null`)

## Respuestas

### 201 Created (draft nuevo)
```json
{
  "success": true,
  "action": "created",
  "guid": "8d6e5f67-1f64-4d83-9ce6-8b2a6f4e2e4b",
  "mrn": "11204810",
  "acc": "3107839",
  "notes": "Paciente con antecedentes",
  "author": "Dr. Perez",
  "createdon": "2026-03-12T14:25:01.120000",
  "updatedon": "2026-03-12T14:25:01.120000",
  "message": "US draft created successfully"
}
```

### 200 OK (draft actualizado)
```json
{
  "success": true,
  "action": "updated",
  "guid": "8d6e5f67-1f64-4d83-9ce6-8b2a6f4e2e4b",
  "mrn": "11204810",
  "acc": "3107839",
  "notes": "Se agrega nota nueva",
  "author": "Dr. Perez",
  "createdon": "2026-03-12T14:25:01.120000",
  "updatedon": "2026-03-12T14:30:10.002000",
  "message": "US draft updated successfully"
}
```

### 400 Bad Request
Errores de validacion:
- Content-Type no es `application/json`
- Body vacio
- `mrn` vacio
- `report` vacio
- `notes` no es string ni null
- `author` no es string ni null

Ejemplo:
```json
{
  "success": false,
  "error": "Field \"mrn\" is required and cannot be empty"
}
```

### 500 Internal Server Error
Error de base de datos o error inesperado.

## Ejemplo rapido (Axios)
```javascript
import axios from "axios";

const payload = {
  mrn: "11204810",
  acc: "3107839",
  report: "Texto del reporte",
  notes: "Paciente con antecedentes",
  author: "Dr. Perez"
};

const response = await axios.post("http://3.137.131.89:5667/api/us/draft", payload, {
  headers: { "Content-Type": "application/json" }
});

// response.data.action => "created" | "updated"
// response.data.guid => id del draft
```
