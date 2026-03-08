-- Migration: Add tenant_id to clock_configs (Phase 6)
-- Links each clock record to a tenant for ownership enforcement.

ALTER TABLE clock_configs
    ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_clock_configs_tenant_id ON clock_configs(tenant_id);
