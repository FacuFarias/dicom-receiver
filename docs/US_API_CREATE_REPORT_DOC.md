# POST /api/us/report - Create/Update US Report

## Description

Endpoint to create or update an ultrasound (US) report in the PostgreSQL database (`reports.us` table).

## URL

```
POST http://localhost:5667/api/us/report
```

## Headers

```
Content-Type: application/json
```

## Request Body

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `mrn` | string | Patient's Medical Record Number (required) |
| `report` | string | Ultrasound report content (required) |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `acc` | string | Study Accession Number (optional) |

### Request Example

```json
{
  "mrn": "12345678",
  "acc": "ACC001234",
  "report": "ULTRASOUND EXAMINATION\n\nClinical History: Hip pain\n\nFindings:\n- Normal bone density\n- No fractures detected\n- Joint space within normal limits\n\nConclusion: Normal hip ultrasound examination."
}
```

## Behavior

### New Report Creation
If a report **DOES NOT exist** for the specified MRN and ACC:
- ✅ A new record is created in `reports.us`
- A GUID is automatically generated
- Both `createdon` and `updatedon` timestamps are set to the current time

### Existing Report Update
If a report **ALREADY EXISTS** for the specified MRN and ACC:
- 🔄 The `report` field is updated with the new content
- The `updatedon` timestamp is updated to the current time
- The same GUID and original `createdon` timestamp are preserved

### Search Logic

**If ACC is provided:**
```sql
WHERE mrn = %s AND acc = %s
```

**If ACC is NOT provided (empty or null):**
```sql
WHERE mrn = %s AND (acc IS NULL OR acc = '')
ORDER BY createdon DESC
LIMIT 1
```
*Note: Updates the most recent report without ACC for that MRN*

## Response

### Success Response (Creation)

**Status Code:** `201 Created`

```json
{
  "success": true,
  "action": "created",
  "guid": "000000000cc6eee7a-65b6-483b-8819-d3c5cf58bb92",
  "mrn": "12345678",
  "acc": "ACC001234",
  "createdon": "2026-03-17T15:06:32.756655",
  "updatedon": "2026-03-17T15:06:32.756655",
  "message": "US report created successfully"
}
```

### Success Response (Update)

**Status Code:** `200 OK`

```json
{
  "success": true,
  "action": "updated",
  "guid": "000000000cc6eee7a-65b6-483b-8819-d3c5cf58bb92",
  "mrn": "12345678",
  "acc": "ACC001234",
  "createdon": "2026-03-17T15:06:32.756655",
  "updatedon": "2026-03-17T15:10:45.123456",
  "message": "US report updated successfully"
}
```

## Error Responses

### Error 400 - Invalid Content-Type

```json
{
  "success": false,
  "error": "Content-Type must be application/json"
}
```

### Error 400 - Empty Request Body

```json
{
  "success": false,
  "error": "Request body is empty"
}
```

### Error 400 - MRN Missing

```json
{
  "success": false,
  "error": "Field \"mrn\" is required and cannot be empty"
}
```

### Error 400 - Report Missing

```json
{
  "success": false,
  "error": "Field \"report\" is required and cannot be empty"
}
```

### Error 500 - Database Error

```json
{
  "success": false,
  "error": "Database error",
  "details": "connection to database failed"
}
```

### Error 500 - Internal Server Error

```json
{
  "success": false,
  "error": "Internal server error",
  "details": "unexpected error message"
}
```

## Usage Examples

### cURL - Create Report

```bash
curl -X POST http://localhost:5667/api/us/report \
  -H "Content-Type: application/json" \
  -d '{
    "mrn": "12345678",
    "acc": "ACC001234",
    "report": "ULTRASOUND EXAMINATION\n\nFindings: Normal study."
  }'
```

### cURL - Update Report

```bash
curl -X POST http://localhost:5667/api/us/report \
  -H "Content-Type: application/json" \
  -d '{
    "mrn": "12345678",
    "acc": "ACC001234",
    "report": "ULTRASOUND EXAMINATION - UPDATED\n\nFindings: Updated findings with new information."
  }'
```

### cURL - Create Report without ACC

```bash
curl -X POST http://localhost:5667/api/us/report \
  -H "Content-Type: application/json" \
  -d '{
    "mrn": "12345678",
    "report": "Emergency ultrasound - no accession number assigned yet."
  }'
```

### Python - requests

```python
import requests

url = "http://localhost:5667/api/us/report"
headers = {"Content-Type": "application/json"}
data = {
    "mrn": "12345678",
    "acc": "ACC001234",
    "report": "ULTRASOUND EXAMINATION\n\nFindings: Normal study."
}

response = requests.post(url, json=data, headers=headers)
print(response.status_code)
print(response.json())
```

### JavaScript - fetch

```javascript
const url = "http://localhost:5667/api/us/report";
const data = {
  mrn: "12345678",
  acc: "ACC001234",
  report: "ULTRASOUND EXAMINATION\n\nFindings: Normal study."
};

fetch(url, {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify(data)
})
  .then(response => response.json())
  .then(data => console.log(data))
  .catch(error => console.error("Error:", error));
```

## Validations

### Required Fields
- ❌ Empty `mrn` → Error 400
- ❌ Empty `report` → Error 400
- ✅ Empty `acc` → Allowed (stored as NULL)

### Data Cleaning
- The `mrn`, `acc`, and `report` fields are cleaned with `.strip()`
- Leading and trailing whitespace is automatically removed

## Database

### Table: `reports.us`

```sql
Schema: reports
Table: us

Columns:
  - guid (UUID, Primary Key)
  - mrn (VARCHAR)
  - acc (VARCHAR, nullable)
  - report (TEXT)
  - createdon (TIMESTAMP)
  - updatedon (TIMESTAMP)
```

### Connection

```
Host: localhost
User: facundo
Password: qii123
Database: qii
```

## Logging

The endpoint logs the following events:

```
✓ US Report CREATED - MRN: 12345678, ACC: ACC001234, GUID: 000000000cc6eee7a...
✓ US Report UPDATED - MRN: 12345678, ACC: ACC001234, GUID: 000000000cc6eee7a...
✗ Database error: connection timeout
✗ Error creating US report: unexpected error
```

## Differences with `/api/us/draft`

| Feature | `/api/us/report` | `/api/us/draft` |
|---------|------------------|-----------------|
| Target table | `reports.us` | `reports.drafts` |
| Extra fields | - | `notes`, `author` |
| AI forwarding | ❌ No | ✅ Yes (to `https://ai.qiitools.com/api/upload-report`) |
| Purpose | Final reports | Draft reports |

## Important Notes

1. **Partial Idempotency**: Calling the endpoint multiple times with the same MRN/ACC will update the existing report, not create duplicates.

2. **No Forwarding**: This endpoint does NOT forward data to the AI system. Use `/api/us/draft` if you need automatic forwarding.

3. **Timestamps**: 
   - `createdon`: Set only on initial creation
   - `updatedon`: Updated on each modification

4. **Stable GUID**: The GUID remains constant during updates, useful for external references.

## Testing

To verify the endpoint works:

```bash
# Health check first
curl http://localhost:5667/api/health

# Create a test report
curl -X POST http://localhost:5667/api/us/report \
  -H "Content-Type: application/json" \
  -d '{"mrn":"TEST001","acc":"TEST001","report":"Test report content"}'
```

## See Also

- [POST /api/us/draft](US_API_DRAFTS_FRONTEND.md) - Create drafts (with AI forwarding)
- [GET /api/us/report/\<mrn\>](us_api.py#L455) - Get reports by MRN
- [GET /api/us/report/\<mrn\>/\<acc\>](us_api.py#L495) - Get specific report
- [GET /api/health](us_api.py#L67) - Health check
- [GET /api/us/stats](us_api.py#L545) - Report statistics
