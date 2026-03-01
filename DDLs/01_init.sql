-- DDL for OneTwenty SaaS
-- Execute this in your database tool (e.g., DBeaver)

CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    tenant_uuid VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    plan VARCHAR(50) DEFAULT 'free'
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    tenant_id VARCHAR(255) REFERENCES tenants(tenant_uuid), -- Foreign key to tenant_uuid (assuming 1:1 for now or shared ID style)
    api_key VARCHAR(255) UNIQUE NOT NULL
);

-- Index for fast lookup by API Key
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);
