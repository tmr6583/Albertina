-- Albertina: vendas, faturamento e logistica da Olist ERP

BEGIN;

CREATE TABLE IF NOT EXISTS olist_core.operation_natures (
  operation_nature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_operation_nature_id BIGINT NULL,
  operation_nature_name TEXT NOT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, operation_nature_name),
  UNIQUE (tenant_id, olist_operation_nature_id)
);

CREATE TABLE IF NOT EXISTS olist_core.orders (
  order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_order_id BIGINT NOT NULL,
  order_number BIGINT NULL,
  order_status INTEGER NULL,
  order_origin INTEGER NULL,
  olist_invoice_id BIGINT NULL,
  contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE SET NULL,
  vendor_id UUID NULL REFERENCES olist_core.vendors(vendor_id) ON DELETE SET NULL,
  deposit_id UUID NULL REFERENCES olist_core.deposits(deposit_id) ON DELETE SET NULL,
  price_list_id UUID NULL REFERENCES olist_core.price_lists(price_list_id) ON DELETE SET NULL,
  intermediator_id UUID NULL REFERENCES olist_core.intermediators(intermediator_id) ON DELETE SET NULL,
  operation_nature_id UUID NULL REFERENCES olist_core.operation_natures(operation_nature_id) ON DELETE SET NULL,
  billing_address_id UUID NULL REFERENCES olist_core.addresses(address_id) ON DELETE SET NULL,
  shipping_address_id UUID NULL REFERENCES olist_core.addresses(address_id) ON DELETE SET NULL,
  external_order_number TEXT NULL,
  sales_channel_order_number TEXT NULL,
  sales_channel_name TEXT NULL,
  ecommerce_name TEXT NULL,
  order_date DATE NULL,
  delivery_date DATE NULL,
  billing_date TIMESTAMPTZ NULL,
  expected_date DATE NULL,
  shipped_at TIMESTAMPTZ NULL,
  purchase_order_number TEXT NULL,
  total_products_amount NUMERIC(18,4) NULL,
  total_order_amount NUMERIC(18,4) NULL,
  discount_amount NUMERIC(18,4) NULL,
  freight_amount NUMERIC(18,4) NULL,
  other_expenses_amount NUMERIC(18,4) NULL,
  notes TEXT NULL,
  internal_notes TEXT NULL,
  is_consumer_final BOOLEAN NOT NULL DEFAULT FALSE,
  consumer_final_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_updated_at TIMESTAMPTZ NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_order_id),
  CONSTRAINT orders_origin_check CHECK (order_origin IN (0, 1) OR order_origin IS NULL)
);

CREATE TABLE IF NOT EXISTS olist_core.order_items (
  order_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  order_id UUID NOT NULL REFERENCES olist_core.orders(order_id) ON DELETE CASCADE,
  line_number INTEGER NULL,
  product_id UUID NULL REFERENCES olist_core.products(product_id) ON DELETE SET NULL,
  service_id UUID NULL REFERENCES olist_core.services(service_id) ON DELETE SET NULL,
  olist_product_id BIGINT NULL,
  product_name_snapshot TEXT NULL,
  quantity NUMERIC(18,4) NOT NULL,
  unit_price NUMERIC(18,4) NOT NULL,
  total_amount NUMERIC(18,4) GENERATED ALWAYS AS (quantity * unit_price) STORED,
  additional_info TEXT NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.order_markers (
  order_marker_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  order_id UUID NOT NULL REFERENCES olist_core.orders(order_id) ON DELETE CASCADE,
  marker_description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, order_id, marker_description)
);

CREATE TABLE IF NOT EXISTS olist_core.order_installments (
  installment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  order_id UUID NOT NULL REFERENCES olist_core.orders(order_id) ON DELETE CASCADE,
  installment_number INTEGER NULL,
  term_days INTEGER NULL,
  due_date DATE NULL,
  installment_amount NUMERIC(18,4) NOT NULL,
  observations TEXT NULL,
  receipt_method_id UUID NULL REFERENCES olist_core.receipt_methods(receipt_method_id) ON DELETE SET NULL,
  payment_method_id UUID NULL REFERENCES olist_core.payment_methods(payment_method_id) ON DELETE SET NULL,
  olist_receipt_method_id BIGINT NULL,
  olist_payment_method_id BIGINT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.order_integrated_payments (
  integrated_payment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  order_id UUID NOT NULL REFERENCES olist_core.orders(order_id) ON DELETE CASCADE,
  payment_type INTEGER NULL,
  payment_amount NUMERIC(18,4) NULL,
  intermediator_cnpj TEXT NULL,
  authorization_code TEXT NULL,
  flag_code INTEGER NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.order_shipping (
  order_shipping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  order_id UUID NOT NULL REFERENCES olist_core.orders(order_id) ON DELETE CASCADE,
  carrier_contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE SET NULL,
  carrier_address_id UUID NULL REFERENCES olist_core.addresses(address_id) ON DELETE SET NULL,
  freight_account_code TEXT NULL,
  shipping_method_id UUID NULL REFERENCES olist_core.shipping_methods(shipping_method_id) ON DELETE SET NULL,
  freight_method_id UUID NULL REFERENCES olist_core.freight_methods(freight_method_id) ON DELETE SET NULL,
  olist_shipping_method_id BIGINT NULL,
  olist_freight_method_id BIGINT NULL,
  tracking_code TEXT NULL,
  tracking_url TEXT NULL,
  company_paid_freight NUMERIC(18,4) NULL,
  predicted_date DATE NULL,
  volumes INTEGER NULL,
  gross_weight NUMERIC(18,4) NULL,
  net_weight NUMERIC(18,4) NULL,
  shipping_notes TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, order_id)
);

CREATE TABLE IF NOT EXISTS olist_core.order_operations (
  order_operation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  order_id UUID NOT NULL REFERENCES olist_core.orders(order_id) ON DELETE CASCADE,
  operation_name TEXT NOT NULL,
  operation_status TEXT NOT NULL DEFAULT 'pending',
  executed_at TIMESTAMPTZ NULL,
  details JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT order_operations_name_check CHECK (
    operation_name IN (
      'lancar_contas',
      'estornar_contas',
      'lancar_estoque',
      'estornar_estoque',
      'gerar_nota_fiscal',
      'gerar_ordem_producao',
      'atualizar_situacao',
      'atualizar_itens',
      'atualizar_despacho'
    )
  ),
  CONSTRAINT order_operations_status_check CHECK (operation_status IN ('pending', 'success', 'error'))
);

CREATE TABLE IF NOT EXISTS olist_core.shipment_groups (
  shipment_group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_shipment_group_id BIGINT NOT NULL,
  group_name TEXT NULL,
  status TEXT NULL,
  concluded_at TIMESTAMPTZ NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_shipment_group_id)
);

CREATE TABLE IF NOT EXISTS olist_core.shipments (
  shipment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_shipment_id BIGINT NOT NULL,
  shipment_group_id UUID NULL REFERENCES olist_core.shipment_groups(shipment_group_id) ON DELETE SET NULL,
  order_id UUID NULL REFERENCES olist_core.orders(order_id) ON DELETE SET NULL,
  status TEXT NULL,
  shipping_method_id UUID NULL REFERENCES olist_core.shipping_methods(shipping_method_id) ON DELETE SET NULL,
  freight_method_id UUID NULL REFERENCES olist_core.freight_methods(freight_method_id) ON DELETE SET NULL,
  tracking_code TEXT NULL,
  tracking_url TEXT NULL,
  shipped_at TIMESTAMPTZ NULL,
  delivered_at TIMESTAMPTZ NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_shipment_id)
);

CREATE TABLE IF NOT EXISTS olist_core.separations (
  separation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_separation_id BIGINT NOT NULL,
  order_id UUID NULL REFERENCES olist_core.orders(order_id) ON DELETE SET NULL,
  document_number TEXT NULL,
  status TEXT NULL,
  origin_type TEXT NULL,
  issued_at TIMESTAMPTZ NULL,
  packed_by_olist_user_id BIGINT NULL,
  packed_by_user_id UUID NULL REFERENCES olist_core.olist_users(olist_user_pk) ON DELETE SET NULL,
  freight_method_id UUID NULL REFERENCES olist_core.freight_methods(freight_method_id) ON DELETE SET NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_separation_id)
);

CREATE TABLE IF NOT EXISTS olist_core.separation_items (
  separation_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  separation_id UUID NOT NULL REFERENCES olist_core.separations(separation_id) ON DELETE CASCADE,
  order_item_id UUID NULL REFERENCES olist_core.order_items(order_item_id) ON DELETE SET NULL,
  product_id UUID NULL REFERENCES olist_core.products(product_id) ON DELETE SET NULL,
  quantity NUMERIC(18,4) NULL,
  status TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.invoices (
  invoice_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_invoice_id BIGINT NOT NULL,
  order_id UUID NULL REFERENCES olist_core.orders(order_id) ON DELETE SET NULL,
  contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE SET NULL,
  invoice_number TEXT NULL,
  invoice_series TEXT NULL,
  invoice_status TEXT NULL,
  invoice_type TEXT NULL,
  access_key TEXT NULL,
  issued_at TIMESTAMPTZ NULL,
  authorized_at TIMESTAMPTZ NULL,
  cancelled_at TIMESTAMPTZ NULL,
  tracking_code TEXT NULL,
  tracking_url TEXT NULL,
  xml_url TEXT NULL,
  danfe_url TEXT NULL,
  total_amount NUMERIC(18,4) NULL,
  source_updated_at TIMESTAMPTZ NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_invoice_id)
);

CREATE TABLE IF NOT EXISTS olist_core.invoice_items (
  invoice_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  invoice_id UUID NOT NULL REFERENCES olist_core.invoices(invoice_id) ON DELETE CASCADE,
  order_item_id UUID NULL REFERENCES olist_core.order_items(order_item_id) ON DELETE SET NULL,
  product_id UUID NULL REFERENCES olist_core.products(product_id) ON DELETE SET NULL,
  service_id UUID NULL REFERENCES olist_core.services(service_id) ON DELETE SET NULL,
  quantity NUMERIC(18,4) NULL,
  unit_price NUMERIC(18,4) NULL,
  total_amount NUMERIC(18,4) NULL,
  tax_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS olist_core.invoice_markers (
  invoice_marker_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  invoice_id UUID NOT NULL REFERENCES olist_core.invoices(invoice_id) ON DELETE CASCADE,
  marker_description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, invoice_id, marker_description)
);

COMMENT ON TABLE olist_core.orders IS 'Entidade central de venda na API Olist ERP, derivada do modulo de pedidos.';
COMMENT ON TABLE olist_core.order_installments IS 'Parcelas e condicoes de recebimento extraidas do pagamento do pedido.';
COMMENT ON TABLE olist_core.invoices IS 'Cabecalho fiscal vinculado a pedidos, expedicao e rastreio.';

CREATE INDEX IF NOT EXISTS idx_operation_natures_lookup ON olist_core.operation_natures (tenant_id, operation_nature_name);
CREATE INDEX IF NOT EXISTS idx_orders_lookup ON olist_core.orders (tenant_id, olist_order_id, source_updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_business_dates ON olist_core.orders (tenant_id, order_date DESC, billing_date DESC);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON olist_core.order_items (tenant_id, order_id);
CREATE INDEX IF NOT EXISTS idx_order_installments_order_id ON olist_core.order_installments (tenant_id, order_id);
CREATE INDEX IF NOT EXISTS idx_order_integrated_payments_order_id ON olist_core.order_integrated_payments (tenant_id, order_id);
CREATE INDEX IF NOT EXISTS idx_order_shipping_order_id ON olist_core.order_shipping (tenant_id, order_id);
CREATE INDEX IF NOT EXISTS idx_order_operations_lookup ON olist_core.order_operations (tenant_id, order_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shipments_lookup ON olist_core.shipments (tenant_id, olist_shipment_id, shipped_at DESC);
CREATE INDEX IF NOT EXISTS idx_separations_lookup ON olist_core.separations (tenant_id, olist_separation_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_lookup ON olist_core.invoices (tenant_id, olist_invoice_id, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON olist_core.invoice_items (tenant_id, invoice_id);

DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'olist_core.operation_natures',
    'olist_core.orders',
    'olist_core.order_items',
    'olist_core.order_markers',
    'olist_core.order_installments',
    'olist_core.order_integrated_payments',
    'olist_core.order_shipping',
    'olist_core.order_operations',
    'olist_core.shipment_groups',
    'olist_core.shipments',
    'olist_core.separations',
    'olist_core.separation_items',
    'olist_core.invoices',
    'olist_core.invoice_items',
    'olist_core.invoice_markers'
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
