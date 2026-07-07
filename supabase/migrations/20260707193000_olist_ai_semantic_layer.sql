-- Albertina: camada semantica da IA e evolucao analitica inicial

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS olist_ai;

CREATE TABLE IF NOT EXISTS olist_ai.ai_metric_catalog (
  metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  metric_code TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  domain TEXT NOT NULL,
  definition TEXT NOT NULL,
  formula_description TEXT NULL,
  sql_rule_summary TEXT NULL,
  source_schema TEXT NOT NULL,
  source_object TEXT NOT NULL,
  time_basis TEXT NULL,
  default_filters JSONB NOT NULL DEFAULT '{}'::JSONB,
  allowed_profiles JSONB NOT NULL DEFAULT '[]'::JSONB,
  status TEXT NOT NULL DEFAULT 'draft',
  owner_area TEXT NULL,
  business_notes TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ai_metric_catalog_status_check CHECK (status IN ('draft', 'active', 'deprecated')),
  CONSTRAINT uq_ai_metric_catalog UNIQUE (tenant_id, metric_code)
);

CREATE TABLE IF NOT EXISTS olist_ai.ai_business_glossary (
  term_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  term TEXT NOT NULL,
  normalized_term TEXT NOT NULL,
  aliases JSONB NOT NULL DEFAULT '[]'::JSONB,
  domain TEXT NOT NULL,
  definition TEXT NOT NULL,
  business_notes TEXT NULL,
  source_reference TEXT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ai_business_glossary_status_check CHECK (status IN ('draft', 'active', 'deprecated')),
  CONSTRAINT uq_ai_business_glossary UNIQUE (tenant_id, normalized_term)
);

CREATE TABLE IF NOT EXISTS olist_ai.ai_entity_synonyms (
  synonym_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL,
  business_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  synonyms JSONB NOT NULL DEFAULT '[]'::JSONB,
  target_schema TEXT NULL,
  target_object TEXT NULL,
  target_field TEXT NULL,
  confidence_level NUMERIC(5,4) NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ai_entity_synonyms_status_check CHECK (status IN ('draft', 'active', 'deprecated'))
);

CREATE TABLE IF NOT EXISTS olist_ai.ai_query_templates (
  template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  tool_name TEXT NOT NULL,
  intent_name TEXT NOT NULL,
  template_description TEXT NOT NULL,
  domain TEXT NOT NULL,
  source_schema TEXT NOT NULL,
  source_object TEXT NOT NULL,
  allowed_filters JSONB NOT NULL DEFAULT '[]'::JSONB,
  required_filters JSONB NOT NULL DEFAULT '[]'::JSONB,
  default_limit INTEGER NULL,
  max_limit INTEGER NULL,
  response_shape JSONB NOT NULL DEFAULT '{}'::JSONB,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ai_query_templates_status_check CHECK (status IN ('draft', 'active', 'deprecated'))
);

CREATE TABLE IF NOT EXISTS olist_ai.ai_prompt_policies (
  policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  policy_name TEXT NOT NULL,
  policy_scope TEXT NOT NULL,
  target_name TEXT NULL,
  policy_text TEXT NOT NULL,
  priority_order INTEGER NOT NULL DEFAULT 100,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ai_prompt_policies_status_check CHECK (status IN ('draft', 'active', 'deprecated'))
);

CREATE TABLE IF NOT EXISTS olist_ai.ai_query_audit (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  user_id TEXT NULL REFERENCES public.users(id) ON DELETE SET NULL,
  session_id TEXT NULL,
  question_text TEXT NOT NULL,
  normalized_intent TEXT NULL,
  tool_name TEXT NULL,
  source_schema TEXT NULL,
  source_object TEXT NULL,
  filters_json JSONB NOT NULL DEFAULT '{}'::JSONB,
  sql_fingerprint TEXT NULL,
  row_count INTEGER NULL,
  result_summary TEXT NULL,
  llm_model TEXT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ NULL,
  status TEXT NOT NULL DEFAULT 'success',
  error_message TEXT NULL,
  CONSTRAINT ai_query_audit_status_check CHECK (status IN ('success', 'error', 'blocked'))
);

CREATE TABLE IF NOT EXISTS olist_ai.ai_documents (
  document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  document_type TEXT NOT NULL,
  document_title TEXT NOT NULL,
  source_uri TEXT NULL,
  source_system TEXT NULL,
  domain TEXT NULL,
  version_label TEXT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT ai_documents_status_check CHECK (status IN ('draft', 'active', 'archived'))
);

CREATE TABLE IF NOT EXISTS olist_ai.ai_document_chunks (
  chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES olist_admin.tenants(tenant_id) ON DELETE CASCADE,
  document_id UUID NOT NULL REFERENCES olist_ai.ai_documents(document_id) ON DELETE CASCADE,
  chunk_order INTEGER NOT NULL,
  domain TEXT NULL,
  chunk_text TEXT NOT NULL,
  chunk_tokens INTEGER NULL,
  embedding VECTOR(1536) NULL,
  metadata_json JSONB NOT NULL DEFAULT '{}'::JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_metric_catalog_domain ON olist_ai.ai_metric_catalog (tenant_id, domain, status);
CREATE INDEX IF NOT EXISTS idx_ai_metric_catalog_source ON olist_ai.ai_metric_catalog (tenant_id, source_schema, source_object);
CREATE INDEX IF NOT EXISTS idx_ai_business_glossary_domain ON olist_ai.ai_business_glossary (tenant_id, domain, status);
CREATE INDEX IF NOT EXISTS idx_ai_business_glossary_term ON olist_ai.ai_business_glossary (tenant_id, normalized_term);
CREATE INDEX IF NOT EXISTS idx_ai_entity_synonyms_target ON olist_ai.ai_entity_synonyms (tenant_id, entity_type, target_schema, target_object);
CREATE INDEX IF NOT EXISTS idx_ai_query_templates_tool ON olist_ai.ai_query_templates (tenant_id, tool_name, status);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_policies_scope ON olist_ai.ai_prompt_policies (tenant_id, policy_scope, priority_order);
CREATE INDEX IF NOT EXISTS idx_ai_query_audit_lookup ON olist_ai.ai_query_audit (tenant_id, started_at DESC, status);
CREATE INDEX IF NOT EXISTS idx_ai_documents_lookup ON olist_ai.ai_documents (tenant_id, document_type, domain, status);
CREATE INDEX IF NOT EXISTS idx_ai_document_chunks_document ON olist_ai.ai_document_chunks (tenant_id, document_id, chunk_order);
CREATE INDEX IF NOT EXISTS idx_ai_document_chunks_embedding ON olist_ai.ai_document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

COMMENT ON TABLE olist_ai.ai_metric_catalog IS 'Catalogo oficial de metricas consumidas pela IA.';
COMMENT ON TABLE olist_ai.ai_business_glossary IS 'Glossario de termos, definicoes e sinonimos do negocio.';
COMMENT ON TABLE olist_ai.ai_entity_synonyms IS 'Mapa semantico entre linguagem natural e objetos reais do banco.';
COMMENT ON TABLE olist_ai.ai_query_templates IS 'Catalogo de templates funcionais associados a tools da IA.';
COMMENT ON TABLE olist_ai.ai_prompt_policies IS 'Politicas operacionais e de comportamento para a camada de IA.';
COMMENT ON TABLE olist_ai.ai_query_audit IS 'Trilha de auditoria das consultas executadas pela IA.';
COMMENT ON TABLE olist_ai.ai_documents IS 'Metadados dos documentos carregados para RAG.';
COMMENT ON TABLE olist_ai.ai_document_chunks IS 'Chunks semanticos e embeddings utilizados na recuperacao vetorial.';

DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'olist_ai.ai_metric_catalog',
    'olist_ai.ai_business_glossary',
    'olist_ai.ai_entity_synonyms',
    'olist_ai.ai_query_templates',
    'olist_ai.ai_prompt_policies',
    'olist_ai.ai_documents',
    'olist_ai.ai_document_chunks'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %s', replace(split_part(tbl, '.', 2), '.', '_') || '_updated_at', tbl);
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION olist_admin.set_row_updated_at()', replace(split_part(tbl, '.', 2), '.', '_') || '_updated_at', tbl);
  END LOOP;
END $$;

DO $$
DECLARE
  tbl TEXT;
  tables TEXT[] := ARRAY[
    'olist_ai.ai_metric_catalog',
    'olist_ai.ai_business_glossary',
    'olist_ai.ai_entity_synonyms',
    'olist_ai.ai_query_templates',
    'olist_ai.ai_prompt_policies',
    'olist_ai.ai_query_audit',
    'olist_ai.ai_documents',
    'olist_ai.ai_document_chunks'
  ];
BEGIN
  FOREACH tbl IN ARRAY tables LOOP
    EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %s', split_part(tbl, '.', 2) || '_select_policy', tbl);
    EXECUTE format('CREATE POLICY %I ON %s FOR SELECT USING (olist_admin.can_read_tenant(tenant_id))', split_part(tbl, '.', 2) || '_select_policy', tbl);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %s', split_part(tbl, '.', 2) || '_write_policy', tbl);
    EXECUTE format('CREATE POLICY %I ON %s FOR ALL USING (olist_admin.can_write_tenant(tenant_id)) WITH CHECK (olist_admin.can_write_tenant(tenant_id))', split_part(tbl, '.', 2) || '_write_policy', tbl);
  END LOOP;
END $$;

INSERT INTO olist_ai.ai_metric_catalog (
  tenant_id,
  metric_code,
  metric_name,
  domain,
  definition,
  formula_description,
  sql_rule_summary,
  source_schema,
  source_object,
  time_basis,
  default_filters,
  allowed_profiles,
  status,
  owner_area,
  business_notes
)
SELECT
  t.tenant_id,
  x.metric_code,
  x.metric_name,
  x.domain,
  x.definition,
  x.formula_description,
  x.sql_rule_summary,
  x.source_schema,
  x.source_object,
  x.time_basis,
  x.default_filters::jsonb,
  x.allowed_profiles::jsonb,
  'active',
  'IA ERP',
  x.business_notes
FROM olist_admin.tenants t
CROSS JOIN (
  VALUES
    (
      'gross_sales_billed',
      'Faturamento Efetivo',
      'vendas',
      'Soma dos pedidos faturados/finalizados no periodo.',
      'Soma de total_order_amount para pedidos com order_status = 1.',
      'sum(total_order_amount) where order_status = 1',
      'olist_mart',
      'vw_fact_orders',
      'billing_date',
      '{"is_billed_order": true}',
      '["executivo","analista","operacional"]',
      'No modelo atual, faturamento efetivo usa billing_date como base temporal.'
    ),
    (
      'orders_count_created',
      'Quantidade De Pedidos',
      'vendas',
      'Quantidade de pedidos no periodo consultado.',
      'Count distinct de order_id.',
      'count(distinct order_id)',
      'olist_mart',
      'vw_fact_orders',
      'order_date',
      '{}',
      '["executivo","analista","operacional"]',
      'Usa order_date para analise de emissao/criacao do pedido.'
    ),
    (
      'average_ticket_billed',
      'Ticket Medio Faturado',
      'vendas',
      'Valor medio por pedido faturado no periodo.',
      'Faturamento efetivo dividido pela quantidade de pedidos faturados.',
      'sum(total_order_amount) / count(distinct order_id) where order_status = 1',
      'olist_mart',
      'vw_fact_orders',
      'billing_date',
      '{"is_billed_order": true}',
      '["executivo","analista"]',
      'Depende do conceito de pedido faturado.'
    ),
    (
      'receivables_open_amount',
      'Saldo Em Aberto A Receber',
      'financeiro',
      'Total em aberto nas contas a receber.',
      'Soma de open_amount.',
      'sum(open_amount)',
      'olist_mart',
      'vw_fact_receivables',
      'due_date',
      '{}',
      '["executivo","analista","operacional"]',
      'A data preferencial para visao de vencimento e due_date.'
    ),
    (
      'receivables_overdue_amount',
      'Recebiveis Vencidos',
      'financeiro',
      'Total em atraso nas contas a receber.',
      'Soma de open_amount onde due_date < hoje.',
      'sum(open_amount) where due_date < current_date and open_amount > 0',
      'olist_mart',
      'vw_fact_receivables',
      'due_date',
      '{"open_amount_gt": 0}',
      '["executivo","analista","operacional"]',
      'Pode receber filtro complementar por status futuramente.'
    ),
    (
      'payables_open_amount',
      'Saldo Em Aberto A Pagar',
      'financeiro',
      'Total em aberto nas contas a pagar.',
      'Soma de open_amount.',
      'sum(open_amount)',
      'olist_mart',
      'vw_fact_payables',
      'due_date',
      '{}',
      '["executivo","analista","operacional"]',
      'A data preferencial para visao de vencimento e due_date.'
    ),
    (
      'payables_overdue_amount',
      'Pagaveis Vencidos',
      'financeiro',
      'Total em atraso nas contas a pagar.',
      'Soma de open_amount onde due_date < hoje.',
      'sum(open_amount) where due_date < current_date and open_amount > 0',
      'olist_mart',
      'vw_fact_payables',
      'due_date',
      '{"open_amount_gt": 0}',
      '["executivo","analista","operacional"]',
      'Pode receber filtro complementar por status futuramente.'
    ),
    (
      'inventory_available_qty',
      'Estoque Disponivel',
      'estoque',
      'Quantidade disponivel para venda ou separacao.',
      'Soma de available_qty.',
      'sum(available_qty)',
      'olist_mart',
      'vw_fact_inventory',
      'source_updated_at',
      '{}',
      '["executivo","analista","operacional"]',
      'Usa a visao consolidada de estoque por deposito.'
    ),
    (
      'inventory_below_minimum',
      'Estoque Abaixo Do Minimo',
      'estoque',
      'Itens com saldo atual igual ou inferior ao estoque minimo cadastrado.',
      'Comparacao entre available_qty e stock_min_qty.',
      'available_qty <= stock_min_qty',
      'olist_mart',
      'vw_fact_inventory',
      'source_updated_at',
      '{"requires_stock_min_qty": true}',
      '["analista","operacional"]',
      'Depende da normalizacao do estoque minimo no modelo analitico.'
    )
) AS x(
  metric_code,
  metric_name,
  domain,
  definition,
  formula_description,
  sql_rule_summary,
  source_schema,
  source_object,
  time_basis,
  default_filters,
  allowed_profiles,
  business_notes
)
ON CONFLICT (tenant_id, metric_code) DO UPDATE
SET metric_name = EXCLUDED.metric_name,
    domain = EXCLUDED.domain,
    definition = EXCLUDED.definition,
    formula_description = EXCLUDED.formula_description,
    sql_rule_summary = EXCLUDED.sql_rule_summary,
    source_schema = EXCLUDED.source_schema,
    source_object = EXCLUDED.source_object,
    time_basis = EXCLUDED.time_basis,
    default_filters = EXCLUDED.default_filters,
    allowed_profiles = EXCLUDED.allowed_profiles,
    status = EXCLUDED.status,
    owner_area = EXCLUDED.owner_area,
    business_notes = EXCLUDED.business_notes,
    updated_at = NOW();

INSERT INTO olist_ai.ai_business_glossary (
  tenant_id,
  term,
  normalized_term,
  aliases,
  domain,
  definition,
  business_notes,
  source_reference,
  status
)
SELECT
  t.tenant_id,
  x.term,
  x.normalized_term,
  x.aliases::jsonb,
  x.domain,
  x.definition,
  x.business_notes,
  x.source_reference,
  'active'
FROM olist_admin.tenants t
CROSS JOIN (
  VALUES
    (
      'Faturamento',
      'faturamento',
      '["vendas faturadas","faturamento efetivo"]',
      'vendas',
      'Soma dos pedidos finalizados com notas fiscais autorizadas ou contas lançadas no período.',
      'No modelo atual do Albertina deve usar billing_date e order_status = 1.',
      'IA Olist + modelo analitico Albertina'
    ),
    (
      'Billing Date',
      'billing_date',
      '["data faturamento","data de faturamento","data de finalizacao"]',
      'vendas',
      'Data de faturamento do pedido, derivada de dataFaturamento no ERP.',
      'Base temporal preferencial para faturamento efetivo.',
      'Mapeamento Olist -> olist_core.orders.billing_date'
    ),
    (
      'Order Date',
      'order_date',
      '["data pedido","data emissao pedido"]',
      'vendas',
      'Data original do pedido, derivada de data no ERP.',
      'Usar para analises de emissao, nao para faturamento efetivo.',
      'Mapeamento Olist -> olist_core.orders.order_date'
    ),
    (
      'Titulos Vencidos',
      'titulos_vencidos',
      '["vencidos","atrasados"]',
      'financeiro',
      'Titulos com data de vencimento anterior a data atual e sem registro de quitacao.',
      'No MVP usar due_date < hoje e open_amount > 0.',
      'IA Olist + modelo analitico Albertina'
    ),
    (
      'Estoque Minimo',
      'estoque_minimo',
      '["minimo estoque","quantidade minima"]',
      'estoque',
      'Parametro de estoque minimo do cadastro do produto.',
      'Atualmente disponivel em raw_attributes -> estoque -> minimo.',
      'Payload de produtos Olist'
    ),
    (
      'Estoque Baixo',
      'estoque_baixo',
      '["abaixo do minimo","risco de ruptura"]',
      'estoque',
      'Situacao em que o saldo atual e igual ou inferior ao estoque minimo do cadastro.',
      'Depende da normalizacao de stock_min_qty na MART.',
      'IA Olist + modelo analitico Albertina'
    )
) AS x(
  term,
  normalized_term,
  aliases,
  domain,
  definition,
  business_notes,
  source_reference
)
ON CONFLICT (tenant_id, normalized_term) DO UPDATE
SET term = EXCLUDED.term,
    aliases = EXCLUDED.aliases,
    domain = EXCLUDED.domain,
    definition = EXCLUDED.definition,
    business_notes = EXCLUDED.business_notes,
    source_reference = EXCLUDED.source_reference,
    status = EXCLUDED.status,
    updated_at = NOW();

INSERT INTO olist_ai.ai_entity_synonyms (
  tenant_id,
  entity_type,
  business_name,
  normalized_name,
  synonyms,
  target_schema,
  target_object,
  target_field,
  confidence_level,
  status
)
SELECT
  t.tenant_id,
  x.entity_type,
  x.business_name,
  x.normalized_name,
  x.synonyms::jsonb,
  x.target_schema,
  x.target_object,
  x.target_field,
  x.confidence_level,
  'active'
FROM olist_admin.tenants t
CROSS JOIN (
  VALUES
    ('metric', 'Faturamento', 'faturamento', '["vendas faturadas","faturamento efetivo"]', 'olist_mart', 'vw_fact_orders', 'total_order_amount', 0.9800),
    ('field', 'Data de Faturamento', 'billing_date', '["data faturamento","data de finalizacao"]', 'olist_mart', 'vw_fact_orders', 'billing_date', 0.9900),
    ('field', 'Data do Pedido', 'order_date', '["data pedido","data emissao"]', 'olist_mart', 'vw_fact_orders', 'order_date', 0.9900),
    ('field', 'Estoque Minimo', 'estoque_minimo', '["minimo","estoque minimo"]', 'olist_core', 'products', 'raw_attributes.estoque.minimo', 0.9200),
    ('field', 'Saldo Disponivel', 'available_qty', '["disponivel","saldo disponivel"]', 'olist_mart', 'vw_fact_inventory', 'available_qty', 0.9900),
    ('field', 'Status do Pedido', 'order_status', '["situacao pedido","status pedido"]', 'olist_mart', 'vw_fact_orders', 'order_status', 0.9900)
) AS x(
  entity_type,
  business_name,
  normalized_name,
  synonyms,
  target_schema,
  target_object,
  target_field,
  confidence_level
);

INSERT INTO olist_ai.ai_query_templates (
  tenant_id,
  tool_name,
  intent_name,
  template_description,
  domain,
  source_schema,
  source_object,
  allowed_filters,
  required_filters,
  default_limit,
  max_limit,
  response_shape,
  status
)
SELECT
  t.tenant_id,
  x.tool_name,
  x.intent_name,
  x.template_description,
  x.domain,
  x.source_schema,
  x.source_object,
  x.allowed_filters::jsonb,
  x.required_filters::jsonb,
  x.default_limit,
  x.max_limit,
  x.response_shape::jsonb,
  'active'
FROM olist_admin.tenants t
CROSS JOIN (
  VALUES
    (
      'consultar_resumo_vendas',
      'sales_summary',
      'Resumo de faturamento, pedidos e ticket medio com foco em pedidos faturados.',
      'vendas',
      'olist_mart',
      'vw_fact_orders',
      '["start_date","end_date","vendor_name","contact_name","order_origin_name","time_basis"]',
      '["start_date","end_date"]',
      50,
      500,
      '{"summary_text":true,"summary_metrics":true,"result_table":true}'
    ),
    (
      'consultar_estoque_baixo',
      'inventory_below_minimum',
      'Lista itens com available_qty menor ou igual ao estoque minimo.',
      'estoque',
      'olist_mart',
      'vw_fact_inventory',
      '["product_name","product_code","deposit_name"]',
      '[]',
      50,
      500,
      '{"summary_text":true,"result_table":true}'
    ),
    (
      'consultar_receber_vencidos',
      'receivables_overdue',
      'Lista titulos a receber vencidos e em aberto.',
      'financeiro',
      'olist_mart',
      'vw_fact_receivables',
      '["reference_date","contact_name","status"]',
      '[]',
      50,
      500,
      '{"summary_text":true,"result_table":true}'
    )
) AS x(
  tool_name,
  intent_name,
  template_description,
  domain,
  source_schema,
  source_object,
  allowed_filters,
  required_filters,
  default_limit,
  max_limit,
  response_shape
)
ON CONFLICT DO NOTHING;

INSERT INTO olist_ai.ai_prompt_policies (
  tenant_id,
  policy_name,
  policy_scope,
  target_name,
  policy_text,
  priority_order,
  status
)
SELECT
  t.tenant_id,
  'default_sql_guardrails',
  'global',
  NULL,
  'A IA deve consultar preferencialmente olist_mart, usar function calling, evitar SQL arbitrario e sempre respeitar tenant_id e perfil do usuario.',
  10,
  'active'
FROM olist_admin.tenants t
ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW olist_mart.vw_dim_products AS
SELECT
  p.tenant_id,
  p.product_id,
  p.olist_product_id,
  p.product_code,
  p.product_name,
  p.sku,
  p.gtin,
  p.product_type,
  c.category_name,
  b.brand_name,
  p.is_active,
  p.created_at,
  p.updated_at,
  p.synced_at,
  CASE
    WHEN jsonb_typeof(p.raw_attributes -> 'estoque') = 'object'
      THEN NULLIF(p.raw_attributes -> 'estoque' ->> 'minimo', '')::NUMERIC
    ELSE NULL
  END AS stock_min_qty,
  CASE
    WHEN jsonb_typeof(p.raw_attributes -> 'estoque') = 'object'
      THEN NULLIF(p.raw_attributes -> 'estoque' ->> 'maximo', '')::NUMERIC
    ELSE NULL
  END AS stock_max_qty,
  CASE
    WHEN jsonb_typeof(p.raw_attributes -> 'estoque') = 'object'
      THEN COALESCE((p.raw_attributes -> 'estoque' ->> 'controlar')::BOOLEAN, FALSE)
    ELSE FALSE
  END AS stock_control_enabled
FROM olist_core.products p
LEFT JOIN olist_core.categories c
  ON c.category_id = p.category_id
LEFT JOIN olist_core.brands b
  ON b.brand_id = p.brand_id;

CREATE OR REPLACE VIEW olist_mart.vw_fact_orders AS
SELECT
  o.tenant_id,
  o.order_id,
  o.olist_order_id,
  o.order_number,
  o.order_status,
  o.order_origin,
  CASE o.order_origin
    WHEN 0 THEN 'Pedido de Venda'
    WHEN 1 THEN 'PDV'
    ELSE 'Nao informado'
  END AS order_origin_name,
  o.contact_id,
  c.contact_name,
  o.vendor_id,
  v.vendor_name,
  o.deposit_id,
  d.deposit_name,
  o.intermediator_id,
  i.intermediator_name,
  o.order_date,
  o.delivery_date,
  o.billing_date,
  o.expected_date,
  o.shipped_at,
  o.purchase_order_number,
  o.total_products_amount,
  o.total_order_amount,
  o.discount_amount,
  o.freight_amount,
  o.other_expenses_amount,
  COALESCE(items.items_count, 0) AS items_count,
  COALESCE(items.total_quantity, 0::NUMERIC) AS total_quantity,
  COALESCE(pay.installments_count, 0) AS installments_count,
  COALESCE(pay.installments_amount, 0::NUMERIC) AS installments_amount,
  COALESCE(ip.integrated_payments_count, 0) AS integrated_payments_count,
  COALESCE(ip.integrated_payments_amount, 0::NUMERIC) AS integrated_payments_amount,
  o.is_consumer_final,
  o.source_updated_at,
  o.created_at,
  o.updated_at,
  o.synced_at,
  CASE o.order_status
    WHEN 0 THEN 'Aberta'
    WHEN 1 THEN 'Faturada'
    WHEN 2 THEN 'Cancelada'
    WHEN 3 THEN 'Aprovada'
    WHEN 4 THEN 'Preparando Envio'
    WHEN 5 THEN 'Enviada'
    WHEN 6 THEN 'Entregue'
    WHEN 7 THEN 'Pronto Envio'
    WHEN 8 THEN 'Dados Incompletos'
    WHEN 9 THEN 'Nao Entregue'
    ELSE 'Nao informado'
  END AS order_status_name,
  (o.order_status = 1 AND o.billing_date IS NOT NULL) AS is_billed_order,
  CASE
    WHEN o.order_status = 1 AND o.billing_date IS NOT NULL THEN (o.billing_date AT TIME ZONE 'UTC')::DATE
    ELSE NULL
  END AS billed_on
FROM olist_core.orders o
LEFT JOIN olist_core.contacts c
  ON c.contact_id = o.contact_id
LEFT JOIN olist_core.vendors v
  ON v.vendor_id = o.vendor_id
LEFT JOIN olist_core.deposits d
  ON d.deposit_id = o.deposit_id
LEFT JOIN olist_core.intermediators i
  ON i.intermediator_id = o.intermediator_id
LEFT JOIN (
  SELECT
    oi.order_id,
    COUNT(*) AS items_count,
    SUM(oi.quantity) AS total_quantity
  FROM olist_core.order_items oi
  GROUP BY oi.order_id
) items
  ON items.order_id = o.order_id
LEFT JOIN (
  SELECT
    oi.order_id,
    COUNT(*) AS installments_count,
    SUM(oi.installment_amount) AS installments_amount
  FROM olist_core.order_installments oi
  GROUP BY oi.order_id
) pay
  ON pay.order_id = o.order_id
LEFT JOIN (
  SELECT
    oip.order_id,
    COUNT(*) AS integrated_payments_count,
    SUM(oip.payment_amount) AS integrated_payments_amount
  FROM olist_core.order_integrated_payments oip
  GROUP BY oip.order_id
) ip
  ON ip.order_id = o.order_id;

CREATE OR REPLACE VIEW olist_mart.vw_fact_inventory AS
SELECT
  sb.tenant_id,
  sb.stock_balance_id,
  sb.product_id,
  p.product_code,
  p.product_name,
  sb.deposit_id,
  d.deposit_name,
  sb.physical_qty,
  sb.reserved_qty,
  sb.available_qty,
  sb.source_updated_at,
  sb.created_at,
  sb.updated_at,
  sb.synced_at,
  CASE
    WHEN jsonb_typeof(p.raw_attributes -> 'estoque') = 'object'
      THEN NULLIF(p.raw_attributes -> 'estoque' ->> 'minimo', '')::NUMERIC
    ELSE NULL
  END AS stock_min_qty,
  CASE
    WHEN jsonb_typeof(p.raw_attributes -> 'estoque') = 'object'
      THEN COALESCE((p.raw_attributes -> 'estoque' ->> 'controlar')::BOOLEAN, FALSE)
    ELSE FALSE
  END AS stock_control_enabled,
  CASE
    WHEN jsonb_typeof(p.raw_attributes -> 'estoque') = 'object'
         AND NULLIF(p.raw_attributes -> 'estoque' ->> 'minimo', '') IS NOT NULL
         AND sb.available_qty IS NOT NULL
      THEN sb.available_qty <= NULLIF(p.raw_attributes -> 'estoque' ->> 'minimo', '')::NUMERIC
    ELSE FALSE
  END AS is_below_min_stock
FROM olist_core.stock_balances sb
LEFT JOIN olist_core.products p
  ON p.product_id = sb.product_id
LEFT JOIN olist_core.deposits d
  ON d.deposit_id = sb.deposit_id;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_dim_products;
CREATE MATERIALIZED VIEW olist_mart.mv_dim_products AS
SELECT * FROM olist_mart.vw_dim_products
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_fact_orders;
CREATE MATERIALIZED VIEW olist_mart.mv_fact_orders AS
SELECT * FROM olist_mart.vw_fact_orders
WITH DATA;

DROP MATERIALIZED VIEW IF EXISTS olist_mart.mv_fact_inventory;
CREATE MATERIALIZED VIEW olist_mart.mv_fact_inventory AS
SELECT * FROM olist_mart.vw_fact_inventory
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_dim_products
  ON olist_mart.mv_dim_products (tenant_id, product_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fact_orders
  ON olist_mart.mv_fact_orders (tenant_id, order_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_fact_inventory
  ON olist_mart.mv_fact_inventory (tenant_id, stock_balance_id);

CREATE INDEX IF NOT EXISTS idx_mv_fact_orders_dates
  ON olist_mart.mv_fact_orders (tenant_id, order_date DESC, billing_date DESC);
CREATE INDEX IF NOT EXISTS idx_mv_fact_orders_billed
  ON olist_mart.mv_fact_orders (tenant_id, is_billed_order, billed_on DESC);
CREATE INDEX IF NOT EXISTS idx_mv_fact_inventory_product
  ON olist_mart.mv_fact_inventory (tenant_id, product_id, deposit_id);
CREATE INDEX IF NOT EXISTS idx_mv_fact_inventory_below_min
  ON olist_mart.mv_fact_inventory (tenant_id, is_below_min_stock, available_qty);

COMMIT;
