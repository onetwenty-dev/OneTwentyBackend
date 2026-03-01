# OneTwenty API v1 Documentation

> **Base URL:** `/api/v1`
>
> All endpoints below are relative to this base path.

---

## Table of Contents

### Authentication
- [Authentication Methods](#authentication-methods)

### Core Endpoints
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 1 | `GET` | [`/status`](#get-status) | Read | Server status, settings, and capabilities |
| 2 | `GET` | [`/verifyauth`](#get-verifyauth) | Read | Verify authentication and permissions |
| 3 | `GET` | [`/adminnotifies`](#get-adminnotifies) | Read | Admin notifications |

### Entries
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 4 | `GET` | [`/entries`](#get-entries) | Read | List entries (default: 10 latest SGV) |
| 5 | `GET` | [`/entries/current`](#get-entriescurrent) | Read | Latest single SGV entry |
| 6 | `GET` | [`/entries/:spec`](#get-entriesspec) | Read | Entry by ID or filtered by type (`sgv`, `mbg`, `cal`) |
| 7 | `POST` | [`/entries/`](#post-entries) | Create | Upload new entries |
| 8 | `POST` | [`/entries/preview`](#post-entriespreview) | Create | Preview (lint) entries without storing |
| 9 | `DELETE` | [`/entries/:spec`](#delete-entriesspec) | Delete | Delete entry by ID or by type filter |
| 10 | `DELETE` | [`/entries/`](#delete-entries) | Delete | Delete entries matching query |

### Entries — Query Helpers
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 11 | `GET` | [`/echo/:echo/:model?/:spec?`](#get-echo) | Read | Echo the generated Mongo query object |
| 12 | `GET` | [`/times/:prefix?/:regex?`](#get-times) | Read | Search entries by date/time regex patterns |
| 13 | `GET` | [`/times/echo/:prefix?/:regex?`](#get-timesecho) | Read | Echo the times query object |
| 14 | `GET` | [`/slice/:storage/:field/:type?/:prefix?/:regex?`](#get-slice) | Read | Advanced regex search across storage layers |
| 15 | `GET` | [`/count/:storage/where`](#get-count) | Read | Aggregate count of records |

### Treatments
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 16 | `GET` | [`/treatments`](#get-treatments) | Read | List treatments |
| 17 | `POST` | [`/treatments/`](#post-treatments) | Create | Add new treatments (requires `careportal`) |
| 18 | `PUT` | [`/treatments/`](#put-treatments) | Update | Update a treatment (requires `careportal`) |
| 19 | `DELETE` | [`/treatments/:id`](#delete-treatmentsid) | Delete | Delete treatment by ID (requires `careportal`) |
| 20 | `DELETE` | [`/treatments/`](#delete-treatments) | Delete | Delete treatments matching query (requires `careportal`) |

### Device Status
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 21 | `GET` | [`/devicestatus/`](#get-devicestatus) | Read | List device status records |
| 22 | `POST` | [`/devicestatus/`](#post-devicestatus) | Create | Upload device status |
| 23 | `DELETE` | [`/devicestatus/:id`](#delete-devicestatusid) | Delete | Delete device status by ID |
| 24 | `DELETE` | [`/devicestatus/`](#delete-devicestatus) | Delete | Delete device status matching query |

### Profile
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 25 | `GET` | [`/profile/`](#get-profile) | Read | List profiles |
| 26 | `GET` | [`/profiles/`](#get-profiles) | Read | List profiles (with query support) |
| 27 | `GET` | [`/profile/current`](#get-profilecurrent) | Read | Current active profile |
| 28 | `POST` | [`/profile/`](#post-profile) | Create | Create new profile |
| 29 | `PUT` | [`/profile/`](#put-profile) | Update | Update profile |
| 30 | `DELETE` | [`/profile/:_id`](#delete-profileid) | Delete | Delete profile by ID |

### Food
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 31 | `GET` | [`/food/`](#get-food) | Read | List all food items |
| 32 | `GET` | [`/food/quickpicks`](#get-foodquickpicks) | Read | List quick pick foods |
| 33 | `GET` | [`/food/regular`](#get-foodregular) | Read | List regular foods |
| 34 | `POST` | [`/food/`](#post-food) | Create | Create food item |
| 35 | `PUT` | [`/food/`](#put-food) | Update | Update food item |
| 36 | `DELETE` | [`/food/:_id`](#delete-foodid) | Delete | Delete food item by ID |

### Activity
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 37 | `GET` | [`/activity`](#get-activity) | Read | List activity records |
| 38 | `POST` | [`/activity/`](#post-activity) | Create | Add activity records (requires `careportal`) |
| 39 | `PUT` | [`/activity/`](#put-activity) | Update | Update activity record (requires `careportal`) |
| 40 | `DELETE` | [`/activity/:_id`](#delete-activityid) | Delete | Delete activity by ID (requires `careportal`) |

### Notifications
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 41 | `POST` | [`/notifications/pushovercallback`](#post-notificationspushovercallback) | None | Pushover acknowledgement callback |
| 42 | `GET` | [`/notifications/ack`](#get-notificationsack) | Ack | Acknowledge a notification |

### Experiments
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 43 | `GET` | [`/experiments/test`](#get-experimentstest) | Debug | Authorization debug test |

### Voice Assistants
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 44 | `POST` | [`/alexa`](#post-alexa) | Read | Amazon Alexa skill endpoint |
| 45 | `POST` | [`/googlehome`](#post-googlehome) | Read | Google Home action endpoint |

### Meta
| # | Method | Endpoint | Auth | Description |
|---|--------|----------|------|-------------|
| 46 | `GET` | [`/versions`](#get-versions) | None | List available API versions |

---

## Authentication Methods

OneTwenty API v1 supports three authentication methods. All write/delete operations require an API key to be set on the server.

### 1. API Secret Header (Hashed)

Pass the **SHA-1 hash** of your `API_SECRET` as a header:

```bash
# Generate the hash
echo -n "your-api-secret-here" | shasum | awk '{print $1}'

# Use in requests
curl -H "api-secret: <sha1-hash>" https://YOUR-SITE/api/v1/entries
```

### 2. Token in Query String (JWT)

Pass a JSON Web Token as a query parameter. Tokens are managed via the `/admin` UI:

```bash
curl "https://YOUR-SITE/api/v1/entries?token=<your-jwt-token>"
```

### 3. Bearer Token (JWT)

Pass a JWT in the `Authorization` header:

```bash
curl -H "Authorization: Bearer <jwt-token>" https://YOUR-SITE/api/v1/entries
```

> [!NOTE]
> Read endpoints may be accessible without authentication depending on server configuration (`AUTH_DEFAULT_ROLES`). Write and delete endpoints always require authentication with the API enabled.

---

## Common Query Parameters

These parameters are shared across many list/query endpoints:

| Parameter | Type | Description |
|-----------|------|-------------|
| `count` | number | Number of records to return (default varies by endpoint) |
| `find` | object | MongoDB-style query filter (nested syntax) |
| `find[field][$operator]` | string | Nested query operator (`$gte`, `$lte`, `$eq`, `$ne`, `$in`, etc.) |

**Example find syntax:**
```
?find[dateString][$gte]=2015-08-27
?find[sgv][$gte]=120
?find[type]=sgv
```

---

## Content Negotiation

Several endpoints (especially Entries) support multiple response formats via the `Accept` header or URL extension:

| Accept Header / Extension | Content-Type | Description |
|---------------------------|-------------|-------------|
| `application/json` / `.json` | JSON | Default — full JSON array |
| `text/plain` / `.txt` | Plain text | Tab-separated values (subset of fields) |
| `text/tab-separated-values` / `.tsv` | TSV | Tab-separated values |
| `text/csv` / `.csv` | CSV | Comma-separated values |
| `text/html` / `.html` | HTML | HTML representation |
| `image/svg+xml` / `.svg` | SVG | SVG badge (status only) |
| `image/png` / `.png` | PNG | PNG badge redirect (status only) |

> [!NOTE]
> TSV/CSV responses for entries include only: `dateString`, `date`, `sgv`, `direction`, `device`

### Conditional Requests

Many endpoints support **`If-Modified-Since`** header. If the data hasn't changed since the given date, the server returns **`304 Not Modified`**.

```bash
curl -H "If-Modified-Since: Thu, 27 Aug 2025 00:00:00 GMT" https://YOUR-SITE/api/v1/entries.json
```

Response headers include `Last-Modified` with the timestamp of the most recent record.

---

## Endpoint Details

---

### GET `/status`

Server status, settings, and capabilities.

**Permission:** `api:status:read`

**Supported response formats:** `json`, `svg`, `csv`, `txt`, `png`, `html`, `js`

#### Base curl
```bash
curl https://YOUR-SITE/api/v1/status
```

#### JSON response
```bash
curl -H "Accept: application/json" https://YOUR-SITE/api/v1/status.json
```

**Response:**
```json
{
  "status": "ok",
  "name": "OneTwenty",
  "version": "14.2.3",
  "serverTime": "2025-08-27T12:00:00.000Z",
  "serverTimeEpoch": 1756339200000,
  "apiEnabled": true,
  "careportalEnabled": true,
  "boluscalcEnabled": false,
  "settings": { ... },
  "extendedSettings": { ... },
  "authorized": null,
  "runtimeState": "loaded"
}
```

#### HTML response
```bash
curl -H "Accept: text/html" https://YOUR-SITE/api/v1/status.html
```
Returns: `<h1>STATUS OK</h1>`

#### Plain text response
```bash
curl -H "Accept: text/plain" https://YOUR-SITE/api/v1/status.txt
```
Returns: `STATUS OK`

#### SVG badge
```bash
curl https://YOUR-SITE/api/v1/status.svg
```
Redirects (302) to shields.io SVG badge.

#### PNG badge
```bash
curl https://YOUR-SITE/api/v1/status.png
```
Redirects (302) to shields.io PNG badge.

#### JavaScript (settings embed)
```bash
curl https://YOUR-SITE/api/v1/status.js
```
Returns: `this.serverSettings = {...};`

#### With auth token (to see authorized field)
```bash
curl "https://YOUR-SITE/api/v1/status.json?token=<jwt-token>"
curl "https://YOUR-SITE/api/v1/status.json?secret=<api-secret-hash>"
```

---

### GET `/verifyauth`

Verify current authentication status and permissions.

**Permission:** None (resolves from request)

#### Base curl
```bash
curl https://YOUR-SITE/api/v1/verifyauth
```

#### With API secret
```bash
curl -H "api-secret: <sha1-hash>" https://YOUR-SITE/api/v1/verifyauth
```

#### With token
```bash
curl "https://YOUR-SITE/api/v1/verifyauth?token=<jwt-token>"
```

**Response:**
```json
{
  "canRead": true,
  "canWrite": true,
  "isAdmin": true,
  "message": "OK",
  "rolefound": "FOUND",
  "permissions": "ROLE"
}
```

**Unauthorized response:**
```json
{
  "canRead": true,
  "canWrite": false,
  "isAdmin": false,
  "message": "UNAUTHORIZED",
  "rolefound": "NOTFOUND",
  "permissions": "DEFAULT"
}
```

---

### GET `/adminnotifies`

Get admin notification alerts.

**Permission:** None (returns `notifyCount` for all; full `notifies` array only for admin)

#### Base curl
```bash
curl https://YOUR-SITE/api/v1/adminnotifies
```

#### As admin
```bash
curl -H "api-secret: <sha1-hash>" https://YOUR-SITE/api/v1/adminnotifies
```

**Response (admin):**
```json
{
  "notifies": [
    { "persistent": true, "lastRecorded": 1756339200000, ... }
  ],
  "notifyCount": 1
}
```

**Response (non-admin):**
```json
{
  "notifies": [],
  "notifyCount": 1
}
```

---

### GET `/entries`

List entries. Defaults to 10 most recent, sorted newest first. Supports `If-Modified-Since`.

**Permission:** `api:entries:read`  
**Default count:** 10

#### Base curl
```bash
curl https://YOUR-SITE/api/v1/entries
```

#### JSON (explicit)
```bash
curl https://YOUR-SITE/api/v1/entries.json
curl -H "Accept: application/json" https://YOUR-SITE/api/v1/entries
```

#### TSV format
```bash
curl https://YOUR-SITE/api/v1/entries.tsv
curl -H "Accept: text/tab-separated-values" https://YOUR-SITE/api/v1/entries
```

#### CSV format
```bash
curl https://YOUR-SITE/api/v1/entries.csv
curl -H "Accept: text/csv" https://YOUR-SITE/api/v1/entries
```

#### Plain text (tab-separated)
```bash
curl https://YOUR-SITE/api/v1/entries.txt
curl -H "Accept: text/plain" https://YOUR-SITE/api/v1/entries
```

#### With count
```bash
curl "https://YOUR-SITE/api/v1/entries.json?count=50"
```

#### With find filter
```bash
# SGV entries >= 120 mg/dl
curl -g "https://YOUR-SITE/api/v1/entries.json?find[sgv][$gte]=120"

# Entries since a date
curl -g "https://YOUR-SITE/api/v1/entries.json?find[dateString][$gte]=2025-08-27"

# Specific type only
curl -g "https://YOUR-SITE/api/v1/entries.json?find[type]=sgv"

# Combined query
curl -g "https://YOUR-SITE/api/v1/entries.json?count=100&find[sgv][$gte]=100&find[sgv][$lte]=200"
```

#### With If-Modified-Since
```bash
curl -H "If-Modified-Since: Thu, 27 Aug 2025 12:00:00 GMT" https://YOUR-SITE/api/v1/entries.json
```
Returns `304 Not Modified` if no newer entries exist.

#### With authentication
```bash
curl -H "api-secret: <sha1-hash>" https://YOUR-SITE/api/v1/entries.json
curl "https://YOUR-SITE/api/v1/entries.json?token=<jwt-token>"
curl -H "Authorization: Bearer <jwt-token>" https://YOUR-SITE/api/v1/entries.json
```

---

### GET `/entries/current`

Get the latest single SGV entry.

**Permission:** `api:entries:read`

#### Base curl
```bash
curl https://YOUR-SITE/api/v1/entries/current
```

#### JSON
```bash
curl https://YOUR-SITE/api/v1/entries/current.json
```

#### TSV
```bash
curl https://YOUR-SITE/api/v1/entries/current.tsv
```

#### CSV
```bash
curl https://YOUR-SITE/api/v1/entries/current.csv
```

**JSON Response:**
```json
[
  {
    "type": "sgv",
    "dateString": "2025-08-27T12:00:00.000Z",
    "date": 1756339200000,
    "sgv": 120,
    "direction": "Flat",
    "noise": 1,
    "filtered": 164000,
    "unfiltered": 163000,
    "rssi": 200,
    "_id": "55cf81bc436037528ec75fa5"
  }
]
```

---

### GET `/entries/:spec`

Fetch entries by MongoDB ID or by type (e.g. `sgv`, `mbg`, `cal`).

**Permission:** `api:entries:read`

#### By ID
```bash
curl https://YOUR-SITE/api/v1/entries/55cf81bc436037528ec75fa5
curl https://YOUR-SITE/api/v1/entries/55cf81bc436037528ec75fa5.json
```

#### By type — SGV
```bash
curl https://YOUR-SITE/api/v1/entries/sgv
curl https://YOUR-SITE/api/v1/entries/sgv.json
curl "https://YOUR-SITE/api/v1/entries/sgv.json?count=50"
```

#### By type — MBG (meter blood glucose)
```bash
curl https://YOUR-SITE/api/v1/entries/mbg.json
```

#### By type — Calibrations
```bash
curl https://YOUR-SITE/api/v1/entries/cal.json
```

#### By type with filter
```bash
curl -g "https://YOUR-SITE/api/v1/entries/sgv.json?find[sgv][$gte]=180&count=20"
```

---

### POST `/entries/`

Upload new entries to the database. Accepts a single entry object or an array.

**Permission:** `api:entries:create`  
**Requires:** API enabled

#### Single entry
```bash
curl -X POST https://YOUR-SITE/api/v1/entries/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "sgv",
    "dateString": "2025-08-27T12:00:00.000Z",
    "date": 1756339200000,
    "sgv": 120,
    "direction": "Flat"
  }'
```

#### Multiple entries (batch)
```bash
curl -X POST https://YOUR-SITE/api/v1/entries/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '[
    {"type":"sgv","dateString":"2025-08-27T12:00:00.000Z","date":1756339200000,"sgv":120,"direction":"Flat"},
    {"type":"sgv","dateString":"2025-08-27T12:05:00.000Z","date":1756339500000,"sgv":125,"direction":"FortyFiveUp"}
  ]'
```

#### With JWT token
```bash
curl -X POST "https://YOUR-SITE/api/v1/entries/?token=<jwt-token>" \
  -H "Content-Type: application/json" \
  -d '[...]'
```

---

### POST `/entries/preview`

Preview/lint entries without persisting to database. Useful for debugging upload issues.

**Permission:** `api:entries:create`

```bash
curl -X POST https://YOUR-SITE/api/v1/entries/preview \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '[{"type":"sgv","dateString":"2025-08-27T12:00:00.000Z","date":1756339200000,"sgv":120,"direction":"Flat"}]'
```

Returns the processed entries as they would be stored (but doesn't actually store them).

---

### DELETE `/entries/:spec`

Delete a specific entry by ID or entries matching a type filter.

**Permission:** `api:entries:delete`  
**Requires:** API enabled

#### By ID
```bash
curl -X DELETE https://YOUR-SITE/api/v1/entries/55cf81bc436037528ec75fa5 \
  -H "api-secret: <sha1-hash>"
```

#### By type — delete all SGV entries (matching default count)
```bash
curl -X DELETE https://YOUR-SITE/api/v1/entries/sgv \
  -H "api-secret: <sha1-hash>"
```

#### Wildcard — delete regardless of type
```bash
curl -X DELETE "https://YOUR-SITE/api/v1/entries/*" \
  -H "api-secret: <sha1-hash>"
```

---

### DELETE `/entries/`

Delete entries matching a query.

**Permission:** `api:entries:delete`  
**Requires:** API enabled

```bash
curl -X DELETE -g "https://YOUR-SITE/api/v1/entries/?find[dateString][$lte]=2025-01-01&count=100" \
  -H "api-secret: <sha1-hash>"
```

---

### GET `/echo/:echo/:model?/:spec?`

Echo the MongoDB query object that would be generated. Useful for debugging.

**Permission:** `api:entries:read`

| Parameter | Description |
|-----------|-------------|
| `:echo` | Storage layer: `entries`, `treatments`, or `devicestatus` |
| `:model` | Optional: entry type (`sgv`, `mbg`, `cal`) |
| `:spec` | Optional: specific ID |

```bash
# Echo entries query
curl https://YOUR-SITE/api/v1/echo/entries

# Echo with type filter
curl "https://YOUR-SITE/api/v1/echo/entries/sgv.json?count=5"

# Echo treatments query
curl "https://YOUR-SITE/api/v1/echo/treatments.json"
```

**Response:**
```json
{
  "query": { ... },
  "input": { "count": "5" },
  "params": { "echo": "entries", "model": "sgv" },
  "storage": "entries"
}
```

---

### GET `/times/:prefix?/:regex?`

Search entries by date/time using regex with bash-style brace expansion. Default match field is `dateString`.

**Permission:** `api:entries:read`

| Parameter | Description |
|-----------|-------------|
| `:prefix` | Date prefix (supports brace expansion) |
| `:regex` | Time regex pattern (supports brace expansion) |

#### Entries in April 2025, 1pm–6pm, every 15 minutes
```bash
curl -s -g 'https://YOUR-SITE/api/v1/times/2025-04/T{13..18}:{00..15}.json?find[sgv][$gte]=120'
```

#### Entries across years
```bash
curl -s -g 'https://YOUR-SITE/api/v1/times/20{24..25}-04/T{13..18}:{00..15}.json?find[sgv][$gte]=120'
```

#### Entries in a specific year range
```bash
curl -s -g 'https://YOUR-SITE/api/v1/times/20{24..25}/T{13..18}:{00..15}.json?find[sgv][$gte]=120'
```

---

### GET `/times/echo/:prefix?/:regex?`

Echo the query object generated by the times regex pattern. For debugging.

```bash
curl -s -g 'https://YOUR-SITE/api/v1/times/echo/2025-04/T{13..18}:{00..15}.json'
```

**Response:**
```json
{
  "req": {
    "params": { "prefix": "2025-04", "regex": "T{13..18}:{00..15}" },
    "query": { "find": { "dateString": { "$in": [...] } } }
  },
  "pattern": [...]
}
```

---

### GET `/slice/:storage/:field/:type?/:prefix?/:regex?`

Advanced regex search allowing you to specify the storage layer, the field to regex against, and the entry type.

**Permission:** `api:entries:read`

| Parameter | Description |
|-----------|-------------|
| `:storage` | `entries`, `treatments`, or `devicestatus` |
| `:field` | Field name to match against (e.g. `dateString`) |
| `:type` | Entry type filter (e.g. `sgv`, `mbg`) |
| `:prefix` | Regex prefix |
| `:regex` | Regex tail |

```bash
# MBG entries matching dateString starting with 2025
curl https://YOUR-SITE/api/v1/slice/entries/dateString/mbg/2025.json

# SGV entries in treatments storage
curl https://YOUR-SITE/api/v1/slice/treatments/dateString/sgv/2025.json
```

---

### GET `/count/:storage/where`

Aggregate count of records matching a query.

**Permission:** `api:entries:read`

```bash
curl -g "https://YOUR-SITE/api/v1/count/entries/where?find[type]=sgv"
```

---

### GET `/treatments`

List treatment records. Supports `If-Modified-Since`.

**Permission:** `api:treatments:read`  
**Default count:** 100 (or 1000 if `find` is provided)

#### Base curl
```bash
curl https://YOUR-SITE/api/v1/treatments
```

#### With count
```bash
curl "https://YOUR-SITE/api/v1/treatments?count=50"
```

#### With filters
```bash
# Insulin doses >= 3 units
curl -g "https://YOUR-SITE/api/v1/treatments?find[insulin][$gte]=3"

# Carb entries >= 100g
curl -g "https://YOUR-SITE/api/v1/treatments?find[carbs][$gte]=100"

# Specific event type
curl -g "https://YOUR-SITE/api/v1/treatments?find[eventType]=Correction+Bolus"

# Since a date
curl -g "https://YOUR-SITE/api/v1/treatments?find[created_at][$gte]=2025-08-27"
```

#### With If-Modified-Since
```bash
curl -H "If-Modified-Since: Thu, 27 Aug 2025 12:00:00 GMT" https://YOUR-SITE/api/v1/treatments
```

---

### POST `/treatments/`

Add new treatment records.

**Permission:** `api:treatments:create`  
**Requires:** API enabled + `careportal` enabled

#### Single treatment
```bash
curl -X POST https://YOUR-SITE/api/v1/treatments/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType": "Correction Bolus",
    "insulin": 2.5,
    "created_at": "2025-08-27T12:00:00.000Z"
  }'
```

#### Multiple treatments
```bash
curl -X POST https://YOUR-SITE/api/v1/treatments/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '[
    {"eventType":"Meal Bolus","insulin":4,"carbs":60,"created_at":"2025-08-27T12:00:00.000Z"},
    {"eventType":"Correction Bolus","insulin":1.5,"created_at":"2025-08-27T14:00:00.000Z"}
  ]'
```

> [!NOTE]
> If `created_at` is not provided, the server sets it to the current server time.

---

### PUT `/treatments/`

Update an existing treatment record.

**Permission:** `api:treatments:update`  
**Requires:** API enabled + `careportal` enabled

```bash
curl -X PUT https://YOUR-SITE/api/v1/treatments/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "_id": "55cf81bc436037528ec75fa5",
    "eventType": "Correction Bolus",
    "insulin": 3.0,
    "created_at": "2025-08-27T12:00:00.000Z"
  }'
```

---

### DELETE `/treatments/:id`

Delete a specific treatment by ID.

**Permission:** `api:treatments:delete`  
**Requires:** API enabled + `careportal` enabled

```bash
curl -X DELETE https://YOUR-SITE/api/v1/treatments/55cf81bc436037528ec75fa5 \
  -H "api-secret: <sha1-hash>"
```

#### Wildcard — delete all matching
```bash
curl -X DELETE "https://YOUR-SITE/api/v1/treatments/*" \
  -H "api-secret: <sha1-hash>"
```

---

### DELETE `/treatments/`

Delete treatments matching a query.

**Permission:** `api:treatments:delete`  
**Requires:** API enabled + `careportal` enabled

```bash
curl -X DELETE -g "https://YOUR-SITE/api/v1/treatments/?find[created_at][$lte]=2025-01-01&count=50" \
  -H "api-secret: <sha1-hash>"
```

---

### GET `/devicestatus/`

List device status records.

**Permission:** `api:devicestatus:read`  
**Default count:** 10

#### Base curl
```bash
curl https://YOUR-SITE/api/v1/devicestatus/
```

#### With count
```bash
curl "https://YOUR-SITE/api/v1/devicestatus/?count=50"
```

#### With filters
```bash
curl -g "https://YOUR-SITE/api/v1/devicestatus/?find[device]=openaps://hostname"
curl -g "https://YOUR-SITE/api/v1/devicestatus/?find[created_at][$gte]=2025-08-27"
```

**Response:**
```json
[
  {
    "_id": "55cf81bc436037528ec75fa5",
    "device": "openaps://hostname",
    "created_at": "2025-08-27T12:00:00.000Z",
    "openaps": { ... },
    "pump": {
      "clock": "2025-08-27T12:00:00.000Z",
      "battery": { "status": "normal", "voltage": 1.5 },
      "reservoir": 150,
      "status": { "status": "normal", "bolusing": false, "suspended": false }
    },
    "uploader": { "battery": 85, "batteryVoltage": 4.1 }
  }
]
```

---

### POST `/devicestatus/`

Upload device status records.

**Permission:** `api:devicestatus:create`  
**Requires:** API enabled

```bash
curl -X POST https://YOUR-SITE/api/v1/devicestatus/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "device": "openaps://myrig",
    "created_at": "2025-08-27T12:00:00.000Z",
    "uploader": { "battery": 85 }
  }'
```

---

### DELETE `/devicestatus/:id`

Delete a device status record by ID.

**Permission:** `api:devicestatus:delete`  
**Requires:** API enabled

```bash
curl -X DELETE https://YOUR-SITE/api/v1/devicestatus/55cf81bc436037528ec75fa5 \
  -H "api-secret: <sha1-hash>"
```

#### Wildcard
```bash
curl -X DELETE "https://YOUR-SITE/api/v1/devicestatus/*" \
  -H "api-secret: <sha1-hash>"
```

---

### DELETE `/devicestatus/`

Delete device status records matching a query.

**Permission:** `api:devicestatus:delete`  
**Requires:** API enabled

```bash
curl -X DELETE -g "https://YOUR-SITE/api/v1/devicestatus/?find[created_at][$lte]=2025-01-01&count=50" \
  -H "api-secret: <sha1-hash>"
```

---

### GET `/profile/`

List profiles.

**Permission:** `api:profile:read`  
**Default count:** 10

```bash
curl https://YOUR-SITE/api/v1/profile/
curl "https://YOUR-SITE/api/v1/profile/?count=5"
```

---

### GET `/profiles/`

List profiles with full query parameter support.

**Permission:** `api:profile:read`  
**Default count:** 10

```bash
curl https://YOUR-SITE/api/v1/profiles/
curl "https://YOUR-SITE/api/v1/profiles/?count=20"
```

---

### GET `/profile/current`

Get the current active profile (last created profile).

**Permission:** `api:profile:read`

```bash
curl https://YOUR-SITE/api/v1/profile/current
```

**Response:** Single profile object or `null` if none exists.

---

### POST `/profile/`

Create a new profile.

**Permission:** `api:profile:create`  
**Requires:** API enabled

```bash
curl -X POST https://YOUR-SITE/api/v1/profile/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "defaultProfile": "Default",
    "store": {
      "Default": {
        "dia": 4,
        "carbratio": [{"time":"00:00","value":10}],
        "sens": [{"time":"00:00","value":50}],
        "basal": [{"time":"00:00","value":0.8}],
        "target_low": [{"time":"00:00","value":80}],
        "target_high": [{"time":"00:00","value":120}],
        "units": "mg/dl"
      }
    },
    "startDate": "2025-08-27T00:00:00.000Z"
  }'
```

---

### PUT `/profile/`

Update an existing profile.

**Permission:** `api:profile:update`  
**Requires:** API enabled

```bash
curl -X PUT https://YOUR-SITE/api/v1/profile/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{ "_id": "55cf81bc436037528ec75fa5", "defaultProfile": "Default", "store": { ... } }'
```

---

### DELETE `/profile/:_id`

Delete a profile by ID.

**Permission:** `api:profile:delete`  
**Requires:** API enabled

```bash
curl -X DELETE https://YOUR-SITE/api/v1/profile/55cf81bc436037528ec75fa5 \
  -H "api-secret: <sha1-hash>"
```

---

### GET `/food/`

List all food items.

**Permission:** `api:food:read`

```bash
curl https://YOUR-SITE/api/v1/food/
```

---

### GET `/food/quickpicks`

List food items marked as quick picks.

**Permission:** `api:food:read`

```bash
curl https://YOUR-SITE/api/v1/food/quickpicks
```

---

### GET `/food/regular`

List regular (non-quickpick) food items.

**Permission:** `api:food:read`

```bash
curl https://YOUR-SITE/api/v1/food/regular
```

---

### POST `/food/`

Create a new food item.

**Permission:** `api:food:create`  
**Requires:** API enabled

```bash
curl -X POST https://YOUR-SITE/api/v1/food/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Apple",
    "category": "Fruit",
    "carbs": 25,
    "gi": 2,
    "portion": 1,
    "unit": "medium"
  }'
```

---

### PUT `/food/`

Update a food item.

**Permission:** `api:food:update`  
**Requires:** API enabled

```bash
curl -X PUT https://YOUR-SITE/api/v1/food/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{ "_id": "55cf81bc436037528ec75fa5", "name": "Apple", "carbs": 30, ... }'
```

---

### DELETE `/food/:_id`

Delete a food item by ID.

**Permission:** `api:food:delete`  
**Requires:** API enabled

```bash
curl -X DELETE https://YOUR-SITE/api/v1/food/55cf81bc436037528ec75fa5 \
  -H "api-secret: <sha1-hash>"
```

---

### GET `/activity`

List activity records. Supports `If-Modified-Since`.

**Permission:** `api:activity:read`

```bash
curl https://YOUR-SITE/api/v1/activity
```

#### With If-Modified-Since
```bash
curl -H "If-Modified-Since: Thu, 27 Aug 2025 12:00:00 GMT" https://YOUR-SITE/api/v1/activity
```

---

### POST `/activity/`

Add new activity records.

**Permission:** `api:activity:create`  
**Requires:** API enabled + `careportal` enabled

```bash
curl -X POST https://YOUR-SITE/api/v1/activity/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "created_at": "2025-08-27T12:00:00.000Z",
    "steps": 5000,
    "heartrate": 72
  }'
```

#### Batch upload
```bash
curl -X POST https://YOUR-SITE/api/v1/activity/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '[
    {"created_at":"2025-08-27T12:00:00.000Z","steps":5000},
    {"created_at":"2025-08-27T13:00:00.000Z","steps":6200}
  ]'
```

---

### PUT `/activity/`

Update an activity record.

**Permission:** `api:activity:update`  
**Requires:** API enabled + `careportal` enabled

```bash
curl -X PUT https://YOUR-SITE/api/v1/activity/ \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{ "_id": "55cf81bc436037528ec75fa5", "steps": 5500 }'
```

---

### DELETE `/activity/:_id`

Delete an activity record by ID.

**Permission:** `api:activity:delete`  
**Requires:** API enabled + `careportal` enabled

```bash
curl -X DELETE https://YOUR-SITE/api/v1/activity/55cf81bc436037528ec75fa5 \
  -H "api-secret: <sha1-hash>"
```

---

### POST `/notifications/pushovercallback`

Pushover acknowledgement webhook callback. No authentication required.

```bash
curl -X POST https://YOUR-SITE/api/v1/notifications/pushovercallback \
  -H "Content-Type: application/json" \
  -d '{ "receipt": "...", "acknowledged": 1, "acknowledged_at": 1756339200 }'
```

**Responses:** `200 OK` on success, `500 Internal Server Error` on failure.

---

### GET `/notifications/ack`

Acknowledge a notification at a given level.

**Permission:** `notifications:*:ack`  
**Requires:** API enabled

| Query Parameter | Type | Description |
|-----------------|------|-------------|
| `level` | number | Notification level (2=urgent, 1=warn, 0=info, -1=low, -2=lowest) |
| `group` | string | Notification group (default: `"default"`) |
| `time` | number | Epoch timestamp of the notification |

```bash
curl -H "api-secret: <sha1-hash>" \
  "https://YOUR-SITE/api/v1/notifications/ack?level=2&group=default&time=1756339200000"
```

---

### GET `/experiments/test`

Authorization debug endpoint. Only available when API is enabled.

**Permission:** `authorization:debug:test`

```bash
curl -H "api-secret: <sha1-hash>" https://YOUR-SITE/api/v1/experiments/test
```

**Response:**
```json
{ "status": "ok" }
```

---

### POST `/alexa`

Amazon Alexa skill webhook endpoint. Handles `LaunchRequest`, `IntentRequest`, and `SessionEndedRequest`.

**Permission:** `api:*:read`  
**Requires:** Alexa context enabled on server

```bash
curl -X POST https://YOUR-SITE/api/v1/alexa \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "type": "IntentRequest",
      "locale": "en-US",
      "intent": {
        "name": "MetricNow",
        "slots": { "metric": { "value": "bg" } }
      }
    }
  }'
```

---

### POST `/googlehome`

Google Home / Dialogflow webhook endpoint.

**Permission:** `api:*:read`  
**Requires:** Google Home context enabled on server

```bash
curl -X POST https://YOUR-SITE/api/v1/googlehome \
  -H "api-secret: <sha1-hash>" \
  -H "Content-Type: application/json" \
  -d '{
    "queryResult": {
      "languageCode": "en",
      "intent": { "displayName": "MetricNow" },
      "parameters": { "metric": "bg" }
    }
  }'
```

---

### GET `/versions`

List all available API versions. No authentication required.

```bash
curl https://YOUR-SITE/api/versions
```

> [!IMPORTANT]
> This endpoint is mounted at `/api/versions`, **not** at `/api/v1/versions`.

**Response:**
```json
[
  { "version": "1.0.0", "url": "/api/v1" },
  { "version": "2.0.0", "url": "/api/v2" },
  { "version": "3.0.0", "url": "/api/v3" }
]
```

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `304` | Not Modified (conditional request via `If-Modified-Since`) |
| `400` | Bad Request |
| `401` | Unauthorized |
| `422` | Validation Error |
| `500` | Internal Server Error |

---

## Notes

- **Default counts:** Entries default to `10`, Treatments to `100` (or `1000` with `find`), Profiles to `10`, Device Status to `10`
- **Careportal gate:** Treatments, Activity POST/PUT/DELETE require the `careportal` feature to be enabled in server settings
- **Data caching:** GET endpoints for entries, treatments, and device status may serve from in-memory cache when the requested count fits within cached data
- **Date de-normalization:** If `deNormalizeDates` is enabled in settings, `dateString` and `created_at` fields will include UTC offset information
- **Device obscuring:** Entry responses pass through `wares.obscure_device` middleware which may redact device information
- **Body size limit:** POST bodies are limited to **50MB** for entries, treatments, and activity
