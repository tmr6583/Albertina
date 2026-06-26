-- Albertina: materialized views analiticas e estrategia de refresh

BEGIN;

CREATE TABLE IF NOT EXISTS olist_admin.mart_refresh_log (
  mart_refresh_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  view_name TEXT NOT NULL,
  refresh_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ NULL,
  duration_ms INTEGER NULL,
  details JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT mart_refresh_log_mode_check CHECK (refresh_mode IN ('standard', 'concurrent')),
  CONSTRAINT mart_refresh_log_status_check CHECK (status IN ('running', 'success', 'error'))
);

COMMENT ON TABLE olist_admin.mart_refresh_log IS 'Historico de refresh das materialized views analiticas.';

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_dim_contacts;
CREATE MATERIALIZED VIEW olist_mart.mv_dim_contacts AS
SELECT * FROM olist_mart.vw_dim_contacts
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_dim_products;
CREATE MATERIALIZED VIEW olist_mart.mv_dim_products AS
SELECT * FROM olist_mart.vw_dim_products
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_fact_orders;
CREATE MATERIALIZED VIEW olist_mart.mv_fact_orders AS
SELECT * FROM olist_mart.vw_fact_orders
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_fact_order_items;
CREATE MATERIALIZED VIEW olist_mart.mv_fact_order_items AS
SELECT * FROM olist_mart.vw_fact_order_items
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_fact_receivables;
CREATE MATERIALIZED VIEW olist_mart.mv_fact_receivables AS
SELECT * FROM olist_mart.vw_fact_receivables
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_fact_payables;
CREATE MATERIALIZED VIEW olist_mart.mv_fact_payables AS
SELECT * FROM olist_mart.vw_fact_payables
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_fact_inventory;
CREATE MATERIALIZED VIEW olist_mart.mv_fact_inventory AS
SELECT * FROM olist_mart.vw_fact_inventory
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_crm_pipeline;
CREATE MATERIALIZED VIEW olist_mart.mv_crm_pipeline AS
SELECT * FROM olist_mart.vw_crm_pipeline
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_dim_contacts
  ON olist_mart.mv_dim_contacts (tenant_id, contact_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_dim_products
  ON olist_mart.mv_dim_products (tenant_id, product_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fact_orders
  ON olist_mart.mv_fact_orders (tenant_id, order_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fact_order_items
  ON olist_mart.mv_fact_order_items (tenant_id, order_item_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fact_receivables
  ON olist_mart.mv_fact_receivables (tenant_id, ar_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fact_payables
  ON olist_mart.mv_fact_payables (tenant_id, ap_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fact_inventory
  ON olist_mart.mv_fact_inventory (tenant_id, stock_balance_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_crm_pipeline
  ON olist_mart.mv_crm_pipeline (tenant_id, crm_subject_id);

CREATE INDEX IF NOT EXISTS idx_mv_fact_orders_dates
  ON olist_mart.mv_fact_orders (tenant_id, order_date DESC, billing_date DESC);
CREATE INDEX IF NOT EXISTS idx_mv_fact_order_items_product
  ON olist_mart.mv_fact_order_items (tenant_id, product_id, order_date DESC);
CREATE INDEX IF NOT EXISTS idx_mv_fact_receivables_due
  ON olist_mart.mv_fact_receivables (tenant_id, due_date DESC, status);
CREATE INDEX IF NOT EXISTS idx_mv_fact_payables_due
  ON olist_mart.mv_fact_payables (tenant_id, due_date DESC, status);
CREATE INDEX IF NOT EXISTS idx_mv_fact_inventory_product
  ON olist_mart.mv_fact_inventory (tenant_id, product_id, deposit_id);
CREATE INDEX IF NOT EXISTS idx_mv_crm_pipeline_stage
  ON olist_mart.mv_crm_pipeline (tenant_id, stage_name, updated_at DESC);

CREATE OR REPLACE FUNCTION olist_admin.refresh_olist_mart_view(
  p_view_name TEXT,
  p_concurrently BOOLEAN DEFAULT FALSE
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_started_at TIMESTAMPTZ := clock_timestamp();
  v_log_id UUID;
  v_sql TEXT;
  v_refresh_mode TEXT := CASE WHEN p_concurrently THEN 'concurrent' ELSE 'standard' END;
BEGIN
  INSERT INTO olist_admin.mart_refresh_log (view_name, refresh_mode, status, started_at)
  VALUES (p_view_name, v_refresh_mode, 'running', v_started_at)
  RETURNING mart_refresh_log_id INTO v_log_id;

  IF p_concurrently THEN
    RAISE EXCEPTION
      'Refresh concorrente deve ser executado manualmente fora de funcao/transacao. Use REFRESH MATERIALIZED VIEW CONCURRENTLY diretamente.';
  END IF;

  CASE p_view_name
    WHEN 'mv_dim_contacts' THEN
      v_sql := 'REFRESH MATERIALIZED VIEW olist_mart.mv_dim_contacts';
    WHEN 'mv_dim_products' THEN
      v_sql := 'REFRESH MATERIALIZED VIEW olist_mart.mv_dim_products';
    WHEN 'mv_fact_orders' THEN
      v_sql := 'REFRESH MATERIALIZED VIEW olist_mart.mv_fact_orders';
    WHEN 'mv_fact_order_items' THEN
      v_sql := 'REFRESH MATERIALIZED VIEW olist_mart.mv_fact_order_items';
    WHEN 'mv_fact_receivables' THEN
      v_sql := 'REFRESH MATERIALIZED VIEW olist_mart.mv_fact_receivables';
    WHEN 'mv_fact_payables' THEN
      v_sql := 'REFRESH MATERIALIZED VIEW olist_mart.mv_fact_payables';
    WHEN 'mv_fact_inventory' THEN
      v_sql := 'REFRESH MATERIALIZED VIEW olist_mart.mv_fact_inventory';
    WHEN 'mv_crm_pipeline' THEN
      v_sql := 'REFRESH MATERIALIZED VIEW olist_mart.mv_crm_pipeline';
    ELSE
      RAISE EXCEPTION 'Materialized view nao suportada: %', p_view_name;
  END CASE;

  EXECUTE v_sql;

  UPDATE olist_admin.mart_refresh_log
  SET status = 'success',
      finished_at = clock_timestamp(),
      duration_ms = FLOOR(EXTRACT(EPOCH FROM (clock_timestamp() - v_started_at)) * 1000)::INTEGER,
      updated_at = NOW()
  WHERE mart_refresh_log_id = v_log_id;
EXCEPTION
  WHEN OTHERS THEN
    UPDATE olist_admin.mart_refresh_log
    SET status = 'error',
        finished_at = clock_timestamp(),
        duration_ms = FLOOR(EXTRACT(EPOCH FROM (clock_timestamp() - v_started_at)) * 1000)::INTEGER,
        details = jsonb_build_object('error', SQLERRM),
        updated_at = NOW()
    WHERE mart_refresh_log_id = v_log_id;
    RAISE;
END;
$$;

CREATE OR REPLACE FUNCTION olist_admin.refresh_olist_mart_views(
  p_concurrently BOOLEAN DEFAULT FALSE
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM olist_admin.refresh_olist_mart_view('mv_dim_contacts', p_concurrently);
  PERFORM olist_admin.refresh_olist_mart_view('mv_dim_products', p_concurrently);
  PERFORM olist_admin.refresh_olist_mart_view('mv_fact_orders', p_concurrently);
  PERFORM olist_admin.refresh_olist_mart_view('mv_fact_order_items', p_concurrently);
  PERFORM olist_admin.refresh_olist_mart_view('mv_fact_receivables', p_concurrently);
  PERFORM olist_admin.refresh_olist_mart_view('mv_fact_payables', p_concurrently);
  PERFORM olist_admin.refresh_olist_mart_view('mv_fact_inventory', p_concurrently);
  PERFORM olist_admin.refresh_olist_mart_view('mv_crm_pipeline', p_concurrently);
END;
$$;

DROP TRIGGER IF EXISTS trg_mart_refresh_log_updated_at ON olist_admin.mart_refresh_log;
CREATE TRIGGER trg_mart_refresh_log_updated_at
BEFORE UPDATE ON olist_admin.mart_refresh_log
FOR EACH ROW
EXECUTE FUNCTION olist_admin.set_row_updated_at();

ALTER TABLE olist_admin.mart_refresh_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mart_refresh_log_select_policy ON olist_admin.mart_refresh_log;
CREATE POLICY mart_refresh_log_select_policy
ON olist_admin.mart_refresh_log
FOR SELECT
USING (TRUE);

DROP POLICY IF EXISTS mart_refresh_log_write_policy ON olist_admin.mart_refresh_log;
CREATE POLICY mart_refresh_log_write_policy
ON olist_admin.mart_refresh_log
FOR ALL
USING (TRUE)
WITH CHECK (TRUE);

COMMENT ON FUNCTION olist_admin.refresh_olist_mart_view(TEXT, BOOLEAN) IS 'Refresh manual padrao de uma materialized view analitica. Para refresh concorrente, execute REFRESH MATERIALIZED VIEW CONCURRENTLY diretamente.';
COMMENT ON FUNCTION olist_admin.refresh_olist_mart_views(BOOLEAN) IS 'Refresh em lote padrao das materialized views analiticas do schema olist_mart. O modo concorrente deve ser executado manualmente, fora de funcao.';

COMMIT;
