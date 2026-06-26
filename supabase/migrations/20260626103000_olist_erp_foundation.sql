-- Albertina: fundacao multi-tenant e ingestao do dominio Olist ERP
-- Banco alvo: PostgreSQL / Supabase

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS olist_admin;
CREATE SCHEMA IF NOT EXISTS olist_raw;
CREATE SCHEMA IF NOT EXISTS olist_core;
CREATE SCHEMA IF NOT EXISTS olist_mart;

CREATE OR REPLACE FUNCTION olist_admin.set_row_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION olist_admin.current_app_user_id()
RETURNS TEXT
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.current_user_id', true), '');
$$;

CREATE TABLE IF NOT EXISTS olist_admin.tenants (
  tenant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_code TEXT NOT NULL UNIQUE,
  tenant_name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  olist_account_id TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT tenants_status_check CHECK (status IN ('active', 'inactive'))
);

COMMENT ON TABLE olist_admin.tenants IS 'Contas logicas de segregacao para dados multi-tenant da Olist no projeto Albertina.';
COMMENT ON COLUMN olist_admin.tenants.tenant_code IS 'Codigo tecnico estavel do tenant.';
COMMENT ON COLUMN olist_admin.tenants.olist_account_id IS 'Identificador externo da conta Olist, quando conhecido.';

CREATE TABLE IF NOT EXISTS olist_admin.user_tenants (
  user_id TEXT NOT NULL,
  tenant_id UUID NOT NULL,
  role TEXT NOT NULL DEFAULT 'reader',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, tenant_id),
  CONSTRAINT user_tenants_user_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
  CONSTRAINT user_tenants_tenant_fk FOREIGN KEY (tenant_id) REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  CONSTRAINT user_tenants_role_check CHECK (role IN ('owner', 'admin', 'operator', 'reader'))
);

COMMENT ON TABLE olist_admin.user_tenants IS 'Vincula usuarios administrativos da Albertina aos tenants de dados Olist.';

CREATE OR REPLACE FUNCTION olist_admin.can_read_tenant(target_tenant_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM olist_admin.user_tenants ut
    WHERE ut.tenant_id = target_tenant_id
      AND ut.user_id = olist_admin.current_app_user_id()
  );
$$;

CREATE OR REPLACE FUNCTION olist_admin.can_write_tenant(target_tenant_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM olist_admin.user_tenants ut
    WHERE ut.tenant_id = target_tenant_id
      AND ut.user_id = olist_admin.current_app_user_id()
      AND ut.role IN ('owner', 'admin', 'operator')
  );
$$;

CREATE TABLE IF NOT EXISTS olist_admin.sync_runs (
  sync_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  entity_name TEXT NOT NULL,
  endpoint_path TEXT NOT NULL,
  http_method TEXT NOT NULL DEFAULT 'GET',
  sync_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ NULL,
  request_count INTEGER NOT NULL DEFAULT 0,
  success_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  watermark_from TIMESTAMPTZ NULL,
  watermark_to TIMESTAMPTZ NULL,
  details JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT sync_runs_mode_check CHECK (sync_mode IN ('full', 'incremental', 'webhook_replay', 'manual')),
  CONSTRAINT sync_runs_status_check CHECK (status IN ('running', 'success', 'partial', 'error', 'cancelled'))
);

COMMENT ON TABLE olist_admin.sync_runs IS 'Execucoes de extracao e sincronizacao por entidade da API Olist.';

CREATE TABLE IF NOT EXISTS olist_admin.sync_watermarks (
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  entity_name TEXT NOT NULL,
  endpoint_path TEXT NOT NULL,
  last_success_at TIMESTAMPTZ NULL,
  last_cursor JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, entity_name, endpoint_path)
);

COMMENT ON TABLE olist_admin.sync_watermarks IS 'Checkpoint de leitura incremental por entidade e endpoint.';

CREATE TABLE IF NOT EXISTS olist_raw.api_payloads (
  raw_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  entity_name TEXT NOT NULL,
  endpoint_path TEXT NOT NULL,
  http_method TEXT NOT NULL,
  olist_object_id BIGINT NULL,
  parent_olist_object_id BIGINT NULL,
  source_updated_at TIMESTAMPTZ NULL,
  extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sync_run_id UUID NULL REFERENCES olist_admin.sync_runs(sync_run_id) ON DELETE SET NULL,
  payload_hash TEXT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE olist_raw.api_payloads IS 'Camada raw com payloads integrais devolvidos pela API Olist.';
COMMENT ON COLUMN olist_raw.api_payloads.payload_hash IS 'Hash opcional para deduplicacao tecnica do payload bruto.';

CREATE TABLE IF NOT EXISTS olist_raw.webhook_events (
  webhook_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  delivery_status TEXT NOT NULL DEFAULT 'received',
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ NULL,
  retry_count INTEGER NOT NULL DEFAULT 0,
  payload JSONB NOT NULL,
  headers JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT webhook_events_status_check CHECK (delivery_status IN ('received', 'processed', 'ignored', 'error'))
);

COMMENT ON TABLE olist_raw.webhook_events IS 'Persistencia dos webhooks oficiais recebidos da Olist.';

CREATE INDEX IF NOT EXISTS idx_user_tenants_tenant_id ON olist_admin.user_tenants (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_lookup ON olist_admin.sync_runs (tenant_id, entity_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sync_watermarks_updated_at ON olist_admin.sync_watermarks (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_api_payloads_lookup ON olist_raw.api_payloads (tenant_id, entity_name, olist_object_id, extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_api_payloads_source_updated_at ON olist_raw.api_payloads (tenant_id, entity_name, source_updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_webhook_events_lookup ON olist_raw.webhook_events (tenant_id, event_type, received_at DESC);

DROP TRIGGER IF EXISTS trg_tenants_updated_at ON olist_admin.tenants;
CREATE TRIGGER trg_tenants_updated_at
BEFORE UPDATE ON olist_admin.tenants
FOR EACH ROW
EXECUTE FUNCTION olist_admin.set_row_updated_at();

DROP TRIGGER IF EXISTS trg_user_tenants_updated_at ON olist_admin.user_tenants;
CREATE TRIGGER trg_user_tenants_updated_at
BEFORE UPDATE ON olist_admin.user_tenants
FOR EACH ROW
EXECUTE FUNCTION olist_admin.set_row_updated_at();

DROP TRIGGER IF EXISTS trg_sync_runs_updated_at ON olist_admin.sync_runs;
CREATE TRIGGER trg_sync_runs_updated_at
BEFORE UPDATE ON olist_admin.sync_runs
FOR EACH ROW
EXECUTE FUNCTION olist_admin.set_row_updated_at();

DROP TRIGGER IF EXISTS trg_sync_watermarks_updated_at ON olist_admin.sync_watermarks;
CREATE TRIGGER trg_sync_watermarks_updated_at
BEFORE UPDATE ON olist_admin.sync_watermarks
FOR EACH ROW
EXECUTE FUNCTION olist_admin.set_row_updated_at();

DROP TRIGGER IF EXISTS trg_webhook_events_updated_at ON olist_raw.webhook_events;
CREATE TRIGGER trg_webhook_events_updated_at
BEFORE UPDATE ON olist_raw.webhook_events
FOR EACH ROW
EXECUTE FUNCTION olist_admin.set_row_updated_at();

ALTER TABLE olist_admin.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE olist_admin.user_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE olist_admin.sync_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE olist_admin.sync_watermarks ENABLE ROW LEVEL SECURITY;
ALTER TABLE olist_raw.api_payloads ENABLE ROW LEVEL SECURITY;
ALTER TABLE olist_raw.webhook_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenants_select_policy ON olist_admin.tenants;
CREATE POLICY tenants_select_policy
ON olist_admin.tenants
FOR SELECT
USING (olist_admin.can_read_tenant(tenant_id));

DROP POLICY IF EXISTS tenants_write_policy ON olist_admin.tenants;
CREATE POLICY tenants_write_policy
ON olist_admin.tenants
FOR ALL
USING (olist_admin.can_write_tenant(tenant_id))
WITH CHECK (olist_admin.can_write_tenant(tenant_id));

DROP POLICY IF EXISTS user_tenants_select_policy ON olist_admin.user_tenants;
CREATE POLICY user_tenants_select_policy
ON olist_admin.user_tenants
FOR SELECT
USING (olist_admin.can_read_tenant(tenant_id));

DROP POLICY IF EXISTS user_tenants_write_policy ON olist_admin.user_tenants;
CREATE POLICY user_tenants_write_policy
ON olist_admin.user_tenants
FOR ALL
USING (olist_admin.can_write_tenant(tenant_id))
WITH CHECK (olist_admin.can_write_tenant(tenant_id));

DROP POLICY IF EXISTS sync_runs_select_policy ON olist_admin.sync_runs;
CREATE POLICY sync_runs_select_policy
ON olist_admin.sync_runs
FOR SELECT
USING (olist_admin.can_read_tenant(tenant_id));

DROP POLICY IF EXISTS sync_runs_write_policy ON olist_admin.sync_runs;
CREATE POLICY sync_runs_write_policy
ON olist_admin.sync_runs
FOR ALL
USING (olist_admin.can_write_tenant(tenant_id))
WITH CHECK (olist_admin.can_write_tenant(tenant_id));

DROP POLICY IF EXISTS sync_watermarks_select_policy ON olist_admin.sync_watermarks;
CREATE POLICY sync_watermarks_select_policy
ON olist_admin.sync_watermarks
FOR SELECT
USING (olist_admin.can_read_tenant(tenant_id));

DROP POLICY IF EXISTS sync_watermarks_write_policy ON olist_admin.sync_watermarks;
CREATE POLICY sync_watermarks_write_policy
ON olist_admin.sync_watermarks
FOR ALL
USING (olist_admin.can_write_tenant(tenant_id))
WITH CHECK (olist_admin.can_write_tenant(tenant_id));

DROP POLICY IF EXISTS api_payloads_select_policy ON olist_raw.api_payloads;
CREATE POLICY api_payloads_select_policy
ON olist_raw.api_payloads
FOR SELECT
USING (olist_admin.can_read_tenant(tenant_id));

DROP POLICY IF EXISTS api_payloads_write_policy ON olist_raw.api_payloads;
CREATE POLICY api_payloads_write_policy
ON olist_raw.api_payloads
FOR ALL
USING (olist_admin.can_write_tenant(tenant_id))
WITH CHECK (olist_admin.can_write_tenant(tenant_id));

DROP POLICY IF EXISTS webhook_events_select_policy ON olist_raw.webhook_events;
CREATE POLICY webhook_events_select_policy
ON olist_raw.webhook_events
FOR SELECT
USING (olist_admin.can_read_tenant(tenant_id));

DROP POLICY IF EXISTS webhook_events_write_policy ON olist_raw.webhook_events;
CREATE POLICY webhook_events_write_policy
ON olist_raw.webhook_events
FOR ALL
USING (olist_admin.can_write_tenant(tenant_id))
WITH CHECK (olist_admin.can_write_tenant(tenant_id));

COMMIT;
