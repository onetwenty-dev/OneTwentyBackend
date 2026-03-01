# OneTwenty SaaS API Documentation

**Base URL:** `http://localhost:8000/api/v1`

**Version:** 15.0.0-saas

---

## Authentication

All endpoints except `/auth/signup` and `/auth/login` require authentication.

### Authentication Methods

1. **JWT (Dashboard/Web):** Include `Authorization: Bearer <access_token>` header
2. **API Key (Devices/Uploaders):** Include `api-secret: <api_key>` header

---

## Endpoints

### 1. Authentication & User Management

#### `POST /auth/signup`
Create a new user account and tenant.

**Request:**
```json
{
  "user_id": "user@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "message": "User created successfully",
  "user_id": "ABC123XYZ"
}
```

---

#### `POST /auth/login`
Login and receive JWT tokens.

**Request:**
```json
{
  "user_id": "user@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

#### `POST /auth/refresh-token`
Refresh an expired access token.

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

#### `POST /auth/api-secret`
Get or create API secret for device uploads.

**Auth:** JWT required

**Response:**
```json
{
  "api_secret": "ABC123XYZ_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
}
```

---

#### `POST /auth/reset-api-secret`
Revoke old API secret and generate a new one.

**Auth:** JWT required

**Response:**
```json
{
  "api_secret": "NEW123KEY_x9y8z7w6v5u4t3s2r1q0p9o8n7m6l5k4"
}
```

---

### 2. CGM Entries

#### `POST /entries`
Upload CGM readings (for devices/uploaders).

**Auth:** API Key required (`api-secret` header)

**Request (Single):**
```json
{
  "type": "sgv",
  "sgv": 120,
  "direction": "Flat",
  "device": "xDrip",
  "date": 1675234567000,
  "dateString": "2023-02-01T12:34:56.000Z"
}
```

**Request (Multiple):**
```json
[
  {
    "type": "sgv",
    "sgv": 120,
    "direction": "Flat",
    "device": "xDrip",
    "date": 1675234567000
  },
  {
    "type": "sgv",
    "sgv": 125,
    "direction": "FortyFiveUp",
    "device": "xDrip",
    "date": 1675234867000
  }
]
```

**Response:**
```json
{
  "status": "ok",
  "inserted": 2
}
```

---

#### `GET /entries?count=10`
Fetch recent CGM entries (for dashboard).

**Auth:** JWT required

**Query Parameters:**
- `count` (optional): Number of entries to return (default: 10)

**Response:**
```json
[
  {
    "_id": "63d9f8a1b2c3d4e5f6a7b8c9",
    "type": "sgv",
    "sgv": 125,
    "direction": "FortyFiveUp",
    "device": "xDrip",
    "date": 1675234867000,
    "dateString": "2023-02-01T12:39:27.000Z",
    "tenant_id": "1"
  }
]
```

---

### 3. Status & Settings

#### `GET /status` or `GET /status.json`
Get OneTwenty configuration for the frontend.

**Auth:** JWT required

**Response:**
```json
{
  "status": "ok",
  "name": "user@example.com's OneTwenty",
  "version": "15.0.0-saas",
  "apiEnabled": true,
  "careportalEnabled": true,
  "boluscalcEnabled": true,
  "units": "mg/dl",
  "enable": ["careportal", "boluscalc", "food", "rawbg", "iob"],
  "thresholds": {
    "bg_high": 180,
    "bg_target_top": 180,
    "bg_target_bottom": 80,
    "bg_low": 70
  },
  "settings": {
    "title": "My OneTwenty",
    "units": "mg/dl",
    "theme": "default",
    "language": "en",
    "alarm_urgent_high": 260,
    "alarm_high": 180,
    "alarm_low": 70,
    "alarm_urgent_low": 55,
    "bg_target_top": 180,
    "bg_target_bottom": 80,
    "enable": ["careportal", "boluscalc", "food"]
  }
}
```

---

#### `PUT /settings`
Update tenant settings (partial update supported).

**Auth:** JWT required

**Request:**
```json
{
  "title": "My Custom OneTwenty",
  "units": "mmol",
  "alarm_high": 200,
  "enable": ["careportal", "iob", "cob"]
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Settings updated successfully",
  "settings": {
    "title": "My Custom OneTwenty",
    "units": "mmol",
    "theme": "default",
    "language": "en",
    "alarm_urgent_high": 260,
    "alarm_high": 200,
    "alarm_low": 70,
    "alarm_urgent_low": 55,
    "bg_target_top": 180,
    "bg_target_bottom": 80,
    "enable": ["careportal", "iob", "cob"]
  }
}
```

---

### 4. Doctor-Patient Management

#### `POST /doctors/assign-patient`
Assign a patient to a doctor (doctor role required).

**Auth:** JWT required (doctor role)

**Request:**
```json
{
  "patient_email": "patient@example.com"
}
```

**Response:**
```json
{
  "status": "ok",
  "message": "Patient assigned successfully"
}
```

---

#### `GET /doctors/my-patients`
Get all patients assigned to the logged-in doctor.

**Auth:** JWT required (doctor role)

**Response:**
```json
[
  {
    "id": 5,
    "email": "patient@example.com",
    "tenant_id": 3,
    "granted_at": "2023-02-01T10:30:00Z"
  }
]
```

---

#### `GET /doctors/my-doctors`
Get all doctors who have access to your data.

**Auth:** JWT required

**Response:**
```json
[
  {
    "id": 2,
    "email": "doctor@example.com",
    "granted_at": "2023-02-01T10:30:00Z"
  }
]
```

---

#### `DELETE /doctors/revoke/{doctor_id}`
Revoke a doctor's access to your data.

**Auth:** JWT required

**Response:**
```json
{
  "status": "ok",
  "message": "Doctor access revoked successfully"
}
```

---

## User Roles

| Role | Description | Access |
|------|-------------|--------|
| **admin** | System administrator | Full access to all tenants and users |
| **doctor** | Healthcare provider | Read-only access to assigned patients' data |
| **user** | Patient/End-user | Full access to own data |

---

## User Tiers

| Tier | Description |
|------|-------------|
| **free** | Default tier for new users |
| **premium** | Paid tier (future) |
| **enterprise** | Enterprise tier (future) |

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

---

## Request ID Tracking

All responses include an `X-Request-ID` header for debugging and log correlation.

**Example:**
```
X-Request-ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Use this ID when reporting issues or searching logs.
