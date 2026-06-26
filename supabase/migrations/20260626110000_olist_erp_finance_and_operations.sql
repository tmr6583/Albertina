-- Albertina: financeiro, CRM e operacoes de compra/servico da Olist ERP

BEGIN;

CREATE TABLE IF NOT EXISTS olist_core.revenue_expense_categories (
  category_fin_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_fin_category_id BIGINT NULL,
  category_name TEXT NOT NULL,
  category_kind TEXT NOT NULL,
  parent_category_fin_id UUID NULL REFERENCES olist_core.revenue_expense_categories(category_fin_id) ON DELETE SET NULL,
  parent_olist_fin_category_id BIGINT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_fin_category_id),
  CONSTRAINT revenue_expense_categories_kind_check CHECK (category_kind IN ('receita', 'despesa'))
);

CREATE TABLE IF NOT EXISTS olist_core.accounts_receivable (
  ar_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_ar_id BIGINT NOT NULL,
  order_id UUID NULL REFERENCES olist_core.orders(order_id) ON DELETE SET NULL,
  invoice_id UUID NULL REFERENCES olist_core.invoices(invoice_id) ON DELETE SET NULL,
  contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE SET NULL,
  revenue_category_id UUID NULL REFERENCES olist_core.revenue_expense_categories(category_fin_id) ON DELETE SET NULL,
  document_number TEXT NULL,
  status TEXT NULL,
  issue_date DATE NULL,
  due_date DATE NULL,
  competence_date DATE NULL,
  amount NUMERIC(18,4) NULL,
  open_amount NUMERIC(18,4) NULL,
  notes TEXT NULL,
  source_updated_at TIMESTAMPTZ NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_ar_id)
);

CREATE TABLE IF NOT EXISTS olist_core.accounts_receivable_receipts (
  ar_receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  ar_id UUID NOT NULL REFERENCES olist_core.accounts_receivable(ar_id) ON DELETE CASCADE,
  receipt_date DATE NULL,
  receipt_amount NUMERIC(18,4) NULL,
  receipt_method_id UUID NULL REFERENCES olist_core.receipt_methods(receipt_method_id) ON DELETE SET NULL,
  payment_method_id UUID NULL REFERENCES olist_core.payment_methods(payment_method_id) ON DELETE SET NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.accounts_receivable_markers (
  ar_marker_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  ar_id UUID NOT NULL REFERENCES olist_core.accounts_receivable(ar_id) ON DELETE CASCADE,
  marker_description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, ar_id, marker_description)
);

CREATE TABLE IF NOT EXISTS olist_core.accounts_payable (
  ap_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_ap_id BIGINT NOT NULL,
  purchase_order_id UUID NULL,
  contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE SET NULL,
  expense_category_id UUID NULL REFERENCES olist_core.revenue_expense_categories(category_fin_id) ON DELETE SET NULL,
  document_number TEXT NULL,
  status TEXT NULL,
  issue_date DATE NULL,
  due_date DATE NULL,
  competence_date DATE NULL,
  amount NUMERIC(18,4) NULL,
  open_amount NUMERIC(18,4) NULL,
  notes TEXT NULL,
  source_updated_at TIMESTAMPTZ NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_ap_id)
);

CREATE TABLE IF NOT EXISTS olist_core.accounts_payable_receipts (
  ap_receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  ap_id UUID NOT NULL REFERENCES olist_core.accounts_payable(ap_id) ON DELETE CASCADE,
  payment_date DATE NULL,
  payment_amount NUMERIC(18,4) NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.accounts_payable_markers (
  ap_marker_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  ap_id UUID NOT NULL REFERENCES olist_core.accounts_payable(ap_id) ON DELETE CASCADE,
  marker_description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, ap_id, marker_description)
);

CREATE TABLE IF NOT EXISTS olist_core.crm_stages (
  crm_stage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_crm_stage_id BIGINT NOT NULL,
  stage_name TEXT NOT NULL,
  pipeline_position INTEGER NULL,
  is_active BOOLEAN NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_crm_stage_id)
);

CREATE TABLE IF NOT EXISTS olist_core.crm_subjects (
  crm_subject_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_subject_id BIGINT NOT NULL,
  contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE SET NULL,
  crm_stage_id UUID NULL REFERENCES olist_core.crm_stages(crm_stage_id) ON DELETE SET NULL,
  subject_title TEXT NULL,
  subject_status TEXT NULL,
  is_archived BOOLEAN NOT NULL DEFAULT FALSE,
  is_starred BOOLEAN NOT NULL DEFAULT FALSE,
  source_updated_at TIMESTAMPTZ NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_subject_id)
);

CREATE TABLE IF NOT EXISTS olist_core.crm_actions (
  crm_action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  crm_subject_id UUID NOT NULL REFERENCES olist_core.crm_subjects(crm_subject_id) ON DELETE CASCADE,
  olist_action_id BIGINT NULL,
  action_type TEXT NULL,
  action_status TEXT NULL,
  scheduled_at TIMESTAMPTZ NULL,
  completed_at TIMESTAMPTZ NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_action_id)
);

CREATE TABLE IF NOT EXISTS olist_core.crm_notes (
  crm_note_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  crm_subject_id UUID NOT NULL REFERENCES olist_core.crm_subjects(crm_subject_id) ON DELETE CASCADE,
  olist_note_id BIGINT NULL,
  note_body TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_note_id)
);

CREATE TABLE IF NOT EXISTS olist_core.crm_markers (
  crm_marker_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  marker_description TEXT NOT NULL,
  color_hex TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, marker_description)
);

CREATE TABLE IF NOT EXISTS olist_core.crm_subject_markers (
  crm_subject_id UUID NOT NULL REFERENCES olist_core.crm_subjects(crm_subject_id) ON DELETE CASCADE,
  crm_marker_id UUID NOT NULL REFERENCES olist_core.crm_markers(crm_marker_id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (crm_subject_id, crm_marker_id)
);

CREATE TABLE IF NOT EXISTS olist_core.purchase_orders (
  purchase_order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_purchase_order_id BIGINT NOT NULL,
  supplier_contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE SET NULL,
  order_number TEXT NULL,
  status TEXT NULL,
  issue_date DATE NULL,
  expected_date DATE NULL,
  total_amount NUMERIC(18,4) NULL,
  notes TEXT NULL,
  source_updated_at TIMESTAMPTZ NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_purchase_order_id)
);

CREATE TABLE IF NOT EXISTS olist_core.purchase_order_items (
  purchase_order_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  purchase_order_id UUID NOT NULL REFERENCES olist_core.purchase_orders(purchase_order_id) ON DELETE CASCADE,
  product_id UUID NULL REFERENCES olist_core.products(product_id) ON DELETE SET NULL,
  quantity NUMERIC(18,4) NULL,
  unit_price NUMERIC(18,4) NULL,
  total_amount NUMERIC(18,4) NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.purchase_order_markers (
  purchase_order_marker_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  purchase_order_id UUID NOT NULL REFERENCES olist_core.purchase_orders(purchase_order_id) ON DELETE CASCADE,
  marker_description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, purchase_order_id, marker_description)
);

CREATE TABLE IF NOT EXISTS olist_core.service_orders (
  service_order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_service_order_id BIGINT NOT NULL,
  contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE SET NULL,
  order_number TEXT NULL,
  status TEXT NULL,
  issue_date DATE NULL,
  expected_date DATE NULL,
  total_amount NUMERIC(18,4) NULL,
  notes TEXT NULL,
  source_updated_at TIMESTAMPTZ NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_service_order_id)
);

CREATE TABLE IF NOT EXISTS olist_core.service_order_items (
  service_order_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  service_order_id UUID NOT NULL REFERENCES olist_core.service_orders(service_order_id) ON DELETE CASCADE,
  service_id UUID NULL REFERENCES olist_core.services(service_id) ON DELETE SET NULL,
  quantity NUMERIC(18,4) NULL,
  unit_price NUMERIC(18,4) NULL,
  total_amount NUMERIC(18,4) NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.service_order_markers (
  service_order_marker_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  service_order_id UUID NOT NULL REFERENCES olist_core.service_orders(service_order_id) ON DELETE CASCADE,
  marker_description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, service_order_id, marker_description)
);

COMMENT ON TABLE olist_core.accounts_receivable IS 'Titulos a receber gerados por vendas e faturamento.';
COMMENT ON TABLE olist_core.accounts_payable IS 'Obrigacoes financeiras a pagar para fornecedores e parceiros.';
COMMENT ON TABLE olist_core.crm_subjects IS 'Pipeline comercial e de relacionamento do modulo CRM.';
COMMENT ON TABLE olist_core.purchase_orders IS 'Cabecalho das ordens de compra da operacao.';
COMMENT ON TABLE olist_core.service_orders IS 'Cabecalho das ordens de servico da operacao.';

ALTER TABLE olist_core.accounts_payable
  ADD CONSTRAINT accounts_payable_purchase_order_fk
  FOREIGN KEY (purchase_order_id) REFERENCES olist_core.purchase_orders(purchase_order_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_fin_categories_lookup ON olist_core.revenue_expense_categories (tenant_id, category_kind, category_name);
CREATE INDEX IF NOT EXISTS idx_accounts_receivable_lookup ON olist_core.accounts_receivable (tenant_id, due_date, status);
CREATE INDEX IF NOT EXISTS idx_accounts_receivable_receipts_ar_id ON olist_core.accounts_receivable_receipts (tenant_id, ar_id);
CREATE INDEX IF NOT EXISTS idx_accounts_payable_lookup ON olist_core.accounts_payable (tenant_id, due_date, status);
CREATE INDEX IF NOT EXISTS idx_accounts_payable_receipts_ap_id ON olist_core.accounts_payable_receipts (tenant_id, ap_id);
CREATE INDEX IF NOT EXISTS idx_crm_subjects_lookup ON olist_core.crm_subjects (tenant_id, olist_subject_id, source_updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_crm_actions_subject_id ON olist_core.crm_actions (tenant_id, crm_subject_id);
CREATE INDEX IF NOT EXISTS idx_purchase_orders_lookup ON olist_core.purchase_orders (tenant_id, olist_purchase_order_id, expected_date DESC);
CREATE INDEX IF NOT EXISTS idx_service_orders_lookup ON olist_core.service_orders (tenant_id, olist_service_order_id, expected_date DESC);

DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'olist_core.revenue_expense_categories',
    'olist_core.accounts_receivable',
    'olist_core.accounts_receivable_receipts',
    'olist_core.accounts_receivable_markers',
    'olist_core.accounts_payable',
    'olist_core.accounts_payable_receipts',
    'olist_core.accounts_payable_markers',
    'olist_core.crm_stages',
    'olist_core.crm_subjects',
    'olist_core.crm_actions',
    'olist_core.crm_notes',
    'olist_core.crm_markers',
    'olist_core.crm_subject_markers',
    'olist_core.purchase_orders',
    'olist_core.purchase_order_items',
    'olist_core.purchase_order_markers',
    'olist_core.service_orders',
    'olist_core.service_order_items',
    'olist_core.service_order_markers'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %s', replace(split_part(tbl, '.', 2), '.', '_') || '_updated_at', tbl);
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION olist_admin.set_row_updated_at()', replace(split_part(tbl, '.', 2), '.', '_') || '_updated_at', tbl);
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %s', split_part(tbl, '.', 2) || '_select_policy', tbl);
    EXECUTE format('CREATE POLICY %I ON %s FOR SELECT USING (olist_admin.can_read_tenant(tenant_id))', split_part(tbl, '.', 2) || '_select_policy', tbl);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %s', split_part(tbl, '.', 2) || '_write_policy', tbl);
    EXECUTE format('CREATE POLICY %I ON %s FOR ALL USING (olist_admin.can_write_tenant(tenant_id)) WITH CHECK (olist_admin.can_write_tenant(tenant_id))', split_part(tbl, '.', 2) || '_write_policy', tbl);
  END LOOP;
END $$;

COMMIT;
