# Design Document: OneTwenty - Multi-Tenant CGM Management Platform

## 1. Executive Summary

OneTwenty is a multi-tenant SaaS platform providing unified continuous glucose monitoring (CGM) data management for Type 1 diabetics. Built from scratch (not a fork), it follows the Nightscout API protocol for compatibility while introducing modern multi-tenant architecture, AI-powered analysis, and comprehensive sharing features.

### Core Design Principles

1. **Multi-Tenant Architecture**: Isolated data spaces per patient with shared infrastructure
2. **Real-Time First**: WebSocket-based live updates with 1-3 minute sync intervals
3. **AI-Native**: Built-in AI for pattern analysis and natural language logging
4. **Zero Setup**: Cloud-hosted with instant account creation (vs. self-hosted Nightscout)

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
├─────────────┬──────────────┬──────────────┬────────────────────┤
│   PWA App   │   Widgets    │  Desk Clock  │  Voice Assistants  │
│  (Vite/JS)  │ (iOS/Android)│  (Hardware)  │  (Alexa/Google)    │
└─────────────┴──────────────┴──────────────┴────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                           │
│  • Subdomain Routing (slug.onetwenty.dev)                       │
│  • Authentication (JWT + API Secrets + Subdomain)                │
│  • Rate Limiting & CORS                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                Application Layer (FastAPI)                       │
│  Auth API  │  Entries API  │  Doctor API  │  WebSocket API      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              Service Layer (Business Logic)                      │
│  AuthService  │  EntriesService  │  DoctorService               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            Repository Layer (Data Access)                        │
│  UserRepo  │  TenantRepo  │  EntryRepo  │  DoctorRepo           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                  │
├──────────────────────────┬──────────────────────────────────────┤
│   PostgreSQL (Relational)│   MongoDB (Time-Series)              │
│   • Users & Auth         │   • Glucose Entries                  │
│   • Tenants & Settings   │   • Treatments                       │
│   • Doctor-Patient Links │   • Notes                            │
└──────────────────────────┴──────────────────────────────────────┘
```

### External Integrations

```
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
├──────────────┬──────────────┬──────────────┬───────────────────┤
│ CGM Uploaders│ Fitness APIs │  Voice APIs  │  AI/ML Services   │
│ • Libre      │ • Apple Fit  │ • Alexa      │ • OpenAI/Claude   │
│ • Dexcom     │ • Google Fit │ • Google Home│ • Pattern Analysis│
│ • Vitatok    │ • Strava     │              │                   │
└──────────────┴──────────────┴──────────────┴───────────────────┘
```

## 3. Database Design

### Entity Relationship Diagram

```
┌─────────────────┐
│     users       │
├─────────────────┤
│ id (PK)         │◄──┐
│ public_id (UK)  │   │
│ email (UK)      │   │
│ hashed_password │   │
│ role            │   │  ┌──────────────────┐
│ tier            │   │  │  doctor_patients │
└─────────────────┘   │  ├──────────────────┤
         │            └──┤ doctor_id (FK)   │
         │               │ patient_id (FK)  │
         │               │ granted_at       │
         │               └──────────────────┘
         ▼
┌─────────────────┐      ┌─────────────────┐
│  tenant_users   │      │     tenants     │
├─────────────────┤      ├─────────────────┤
│ user_id (FK)    │─────►│ id (PK)         │
│ tenant_id (FK)  │◄─────│ public_id (UK)  │
│ role            │      │ slug (UK)       │
└─────────────────┘      │ settings (JSON) │
                         └─────────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │    api_keys     │
                         ├─────────────────┤
                         │ tenant_id (FK)  │
                         │ key_value (UK)  │
                         │ is_active       │
                         └─────────────────┘
```

### Data Storage Strategy

**PostgreSQL**: Relational data requiring ACID transactions
- Users, authentication, tenants, API keys
- Doctor-patient relationships
- Tenant settings (JSONB)

**MongoDB**: High-throughput time-series data
- Glucose entries (1-5 minute intervals)
- Treatment logs (insulin, carbs, exercise)
- Indexed on `tenant_id` and `date` for fast range queries

## 4. Authentication Architecture

### Three Authentication Methods

```
┌─────────────────────────────────────────────────────────────────┐
│  1. JWT Authentication (Dashboard Users)                         │
│     Authorization: Bearer <token>                                │
│     • Used by: PWA app, doctor portal                           │
│     • Contains: user_id, tenant_id, role                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  2. API Secret Authentication (Uploaders)                        │
│     api-secret: ABC123XYZ_a1b2c3d4e5f6...                       │
│     • Used by: CGM uploaders, third-party integrations          │
│     • Format: 10-char prefix + 32-char secret                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  3. Subdomain Authentication (Public Read-Only)                  │
│     https://john-smith.onetwenty.dev/api/v1/entries             │
│     • Used by: Public widgets, desk clock, family members       │
│     • No credentials required for read operations               │
└─────────────────────────────────────────────────────────────────┘
```

### Role-Based Access Control (RBAC)

| Role          | Permissions                                      |
|---------------|--------------------------------------------------|
| **Patient**   | Full CRUD on own tenant, invite family, manage API keys |
| **Family**    | Read-only access to patient's data, receive alerts |
| **Doctor**    | Read-only access to assigned patients, multi-patient dashboard |
| **Admin**     | Platform administration, user management         |


## 5. Real-Time Data Flow

### CGM Data Upload & Broadcast

```
┌─────────────────────────────────────────────────────────────────┐
│  1. CGM Device → Manufacturer Cloud (Libre/Dexcom)              │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. OneTwenty Uploader polls API (every 5 min)                  │
│     • POST /api/v1/entries with API secret                      │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. Backend stores in MongoDB + broadcasts via WebSocket        │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. All connected clients receive update (tenant-scoped)        │
│     • PWA app (updates chart)                                   │
│     • Widgets (updates display)                                 │
│     • Family members (notifications if alert)                   │
└─────────────────────────────────────────────────────────────────┘
```

### WebSocket Architecture

- **Tenant-Scoped Connections**: Each WebSocket connection is tied to a specific tenant
- **Broadcast Manager**: Maintains connection pools per tenant, broadcasts only to relevant clients
- **Auto-Reconnection**: Clients automatically reconnect on disconnect with exponential backoff
- **Message Format**: JSON with `type` and `data` fields (e.g., `{type: "new_entry", data: {...}}`)

## 6. Key Design Decisions

### 6.1 Multi-Tenant vs. Single-Tenant

**Decision**: Multi-tenant architecture with logical data isolation

**Rationale**:
- **Cost**: Shared infrastructure vs. one server per patient
- **Scalability**: Horizontal scaling without per-tenant infrastructure
- **Onboarding**: Instant account creation vs. manual server provisioning
- **Operations**: Single deployment, centralized monitoring

**Implementation**:
- All queries filtered by `tenant_id` at repository layer
- MongoDB indexes on `tenant_id` for performance
- Subdomain routing for tenant identification

### 6.2 PostgreSQL + MongoDB Hybrid

**Decision**: Use both relational and document databases

**Rationale**:
- **PostgreSQL**: ACID transactions for auth, foreign key constraints, complex joins
- **MongoDB**: High write throughput for glucose entries (every 1-5 min)

**Trade-off**: Increased operational complexity, but optimized for each data type

### 6.3 FastAPI Framework

**Decision**: FastAPI over Flask/Django

**Rationale**:
- **Performance**: ASGI-based, async/await for WebSockets
- **Type Safety**: Pydantic models for validation
- **Auto-Documentation**: OpenAPI/Swagger UI
- **Modern**: Python 3.11+ features

### 6.4 Vanilla JavaScript PWA

**Decision**: Vanilla JS with Vite instead of React/Vue

**Rationale**:
- **Performance**: No framework overhead, faster load times
- **Bundle Size**: ~50KB vs. 200KB+ with frameworks
- **Simplicity**: Direct DOM manipulation

### 6.5 Subdomain-Based Tenancy

**Decision**: Each tenant gets unique subdomain (e.g., john-smith.onetwenty.dev)

**Rationale**:
- **Nightscout Compatibility**: Existing clients expect subdomain URLs
- **Branding**: Personalized URLs for patients
- **Public Sharing**: Easy read-only access without auth
- **SEO**: Unique URLs per tenant

## 7. Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Web Server**: Uvicorn (ASGI)
- **Authentication**: python-jose (JWT), passlib (bcrypt)
- **Databases**: PostgreSQL 15, MongoDB 6.0
- **WebSockets**: websockets 12.0
- **Validation**: Pydantic 2.0

### Frontend
- **Build Tool**: Vite 7.2
- **UI**: Vanilla JavaScript (ES6+)
- **Charting**: D3.js 7.9
- **Utilities**: Lodash, Moment.js
- **Storage**: LocalStorage, IndexedDB

### Infrastructure
- **Hosting**: AWS EC2 (Ubuntu/Amazon Linux)
- **Database**: AWS RDS (PostgreSQL), MongoDB Atlas
- **CDN**: CloudFlare
- **Monitoring**: Prometheus + Grafana
- **CI/CD**: GitHub Actions

### Future Additions
- **AI/ML**: OpenAI API, LangChain
- **Voice**: Alexa Skills Kit, Google Actions SDK
- **Mobile**: React Native or Flutter
- **Hardware**: ESP32 firmware (Arduino)

## 8. Scalability Strategy

### Horizontal Scaling

```
┌─────────────────────────────────────────────────────────────────┐
│                      Load Balancer                               │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  API Server  │    │  API Server  │    │  API Server  │
│  Instance 1  │    │  Instance 2  │    │  Instance 3  │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  Shared Data Layer    │
                │  • PostgreSQL         │
                │  • MongoDB            │
                │  • Redis Cache        │
                └───────────────────────┘
```

### Performance Optimizations

- **Database Indexes**: Compound indexes on `tenant_id` + `date` for fast queries
- **Caching**: Redis for tenant settings, API key lookups (5-min TTL)
- **Connection Pooling**: 10-20 DB connections per API instance
- **CDN**: Static assets served via CloudFlare edge network

### Performance Targets

| Metric                          | Target          |
|---------------------------------|-----------------|
| API Response Time (p95)         | < 200ms         |
| WebSocket Message Latency       | < 500ms         |
| Database Query Time (p95)       | < 50ms          |
| PWA Load Time (3G)              | < 3s            |
| Concurrent WebSocket Connections| 10,000+         |

## 9. Security Design

### Data Protection

- **Passwords**: bcrypt (cost factor 12)
- **API Secrets**: SHA1
- **Data in Transit**: TLS 1.3
- **Database Backups**: AES-256 encryption

### Audit Logging

All sensitive operations logged:
- Authentication attempts (success/failure)
- Doctor-patient access grants/revokes
- API key creation/rotation
- Data exports

### Rate Limiting

```python
RATE_LIMITS = {
    'entries_read': '1000/hour',
    'entries_write': '500/hour',
    'auth': '10/minute',
    'websocket': '100 concurrent connections per tenant'
}
```

## 10. AI/ML Features (Future)

### Pattern Analysis Engine

```
User Query → AI Service → Data Analysis → Response Generation
    ↓            ↓              ↓                ↓
"Why am I    Query         Calculate        "Your glucose
high in the  Understanding  statistics,      rises 40 mg/dL
morning?"    (LLM)         detect patterns   between 3-6am
                           (Time-Series)     (dawn phenomenon)"
```

**Capabilities**:
- Dawn phenomenon detection
- Post-meal spike analysis
- Overnight stability scoring
- Insulin-to-carb ratio optimization

### Agentic AI Logging

```
User Input:
"Had breakfast at 8am with toast, took 6 units. 
Went for a run at 10am. Lunch was pasta at 1pm, 8 units."

                    ↓
        Entity Extraction (NER)
                    ↓
        Timestamp Inference
                    ↓
    Treatment Entry Generation
                    ↓
        User Confirmation UI
```

### Voice Assistant Integration

- **Alexa**: "Alexa, ask OneTwenty what's my glucose?"
- **Google Home**: "Hey Google, log 5 units of insulin"
- **Siri Shortcuts**: "Log carbs" → Quick entry form

## 11. Hardware Integration: Desk Clock

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  ESP32 Microcontroller + E-Ink Display                          │
│  • Connects to WiFi                                             │
│  • Polls /api/v1/entries/current every 3 minutes                │
│  • Displays: Glucose value + Trend arrow + Time                 │
│  • Color-coded: Green (in range), Yellow (high), Red (low)     │
└─────────────────────────────────────────────────────────────────┘
```

**Communication**: REST API with API secret authentication  
**Power**: USB-C or battery (18650 Li-ion)  
**Display**: E-Ink (low power, always visible)

## 12. Deployment Architecture

### Production Environment

```
┌─────────────────────────────────────────────────────────────────┐
│  CloudFlare CDN (Global Edge Network)                           │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  AWS Application Load Balancer (ALB)                            │
│  • SSL Termination                                              │
│  • Health Checks                                                │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  AWS EC2 Auto Scaling Group                                     │
│  • 2-5 instances (t3.medium)                                    │
│  • Auto-scaling: CPU > 70% → add instance                       │
│  • FastAPI + Uvicorn                                            │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Databases                                                       │
│  • PostgreSQL: AWS RDS (db.t3.medium, Multi-AZ)                 │
│  • MongoDB: MongoDB Atlas (M10, 3-node replica set)             │
│  • Redis: AWS ElastiCache (cache.t3.micro)                      │
└─────────────────────────────────────────────────────────────────┘
```

### CI/CD Pipeline

```
GitHub Push → GitHub Actions → Tests → Build Docker Image → 
Deploy to EC2 → Health Check → Route Traffic
```

## 13. Cost Estimation

### Infrastructure (Monthly)

| Service                  | Cost (INR)  |
|--------------------------|-------------|
| AWS EC2 (2x t3.medium)   | ₹5,000      |
| AWS RDS PostgreSQL       | ₹6,250      |
| MongoDB Atlas (M10)      | ₹5,000      |
| AWS ElastiCache Redis    | ₹1,250      |
| AWS ALB                  | ₹1,650      |
| CloudFlare CDN           | ₹1,650      |
| Monitoring               | ₹2,500      |
| **Total**                | **₹23,300** |

### Revenue Model

**Single Flat Subscription**: ₹200-250 per year

**All Features Included**:
- Unlimited CGM brands
- Unlimited data retention
- Real-time monitoring & alerts
- Family sharing (unlimited members)
- Doctor portal access
- AI-powered analysis (when available)
- Voice assistant integration (when available)
- Hardware integrations (desk clock)
- Medical records storage
- Data export (CSV, JSON, PDF)

### Financial Projections (100-150 Users)

| Metric                    | Value              |
|---------------------------|--------------------|
| Target Users              | 100-150            |
| Subscription Price        | ₹225/year (avg)    |
| **Annual Revenue**        | **₹22,500-33,750** |
| Monthly Infrastructure    | ₹23,300            |
| **Annual Infrastructure** | **₹2,79,600**      |
| **Break-even Users**      | ~1,250 users       |

**Note**: Initial phase focuses on user acquisition and product validation. Revenue model designed for affordability in Indian market while building user base for future sustainability.

## 14. Roadmap

### Phase 1: MVP (Current)
- ✅ Multi-tenant backend (FastAPI + PostgreSQL + MongoDB)
- ✅ PWA with real-time updates (WebSocket)
- ✅ Doctor portal (multi-patient dashboard)
- ✅ API secret management
- ✅ Subdomain-based tenancy

### Phase 2: AI Features (3-6 months)
- [ ] Pattern analysis engine
- [ ] Agentic AI logging
- [ ] Voice assistant integration
- [ ] Predictive glucose alerts

### Phase 3: Mobile & Hardware (6-12 months)
- [ ] Native mobile apps (iOS/Android)
- [ ] Blood glucose desk clock
- [ ] Apple Watch complications
- [ ] Android Wear OS app

### Phase 4: Integrations (12+ months)
- [ ] Fitness app integrations
- [ ] Insulin pump integrations
- [ ] Medical records storage
- [ ] Telemedicine integration

---

**Document Version**: 1.0  
**Last Updated**: February 14, 2026  
**Status**: Ready for Hackathon Presentation
