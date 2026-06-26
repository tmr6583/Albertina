-- Albertina: views analiticas do dominio Olist ERP

BEGIN;

CREATE OR REPLACE VIEW olist_mart.vw_dim_contacts AS
SELECT
  c.tenant_id,
  c.contact_id,
  c.olist_contact_id,
  c.contact_code,
  c.contact_name,
  c.trade_name,
  c.person_type,
  c.cpf_cnpj,
  c.crm_status,
  v.vendor_name AS owner_vendor_name,
  ct.type_name AS contact_type_name,
  c.created_at,
  c.updated_at,
  c.synced_at
FROM olist_core.contacts c
LEFT JOIN olist_core.vendors v
  ON v.vendor_id = c.vendor_id
LEFT JOIN olist_core.contact_types ct
  ON ct.contact_type_id = c.contact_type_id;

COMMENT ON VIEW olist_mart.vw_dim_contacts IS 'Dimensao analitica de contatos consolidados da Olist.';

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
  p.synced_at
FROM olist_core.products p
LEFT JOIN olist_core.categories c
  ON c.category_id = p.category_id
LEFT JOIN olist_core.brands b
  ON b.brand_id = p.brand_id;

COMMENT ON VIEW olist_mart.vw_dim_products IS 'Dimensao analitica de produtos com categoria e marca.';

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
  COALESCE(items.total_quantity, 0::numeric) AS total_quantity,
  COALESCE(pay.installments_count, 0) AS installments_count,
  COALESCE(pay.installments_amount, 0::numeric) AS installments_amount,
  COALESCE(ip.integrated_payments_count, 0) AS integrated_payments_count,
  COALESCE(ip.integrated_payments_amount, 0::numeric) AS integrated_payments_amount,
  o.is_consumer_final,
  o.source_updated_at,
  o.created_at,
  o.updated_at,
  o.synced_at
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

COMMENT ON VIEW olist_mart.vw_fact_orders IS 'Fato analitico de pedidos/vendas com metricas consolidadas por cabecalho.';

CREATE OR REPLACE VIEW olist_mart.vw_fact_order_items AS
SELECT
  oi.tenant_id,
  oi.order_item_id,
  oi.order_id,
  o.olist_order_id,
  o.order_number,
  o.order_date,
  o.order_status,
  o.order_origin,
  o.contact_id,
  c.contact_name,
  oi.product_id,
  p.product_code,
  p.product_name,
  oi.service_id,
  s.service_name,
  oi.quantity,
  oi.unit_price,
  oi.total_amount,
  o.discount_amount,
  o.freight_amount,
  o.intermediator_id,
  i.intermediator_name,
  o.created_at,
  o.updated_at,
  o.synced_at
FROM olist_core.order_items oi
JOIN olist_core.orders o
  ON o.order_id = oi.order_id
LEFT JOIN olist_core.contacts c
  ON c.contact_id = o.contact_id
LEFT JOIN olist_core.products p
  ON p.product_id = oi.product_id
LEFT JOIN olist_core.services s
  ON s.service_id = oi.service_id
LEFT JOIN olist_core.intermediators i
  ON i.intermediator_id = o.intermediator_id;

COMMENT ON VIEW olist_mart.vw_fact_order_items IS 'Fato analitico de itens de pedidos com granularidade linha a linha.';

CREATE OR REPLACE VIEW olist_mart.vw_fact_receivables AS
SELECT
  ar.tenant_id,
  ar.ar_id,
  ar.olist_ar_id,
  ar.order_id,
  o.order_number,
  ar.invoice_id,
  inv.invoice_number,
  ar.contact_id,
  c.contact_name,
  rec.category_name AS revenue_category_name,
  ar.status,
  ar.issue_date,
  ar.due_date,
  ar.competence_date,
  ar.amount,
  ar.open_amount,
  COALESCE(rr.total_received_amount, 0::numeric) AS total_received_amount,
  ar.created_at,
  ar.updated_at,
  ar.synced_at
FROM olist_core.accounts_receivable ar
LEFT JOIN olist_core.orders o
  ON o.order_id = ar.order_id
LEFT JOIN olist_core.invoices inv
  ON inv.invoice_id = ar.invoice_id
LEFT JOIN olist_core.contacts c
  ON c.contact_id = ar.contact_id
LEFT JOIN olist_core.revenue_expense_categories rec
  ON rec.category_fin_id = ar.revenue_category_id
LEFT JOIN (
  SELECT
    arr.ar_id,
    SUM(arr.receipt_amount) AS total_received_amount
  FROM olist_core.accounts_receivable_receipts arr
  GROUP BY arr.ar_id
) rr
  ON rr.ar_id = ar.ar_id;

COMMENT ON VIEW olist_mart.vw_fact_receivables IS 'Fato analitico de contas a receber com recebido acumulado.';

CREATE OR REPLACE VIEW olist_mart.vw_fact_payables AS
SELECT
  ap.tenant_id,
  ap.ap_id,
  ap.olist_ap_id,
  ap.purchase_order_id,
  po.order_number AS purchase_order_number,
  ap.contact_id,
  c.contact_name,
  exp.category_name AS expense_category_name,
  ap.status,
  ap.issue_date,
  ap.due_date,
  ap.competence_date,
  ap.amount,
  ap.open_amount,
  COALESCE(pr.total_paid_amount, 0::numeric) AS total_paid_amount,
  ap.created_at,
  ap.updated_at,
  ap.synced_at
FROM olist_core.accounts_payable ap
LEFT JOIN olist_core.purchase_orders po
  ON po.purchase_order_id = ap.purchase_order_id
LEFT JOIN olist_core.contacts c
  ON c.contact_id = ap.contact_id
LEFT JOIN olist_core.revenue_expense_categories exp
  ON exp.category_fin_id = ap.expense_category_id
LEFT JOIN (
  SELECT
    apr.ap_id,
    SUM(apr.payment_amount) AS total_paid_amount
  FROM olist_core.accounts_payable_receipts apr
  GROUP BY apr.ap_id
) pr
  ON pr.ap_id = ap.ap_id;

COMMENT ON VIEW olist_mart.vw_fact_payables IS 'Fato analitico de contas a pagar com pago acumulado.';

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
  sb.synced_at
FROM olist_core.stock_balances sb
LEFT JOIN olist_core.products p
  ON p.product_id = sb.product_id
LEFT JOIN olist_core.deposits d
  ON d.deposit_id = sb.deposit_id;

COMMENT ON VIEW olist_mart.vw_fact_inventory IS 'Fato analitico de estoque por produto e deposito.';

CREATE OR REPLACE VIEW olist_mart.vw_crm_pipeline AS
SELECT
  cs.tenant_id,
  cs.crm_subject_id,
  cs.olist_subject_id,
  cs.contact_id,
  c.contact_name,
  st.stage_name,
  cs.subject_title,
  cs.subject_status,
  cs.is_archived,
  cs.is_starred,
  COALESCE(a.actions_count, 0) AS actions_count,
  COALESCE(n.notes_count, 0) AS notes_count,
  cs.source_updated_at,
  cs.created_at,
  cs.updated_at,
  cs.synced_at
FROM olist_core.crm_subjects cs
LEFT JOIN olist_core.contacts c
  ON c.contact_id = cs.contact_id
LEFT JOIN olist_core.crm_stages st
  ON st.crm_stage_id = cs.crm_stage_id
LEFT JOIN (
  SELECT
    ca.crm_subject_id,
    COUNT(*) AS actions_count
  FROM olist_core.crm_actions ca
  GROUP BY ca.crm_subject_id
) a
  ON a.crm_subject_id = cs.crm_subject_id
LEFT JOIN (
  SELECT
    cn.crm_subject_id,
    COUNT(*) AS notes_count
  FROM olist_core.crm_notes cn
  GROUP BY cn.crm_subject_id
) n
  ON n.crm_subject_id = cs.crm_subject_id;

COMMENT ON VIEW olist_mart.vw_crm_pipeline IS 'Visao analitica do pipeline de CRM com totalizadores por assunto.';

COMMIT;
