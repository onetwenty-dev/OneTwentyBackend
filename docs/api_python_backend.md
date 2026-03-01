# OneTwenty Python Backend — API Documentation

> **Base URL:** `/api/v1`
>
> **Framework:** FastAPI (Python)  
> **Architecture:** Multi-tenant SaaS — each user belongs to a **tenant** (isolated OneTwenty instance), identified by subdomain slug.

---

## Table of Contents

### Authentication
- [Authentication Methods](#authentication-methods)
- [Obtaining a JWT Token](#obtaining-a-jwt-token)

### Auth Endpoints
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 1 | `POST` | [`/auth/signup`](#post-authsignup) | None | Register a new user |
| 2 | `POST` | [`/auth/login`](#post-authlogin) | None | Login, returns JWT tokens |
| 3 | `POST` | [`/auth/refresh-token`](#post-authrefresh-token) | None | Refresh an expired access token |
| 4 | `POST` | [`/auth/api-secret`](#post-authapi-secret) | JWT | Get or create API secret for tenant |
| 5 | `POST` | [`/auth/reset-api-secret`](#post-authreset-api-secret) | JWT | Rotate (revoke + regenerate) API secret |
| 6 | `GET` | [`/auth/profile`](#get-authprofile) | JWT | Get current user's profile and tenant info |

### Status & Settings
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 7 | `GET` | [`/status`](#get-status) | Multi | Server status and tenant configuration |
| 8 | `PUT` | [`/settings`](#put-settings) | JWT | Update tenant settings |

### Entries (CGM Data)
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 9 | `GET` | [`/entries`](#get-entries) | Multi | List entries with flexible filtering |
| 10 | `GET` | [`/entries/current`](#get-entriescurrent) | Multi | Latest entry (TSV format) |
| 11 | `POST` | [`/entries`](#post-entries) | API Secret | Upload new entries |

### Doctors (RBAC)
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 12 | `POST` | [`/doctors/assign-patient`](#post-doctorsassign-patient) | JWT | Doctor assigns a patient |
| 13 | `GET` | [`/doctors/my-patients`](#get-doctorsmy-patients) | JWT | Doctor lists their patients |
| 14 | `GET` | [`/doctors/my-doctors`](#get-doctorsmy-doctors) | JWT | Patient lists their doctors |
| 15 | `DELETE` | [`/doctors/revoke/:doctor_id`](#delete-doctorsrevokedoctor_id) | JWT | Patient revokes doctor access |

### WebSocket
| # | Protocol | Endpoint | Auth | Description |
|---|----------|----------|------|-------------|
| 16 | `WS` | [`/ws`](#websocket-ws) | JWT (query) | Real-time glucose data stream |

---

## Authentication Methods

The Python backend supports **three authentication strategies**, used by different clients. Endpoints marked **"Multi"** accept all three, tried in order.

### 1. API Secret Header (SHA-1 hashed)

Used by **uploaders** (xDrip, Loop, Spike). The client sends the SHA-1 hash of their API secret:

```bash
# Generate the SHA-1 hash of your API secret
echo -n "my-api-secret" | shasum | awk '{print $1}'

# Use in requests
curl -H "api-secret: <sha1-hash>" https://slug.onetwenty.dev/api/v1/entries
```

> [!NOTE]
> The backend accepts both plain text and SHA-1 hashed secrets for backward compatibility.  
> On subdomain requests, the API key is validated **only against that tenant**, preventing cross-tenant access.

### 2. JWT Bearer Token

Used by the **dashboard/SaaS frontend**. Obtained via the `/auth/login` endpoint:

```bash
curl -H "Authorization: Bearer <access-token>" https://slug.onetwenty.dev/api/v1/entries
```

### 3. Subdomain (Read-Only Fallback)

If neither API secret nor JWT is provided, the backend resolves the tenant from the **subdomain slug** in the URL. This provides **public read-only access**:

```bash
# No auth header needed — tenant resolved from "ayush" subdomain
curl https://ayush.onetwenty.dev/api/v1/entries
```

### Auth Resolution Order

For "Multi" auth endpoints, the backend tries in this order:
1. `api-secret` header → Tenant from API key lookup
2. `Authorization: Bearer <jwt>` → Tenant from user's JWT → user → tenant mapping
3. Subdomain → Tenant from slug in the `Host` header
4. If all fail → **401 Unauthorized**

---

## Obtaining a JWT Token

```bash
# 1. Sign up
curl -X POST https://onetwenty.dev/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'

# 2. Login to get tokens
curl -X POST https://onetwenty.dev/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user@example.com", "password": "securepass123"}'

# Response:
# {
#   "access_token": "eyJhbGciOi...",
#   "refresh_token": "eyJhbGciOi...",
#   "token_type": "bearer"
# }

# 3. Use the access_token
curl -H "Authorization: Bearer eyJhbGciOi..." https://slug.onetwenty.dev/api/v1/entries

# 4. When access token expires, refresh it
curl -X POST "https://onetwenty.dev/api/v1/auth/refresh-token?refresh_token=eyJhbGciOi..."
```

> [!IMPORTANT]
> - **Access tokens** expire in **14,400 minutes (10 days)**
> - **Refresh tokens** expire in **7 days**
> - Algorithm: **HS256**

---

## Endpoint Details

---

### POST `/auth/signup`

Register a new user account.

**Auth:** None

```bash
curl -X POST https://onetwenty.dev/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123"
  }'
```

**Request Body:**
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `email` | string (email) | ✅ | Valid email format |
| `password` | string | ✅ | 8–72 characters |

**Response (200):**
```json
{
  "message": "User created successfully",
  "user_id": "public-uuid-here"
}
```

---

### POST `/auth/login`

Authenticate and receive JWT tokens.

**Auth:** None

```bash
curl -X POST https://onetwenty.dev/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user@example.com",
    "password": "securepass123"
  }'
```

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | string | ✅ | Email or public ID |
| `password` | string | ✅ | User password |

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Error (401):**
```json
{ "detail": "Invalid credentials" }
```

---

### POST `/auth/refresh-token`

Refresh an expired access token using a valid refresh token.

**Auth:** None

```bash
curl -X POST "https://onetwenty.dev/api/v1/auth/refresh-token?refresh_token=eyJhbGciOi..."
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOi...(new)...",
  "refresh_token": "eyJhbGciOi...(same)...",
  "token_type": "bearer"
}
```

---

### POST `/auth/api-secret`

Get the existing API secret for the user's tenant, or create one if none exists.

**Auth:** JWT Bearer

```bash
curl -X POST https://onetwenty.dev/api/v1/auth/api-secret \
  -H "Authorization: Bearer <access-token>"
```

**Response (200):**
```json
{ "api_secret": "a1b2c3d4e5f6..." }
```

---

### POST `/auth/reset-api-secret`

Revoke the current API secret and generate a new one. All devices using the old secret will stop working.

**Auth:** JWT Bearer

```bash
curl -X POST https://onetwenty.dev/api/v1/auth/reset-api-secret \
  -H "Authorization: Bearer <access-token>"
```

**Response (200):**
```json
{ "api_secret": "new-secret-value..." }
```

> [!CAUTION]
> This invalidates the old API secret immediately. All uploaders (xDrip, Loop, etc.) will need to be reconfigured with the new secret.

---

### GET `/auth/profile`

Get the current user's profile including tenant information and subdomain URL.

**Auth:** JWT Bearer

```bash
curl https://onetwenty.dev/api/v1/auth/profile \
  -H "Authorization: Bearer <access-token>"
```

**Response (200):**
```json
{
  "user_id": 1,
  "tenant_id": 5,
  "tenant_name": "Ayush's OneTwenty",
  "slug": "ayush",
  "subdomain_url": "https://ayush.onetwenty.dev"
}
```

---

### GET `/status`

Server status and tenant configuration. The frontend uses this to initialize itself.

**Auth:** Multi (API Secret → JWT → Subdomain)  
**Route aliases:** `/status`, `/status.json`

#### With API secret
```bash
curl -H "api-secret: <sha1-hash>" https://ayush.onetwenty.dev/api/v1/status
```

#### With JWT
```bash
curl -H "Authorization: Bearer <token>" https://ayush.onetwenty.dev/api/v1/status
```

#### With subdomain only (public)
```bash
curl https://ayush.onetwenty.dev/api/v1/status
```

#### JSON extension
```bash
curl https://ayush.onetwenty.dev/api/v1/status.json
```

**Response (200):**
```json
{
  "status": "ok",
  "name": "Ayush's OneTwenty",
  "version": "15.0.0-saas",
  "serverTime": null,
  "apiEnabled": true,
  "careportalEnabled": true,
  "boluscalcEnabled": true,
  "settings": {
    "title": "OneTwenty",
    "units": "mg/dl",
    "theme": "default",
    "language": "en",
    "alarm_urgent_high": 260,
    "alarm_high": 180,
    "alarm_low": 70,
    "alarm_urgent_low": 55,
    "bg_target_top": 180,
    "bg_target_bottom": 80,
    "enable": ["careportal", "boluscalc", "food", "rawbg", "iob", "cob", "bwp", "cage", "sage", "iage", "treatmentnotify", "basal", "bridge"]
  },
  "extendedSettings": {
    "devicestatus": { "advanced": true }
  },
  "units": "mg/dl",
  "enable": ["careportal", "boluscalc", "..."],
  "thresholds": {
    "bg_high": 180,
    "bg_target_top": 180,
    "bg_target_bottom": 80,
    "bg_low": 70
  }
}
```

---

### PUT `/settings`

Update tenant settings. Accepts partial updates — only provided fields are merged.

**Auth:** JWT Bearer

```bash
curl -X PUT https://onetwenty.dev/api/v1/settings \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "units": "mmol",
    "alarm_high": 200,
    "alarm_low": 65,
    "title": "My CGM"
  }'
```

**Response (200):**
```json
{
  "status": "ok",
  "message": "Settings updated successfully",
  "settings": {
    "title": "My CGM",
    "units": "mmol",
    "alarm_high": 200,
    "alarm_low": 65,
    "...": "...merged with existing settings..."
  }
}
```

---

### GET `/entries`

List CGM entries for the authenticated tenant.

**Auth:** Multi (API Secret → JWT → Subdomain)  
**Route aliases:** `/entries`, `/entries/`

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `count` | int | 10 | Number of entries to return |
| `hours` | int | — | Time range in hours (overrides `count`) |
| `start` | string | — | Start timestamp (ISO 8601 or Unix ms) |
| `end` | string | — | End timestamp (ISO 8601 or Unix ms) |

**Priority:** `start`+`end` > `hours` > `count`

#### Basic — latest 10 entries
```bash
curl https://ayush.onetwenty.dev/api/v1/entries
```

#### With count
```bash
curl "https://ayush.onetwenty.dev/api/v1/entries?count=50"
```

#### By time range (hours)
```bash
# Last 2 hours
curl "https://ayush.onetwenty.dev/api/v1/entries?hours=2"

# Last 24 hours
curl "https://ayush.onetwenty.dev/api/v1/entries?hours=24"
```

#### By timestamp range (ISO)
```bash
curl "https://ayush.onetwenty.dev/api/v1/entries?start=2025-08-27T00:00:00Z&end=2025-08-27T23:59:59Z"
```

#### By timestamp range (Unix ms)
```bash
curl "https://ayush.onetwenty.dev/api/v1/entries?start=1756339200000&end=1756425600000"
```

#### With API Secret
```bash
curl -H "api-secret: <sha1-hash>" https://ayush.onetwenty.dev/api/v1/entries
```

#### With JWT
```bash
curl -H "Authorization: Bearer <token>" https://ayush.onetwenty.dev/api/v1/entries
```

#### Public (subdomain only)
```bash
curl https://ayush.onetwenty.dev/api/v1/entries
```

**Response (200):**
```json
[
  {
    "_id": "65cf81bc436037528ec75fa5",
    "type": "sgv",
    "dateString": "2025-08-27T12:00:00.000Z",
    "date": 1756339200000,
    "sgv": 120,
    "direction": "Flat",
    "noise": 1,
    "device": "xDrip-LibreLink",
    "tenant_id": "5"
  }
]
```

---

### GET `/entries/current`

Get the latest single entry in **TSV (tab-separated values)** format. Used by uploaders to check the last known reading.

**Auth:** Multi (API Secret → JWT → Subdomain)  
**Route aliases:** `/entries/current`, `/entries/current.json`  
**Content-Type:** `text/plain; charset=utf-8`

#### Base curl
```bash
curl https://ayush.onetwenty.dev/api/v1/entries/current
```

#### With JSON extension
```bash
curl https://ayush.onetwenty.dev/api/v1/entries/current.json
```

#### With API secret
```bash
curl -H "api-secret: <sha1-hash>" https://ayush.onetwenty.dev/api/v1/entries/current
```

**Response (200):** Plain text TSV
```
"2025-08-27T12:00:00.000Z"	1756339200000	120	"Flat"	"xDrip-LibreLink"
```

Fields: `dateString`, `date`, `sgv`, `direction`, `device`

**Error (404):**
```json
{ "detail": "No entries found" }
```

---

### POST `/entries`

Upload new CGM entries. Broadcasts new entries to connected WebSocket clients.

**Auth:** API Secret (header)  
**Route aliases:** `/entries`, `/entries/`, `/entries.json`  
**Status:** `201 Created`

#### Single entry
```bash
curl -X POST https://ayush.onetwenty.dev/api/v1/entries \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "sgv",
    "dateString": "2025-08-27T12:00:00.000Z",
    "date": 1756339200000,
    "sgv": 120,
    "direction": "Flat",
    "device": "xDrip-LibreLink"
  }'
```

#### Multiple entries (batch)
```bash
curl -X POST https://ayush.onetwenty.dev/api/v1/entries \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '[
    {"type":"sgv","dateString":"2025-08-27T12:00:00.000Z","date":1756339200000,"sgv":120,"direction":"Flat"},
    {"type":"sgv","dateString":"2025-08-27T12:05:00.000Z","date":1756339500000,"sgv":125,"direction":"FortyFiveUp"}
  ]'
```

#### JSON extension
```bash
curl -X POST https://ayush.onetwenty.dev/api/v1/entries.json \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '[...]'
```

**Request Body (EntryCreate schema):**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | ✅ (default: `"sgv"`) | Entry type: `sgv`, `mbg`, `cal`, etc. |
| `dateString` | string | ✅ | ISO 8601 date string |
| `date` | int | ✅ | Unix epoch (milliseconds) |
| `sgv` | int | ❌ | Glucose value (mg/dl) — for `sgv` type |
| `direction` | string | ❌ | Trend arrow: `Flat`, `FortyFiveUp`, `SingleUp`, etc. |
| `noise` | int | ❌ | Noise level |
| `filtered` | int | ❌ | Raw filtered CGM value |
| `unfiltered` | int | ❌ | Raw unfiltered CGM value |
| `rssi` | int | ❌ | Signal strength |
| `device` | string | ❌ | Device name |

> [!NOTE]
> Extra fields beyond this schema are **allowed** (schema uses `extra = "allow"`) for legacy compatibility.

**Response (201):**
```json
{ "inserted_ids": ["65cf81bc436037528ec75fa5", "65cf81bc436037528ec75fa6"] }
```

**Side effect:** Each new entry is broadcast to all WebSocket clients connected to the same tenant.

---

### POST `/doctors/assign-patient`

Assign a patient to the logged-in doctor.

**Auth:** JWT Bearer  
**Role required:** `doctor`

```bash
curl -X POST "https://onetwenty.dev/api/v1/doctors/assign-patient?patient_email=patient@example.com" \
  -H "Authorization: Bearer <doctor-jwt-token>"
```

**Response (200):**
```json
{ "status": "ok", "message": "Patient assigned successfully" }
```

**Errors:**
| Code | Detail |
|------|--------|
| 403 | `"Only doctors can assign patients"` |
| 404 | `"Patient not found"` |
| 400 | `"Can only assign regular users as patients"` |

---

### GET `/doctors/my-patients`

Get all patients assigned to the logged-in doctor.

**Auth:** JWT Bearer  
**Role required:** `doctor`

```bash
curl https://onetwenty.dev/api/v1/doctors/my-patients \
  -H "Authorization: Bearer <doctor-jwt-token>"
```

**Response (200):**
```json
[
  {
    "id": 3,
    "email": "patient@example.com",
    "tenant_id": 5,
    "granted_at": "2025-08-27T12:00:00Z"
  }
]
```

---

### GET `/doctors/my-doctors`

Get all doctors who have access to the logged-in user's data.

**Auth:** JWT Bearer

```bash
curl https://onetwenty.dev/api/v1/doctors/my-doctors \
  -H "Authorization: Bearer <patient-jwt-token>"
```

**Response (200):**
```json
[
  {
    "id": 7,
    "email": "dr.smith@clinic.com",
    "granted_at": "2025-08-27T12:00:00Z"
  }
]
```

---

### DELETE `/doctors/revoke/:doctor_id`

Revoke a doctor's access to the logged-in user's data.

**Auth:** JWT Bearer

```bash
curl -X DELETE https://onetwenty.dev/api/v1/doctors/revoke/7 \
  -H "Authorization: Bearer <patient-jwt-token>"
```

**Response (200):**
```json
{ "status": "ok", "message": "Doctor access revoked successfully" }
```

**Error (404):**
```json
{ "detail": "Doctor access not found" }
```

---

### WebSocket `/ws`

Real-time glucose data stream. Receives new entries as they're uploaded.

**Auth:** JWT via query parameter  
**Protocol:** WebSocket

#### Connect
```
ws://ayush.onetwenty.dev/api/v1/ws?token=<jwt-access-token>
```

#### JavaScript example
```javascript
const ws = new WebSocket(`wss://ayush.onetwenty.dev/api/v1/ws?token=${accessToken}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === "new_entry") {
    console.log("New CGM reading:", data.data);
    // { type: "sgv", sgv: 120, direction: "Flat", ... }
  }

  if (data.type === "ping") {
    ws.send(JSON.stringify({ type: "pong" }));
  }
};
```

#### Message Types

**Server → Client:**
| Type | Description |
|------|-------------|
| `new_entry` | New CGM entry uploaded. `data` contains the full entry object |
| `ping` | Keep-alive ping (sent every ~30s if client is silent) |

**Client → Server:**
| Type | Description |
|------|-------------|
| `ping` | Client ping. Server responds with `{"type": "pong"}` |

#### Connection Lifecycle
1. Client connects with JWT in query parameter
2. Server validates JWT → resolves user → resolves tenant
3. Connection is added to tenant's broadcast group
4. Client receives `new_entry` messages whenever entries are POSTed
5. Keep-alive ping/pong every 30 seconds

**Close Codes:**
| Code | Reason |
|------|--------|
| 1008 | `"Invalid token"` or `"No tenant found"` or `"Authentication failed"` |
| 1011 | `"Internal error"` |

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created (entries POST) |
| `400` | Bad Request / validation error |
| `401` | Unauthorized — invalid or missing credentials |
| `403` | Forbidden — wrong role (e.g., non-doctor calling doctor endpoints) |
| `404` | Not found |
| `422` | Validation error (FastAPI automatic) |
| `500` | Internal Server Error |

---

## Differences from Original OneTwenty API

| Feature | Original OneTwenty | OneTwenty Python Backend |
|---------|--------------------|-----------------------------|
| **Multi-tenancy** | Single instance per user | Shared SaaS, isolated by tenant |
| **Auth** | API Secret + OneTwenty tokens | API Secret + JWT + Subdomain |
| **User accounts** | None (just API secret) | Full signup/login with JWT |
| **Entries GET formats** | JSON, TSV, CSV, TXT, HTML | JSON (GET list), TSV (current) |
| **`If-Modified-Since`** | Supported | Not yet implemented |
| **`find[]` query syntax** | MongoDB nested query | `count`, `hours`, `start`/`end` |
| **Content negotiation** | `Accept` header + URL extension | Route aliases (`.json`) |
| **Doctor RBAC** | Not available | Built-in doctor-patient system |
| **WebSocket** | Socket.IO based | Native WebSocket with JWT auth |
| **Treatments/Profile/Food** | Full CRUD | Not yet implemented |
| **Device Status** | Full CRUD | Not yet implemented |

---

## Notes

- **Database:** MongoDB for entries (document store), PostgreSQL for users/tenants/auth (relational)
- **Subdomain isolation:** API keys are validated against the subdomain's tenant only, preventing cross-tenant access
- **WebSocket broadcasts:** Every `POST /entries` automatically broadcasts to all WebSocket clients for that tenant
- **Schema flexibility:** Entry schema allows extra fields (`extra = "allow"`) for legacy uploader compatibility
- **Password limits:** Passwords are capped at 72 characters (bcrypt limit)
