-- Albertina: dominios mestres e cadastros da Olist ERP

BEGIN;

CREATE TABLE IF NOT EXISTS olist_core.companies (
  company_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_company_id BIGINT NULL,
  legal_name TEXT NULL,
  trade_name TEXT NULL,
  cnpj TEXT NULL,
  state_registration TEXT NULL,
  company_type TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_company_id)
);

CREATE TABLE IF NOT EXISTS olist_core.olist_users (
  olist_user_pk UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_user_id BIGINT NOT NULL,
  user_name TEXT NULL,
  user_type TEXT NULL,
  email TEXT NULL,
  status TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_user_id)
);

CREATE TABLE IF NOT EXISTS olist_core.vendors (
  vendor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_vendor_id BIGINT NOT NULL,
  vendor_name TEXT NULL,
  vendor_code TEXT NULL,
  email TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_vendor_id)
);

CREATE TABLE IF NOT EXISTS olist_core.contact_types (
  contact_type_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_contact_type_id BIGINT NULL,
  type_name TEXT NOT NULL,
  is_active BOOLEAN NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, type_name),
  UNIQUE (tenant_id, olist_contact_type_id)
);

CREATE TABLE IF NOT EXISTS olist_core.contacts (
  contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_contact_id BIGINT NOT NULL,
  contact_code TEXT NULL,
  contact_name TEXT NULL,
  trade_name TEXT NULL,
  person_type TEXT NULL,
  cpf_cnpj TEXT NULL,
  state_registration TEXT NULL,
  rg TEXT NULL,
  phone TEXT NULL,
  mobile TEXT NULL,
  email TEXT NULL,
  crm_status TEXT NULL,
  vendor_id UUID NULL REFERENCES olist_core.vendors(vendor_id) ON DELETE SET NULL,
  contact_type_id UUID NULL REFERENCES olist_core.contact_types(contact_type_id) ON DELETE SET NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_contact_id)
);

CREATE TABLE IF NOT EXISTS olist_core.contact_people (
  contact_person_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  contact_id UUID NOT NULL REFERENCES olist_core.contacts(contact_id) ON DELETE CASCADE,
  olist_contact_person_id BIGINT NULL,
  person_name TEXT NULL,
  role_name TEXT NULL,
  email TEXT NULL,
  phone TEXT NULL,
  mobile TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_contact_person_id)
);

CREATE TABLE IF NOT EXISTS olist_core.addresses (
  address_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  contact_id UUID NULL REFERENCES olist_core.contacts(contact_id) ON DELETE CASCADE,
  address_role TEXT NOT NULL,
  recipient_name TEXT NULL,
  person_type TEXT NULL,
  cpf_cnpj TEXT NULL,
  state_registration TEXT NULL,
  phone TEXT NULL,
  street TEXT NULL,
  street_number TEXT NULL,
  complement TEXT NULL,
  district TEXT NULL,
  city TEXT NULL,
  state TEXT NULL,
  zip_code TEXT NULL,
  country TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT addresses_role_check CHECK (address_role IN ('principal', 'entrega', 'cobranca', 'transportadora', 'outro'))
);

CREATE TABLE IF NOT EXISTS olist_core.categories (
  category_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_category_id BIGINT NOT NULL,
  parent_category_id UUID NULL REFERENCES olist_core.categories(category_id) ON DELETE SET NULL,
  parent_olist_category_id BIGINT NULL,
  category_name TEXT NOT NULL,
  tree_level INTEGER NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_category_id)
);

CREATE TABLE IF NOT EXISTS olist_core.brands (
  brand_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_brand_id BIGINT NOT NULL,
  brand_name TEXT NOT NULL,
  is_active BOOLEAN NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_brand_id)
);

CREATE TABLE IF NOT EXISTS olist_core.tag_groups (
  tag_group_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_tag_group_id BIGINT NOT NULL,
  group_name TEXT NOT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_tag_group_id)
);

CREATE TABLE IF NOT EXISTS olist_core.product_tags (
  product_tag_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_product_tag_id BIGINT NOT NULL,
  tag_group_id UUID NULL REFERENCES olist_core.tag_groups(tag_group_id) ON DELETE SET NULL,
  tag_name TEXT NOT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_product_tag_id)
);

CREATE TABLE IF NOT EXISTS olist_core.products (
  product_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_product_id BIGINT NOT NULL,
  product_code TEXT NULL,
  product_name TEXT NOT NULL,
  sku TEXT NULL,
  gtin TEXT NULL,
  product_type TEXT NULL,
  category_id UUID NULL REFERENCES olist_core.categories(category_id) ON DELETE SET NULL,
  brand_id UUID NULL REFERENCES olist_core.brands(brand_id) ON DELETE SET NULL,
  is_active BOOLEAN NULL,
  source_updated_at TIMESTAMPTZ NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_product_id)
);

CREATE TABLE IF NOT EXISTS olist_core.product_variants (
  product_variant_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES olist_core.products(product_id) ON DELETE CASCADE,
  olist_variant_id BIGINT NULL,
  variant_code TEXT NULL,
  variant_name TEXT NULL,
  gtin TEXT NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_variant_id)
);

CREATE TABLE IF NOT EXISTS olist_core.product_tag_links (
  product_id UUID NOT NULL REFERENCES olist_core.products(product_id) ON DELETE CASCADE,
  product_tag_id UUID NOT NULL REFERENCES olist_core.product_tags(product_tag_id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (product_id, product_tag_id)
);

CREATE TABLE IF NOT EXISTS olist_core.services (
  service_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_service_id BIGINT NOT NULL,
  service_code TEXT NULL,
  service_name TEXT NOT NULL,
  is_active BOOLEAN NULL,
  raw_attributes JSONB NOT NULL DEFAULT '{}'::JSONB,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_service_id)
);

CREATE TABLE IF NOT EXISTS olist_core.price_lists (
  price_list_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_price_list_id BIGINT NOT NULL,
  price_list_name TEXT NOT NULL,
  adjustment_value NUMERIC(18,4) NULL,
  is_active BOOLEAN NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_price_list_id)
);

CREATE TABLE IF NOT EXISTS olist_core.price_list_items (
  price_list_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  price_list_id UUID NOT NULL REFERENCES olist_core.price_lists(price_list_id) ON DELETE CASCADE,
  product_id UUID NULL REFERENCES olist_core.products(product_id) ON DELETE SET NULL,
  olist_product_id BIGINT NULL,
  unit_price NUMERIC(18,4) NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, price_list_id, olist_product_id)
);

CREATE TABLE IF NOT EXISTS olist_core.payment_methods (
  payment_method_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_payment_method_id BIGINT NOT NULL,
  payment_method_name TEXT NOT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_payment_method_id)
);

CREATE TABLE IF NOT EXISTS olist_core.receipt_methods (
  receipt_method_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_receipt_method_id BIGINT NOT NULL,
  receipt_method_name TEXT NOT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_receipt_method_id)
);

CREATE TABLE IF NOT EXISTS olist_core.shipping_methods (
  shipping_method_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_shipping_method_id BIGINT NOT NULL,
  shipping_method_name TEXT NOT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_shipping_method_id)
);

CREATE TABLE IF NOT EXISTS olist_core.freight_methods (
  freight_method_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_freight_method_id BIGINT NULL,
  freight_method_name TEXT NOT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, freight_method_name),
  UNIQUE (tenant_id, olist_freight_method_id)
);

CREATE TABLE IF NOT EXISTS olist_core.intermediators (
  intermediator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_intermediator_id BIGINT NOT NULL,
  intermediator_name TEXT NULL,
  cnpj TEXT NULL,
  payment_institution_cnpj TEXT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_intermediator_id)
);

CREATE TABLE IF NOT EXISTS olist_core.deposits (
  deposit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  olist_deposit_id BIGINT NOT NULL,
  deposit_name TEXT NOT NULL,
  is_active BOOLEAN NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, olist_deposit_id)
);

CREATE TABLE IF NOT EXISTS olist_core.stock_balances (
  stock_balance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  product_id UUID NOT NULL REFERENCES olist_core.products(product_id) ON DELETE CASCADE,
  deposit_id UUID NULL REFERENCES olist_core.deposits(deposit_id) ON DELETE SET NULL,
  physical_qty NUMERIC(18,4) NULL,
  reserved_qty NUMERIC(18,4) NULL,
  available_qty NUMERIC(18,4) NULL,
  source_updated_at TIMESTAMPTZ NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, product_id, deposit_id)
);

CREATE TABLE IF NOT EXISTS olist_core.stock_movements (
  stock_movement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  product_id UUID NULL REFERENCES olist_core.products(product_id) ON DELETE SET NULL,
  deposit_id UUID NULL REFERENCES olist_core.deposits(deposit_id) ON DELETE SET NULL,
  movement_type TEXT NOT NULL,
  movement_date TIMESTAMPTZ NULL,
  quantity NUMERIC(18,4) NULL,
  reference_entity TEXT NULL,
  reference_olist_id BIGINT NULL,
  source_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT stock_movements_type_check CHECK (movement_type IN ('entrada', 'saida', 'ajuste', 'reserva', 'estorno', 'outro'))
);

COMMENT ON TABLE olist_core.contacts IS 'Cadastro consolidado de clientes, fornecedores e demais contatos do ERP.';
COMMENT ON TABLE olist_core.products IS 'Catalogo normalizado de produtos com suporte a atributos flexiveis em JSONB.';
COMMENT ON TABLE olist_core.stock_balances IS 'Saldo consolidado por produto e deposito.';

CREATE INDEX IF NOT EXISTS idx_companies_tenant_id ON olist_core.companies (tenant_id);
CREATE INDEX IF NOT EXISTS idx_olist_users_tenant_id ON olist_core.olist_users (tenant_id);
CREATE INDEX IF NOT EXISTS idx_vendors_tenant_id ON olist_core.vendors (tenant_id);
CREATE INDEX IF NOT EXISTS idx_contacts_lookup ON olist_core.contacts (tenant_id, cpf_cnpj, contact_code);
CREATE INDEX IF NOT EXISTS idx_contact_people_contact_id ON olist_core.contact_people (contact_id);
CREATE INDEX IF NOT EXISTS idx_addresses_contact_id ON olist_core.addresses (contact_id, address_role);
CREATE INDEX IF NOT EXISTS idx_categories_parent ON olist_core.categories (tenant_id, parent_olist_category_id);
CREATE INDEX IF NOT EXISTS idx_products_lookup ON olist_core.products (tenant_id, product_code, product_name);
CREATE INDEX IF NOT EXISTS idx_product_variants_product_id ON olist_core.product_variants (product_id);
CREATE INDEX IF NOT EXISTS idx_product_tag_links_tag_id ON olist_core.product_tag_links (product_tag_id);
CREATE INDEX IF NOT EXISTS idx_price_list_items_lookup ON olist_core.price_list_items (tenant_id, olist_product_id);
CREATE INDEX IF NOT EXISTS idx_stock_balances_lookup ON olist_core.stock_balances (tenant_id, product_id, deposit_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_lookup ON olist_core.stock_movements (tenant_id, movement_date DESC);

DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'olist_core.companies',
    'olist_core.olist_users',
    'olist_core.vendors',
    'olist_core.contact_types',
    'olist_core.contacts',
    'olist_core.contact_people',
    'olist_core.addresses',
    'olist_core.categories',
    'olist_core.brands',
    'olist_core.tag_groups',
    'olist_core.product_tags',
    'olist_core.products',
    'olist_core.product_variants',
    'olist_core.product_tag_links',
    'olist_core.services',
    'olist_core.price_lists',
    'olist_core.price_list_items',
    'olist_core.payment_methods',
    'olist_core.receipt_methods',
    'olist_core.shipping_methods',
    'olist_core.freight_methods',
    'olist_core.intermediators',
    'olist_core.deposits',
    'olist_core.stock_balances',
    'olist_core.stock_movements'
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
