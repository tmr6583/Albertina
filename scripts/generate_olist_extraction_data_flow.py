from __future__ import annotations

import html
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
BACKEND = ROOT / "backend"
OUTPUT = DOCS / "olist_extraction_data_flow.html"

sys.path.insert(0, str(BACKEND))

from olist_extraction.catalog import WORKFLOWS  # type: ignore  # noqa: E402


def parse_markdown_table(lines: list[str]) -> list[dict[str, str]]:
    if len(lines) < 2:
        return []
    headers = [cell.strip().strip("`") for cell in lines[0].strip().strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        values = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(values) != len(headers):
            continue
        rows.append(dict(zip(headers, values)))
    return rows


def extract_table_after_marker(path: Path, marker: str) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.strip() != marker:
            continue
        table_lines: list[str] = []
        for candidate in lines[index + 2 :]:
            if candidate.strip().startswith("|"):
                table_lines.append(candidate)
            elif table_lines:
                break
        return parse_markdown_table(table_lines)
    return []


EXECUTIVE_ROWS = extract_table_after_marker(DOCS / "olist_mapping_guide.md", "## Mapa Executivo Por Domínio")
FIELD_ROWS = extract_table_after_marker(DOCS / "olist_mapping_matrix_consolidated.md", "## Planilha")

WORKFLOW_META: dict[str, dict[str, object]] = {
    "company_info": {
        "dominio": "Empresa",
        "descricao": "Dados institucionais da conta Olist.",
        "atual": ["olist_raw.api_payloads (entity_name='company_info')", "olist_admin.sync_runs", "olist_admin.sync_run_logs"],
        "core": ["olist_core.companies"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Fonte confirmada em /info; normalizacao ainda depende de carga dedicada.",
    },
    "users": {
        "dominio": "Cadastros",
        "descricao": "Usuarios do ERP usados em operacoes e separacao.",
        "atual": ["olist_raw.api_payloads (entity_name='users')", "olist_admin.sync_runs"],
        "core": ["olist_core.olist_users"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Usado tambem como referencia para packed_by_user_id.",
    },
    "vendors": {
        "dominio": "Cadastros",
        "descricao": "Vendedores e donos comerciais de contatos/pedidos.",
        "atual": ["olist_raw.api_payloads (entity_name='vendors')", "olist_admin.sync_runs"],
        "core": ["olist_core.vendors"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Relacionamento confirmado com contatos e pedidos.",
    },
    "brands": {
        "dominio": "Catalogo",
        "descricao": "Marcas do catalogo de produtos.",
        "atual": ["olist_raw.api_payloads (entity_name='brands')", "olist_admin.sync_runs"],
        "core": ["olist_core.brands"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Dimensao auxiliar de produtos.",
    },
    "categories": {
        "dominio": "Catalogo",
        "descricao": "Arvore de categorias e hierarquia do catalogo.",
        "atual": ["olist_raw.api_payloads (entity_name='categories')", "olist_admin.sync_runs"],
        "core": ["olist_core.categories"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Inclui listagem em arvore e detalhe por categoria.",
    },
    "revenue_expense_categories": {
        "dominio": "Financeiro",
        "descricao": "Categorias de receita e despesa.",
        "atual": ["olist_raw.api_payloads (entity_name='revenue_expense_categories')", "olist_admin.sync_runs"],
        "core": ["olist_core.revenue_expense_categories"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Base para contas a receber e a pagar.",
    },
    "contacts": {
        "dominio": "Cadastros",
        "descricao": "Clientes, fornecedores, tipos, pessoas e enderecos.",
        "atual": [
            "olist_raw.api_payloads (entity_name='contacts')",
            "olist_admin.sync_runs",
            "olist_admin.sync_watermarks",
            "olist_admin.sync_run_logs",
        ],
        "core": ["olist_core.contacts", "olist_core.contact_people", "olist_core.addresses", "olist_core.contact_types"],
        "mart": ["olist_mart.vw_dim_contacts", "olist_mart.mv_dim_contacts"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Workflow pesado; pagina curta e watermark por dataAtualizacao.",
    },
    "payment_methods": {
        "dominio": "Financeiro",
        "descricao": "Formas de pagamento para pedidos e recebimentos.",
        "atual": ["olist_raw.api_payloads (entity_name='payment_methods')", "olist_admin.sync_runs"],
        "core": ["olist_core.payment_methods"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Lista e detalhe por id.",
    },
    "receipt_methods": {
        "dominio": "Financeiro",
        "descricao": "Formas de recebimento de parcelas e recebimentos.",
        "atual": ["olist_raw.api_payloads (entity_name='receipt_methods')", "olist_admin.sync_runs"],
        "core": ["olist_core.receipt_methods"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Relaciona pedidos e titulos financeiros.",
    },
    "shipping_methods": {
        "dominio": "Logistica",
        "descricao": "Formas de envio e referencias de frete.",
        "atual": ["olist_raw.api_payloads (entity_name='shipping_methods')", "olist_admin.sync_runs"],
        "core": ["olist_core.shipping_methods", "olist_core.freight_methods [A CONFIRMAR path dedicado]"],
        "mart": [],
        "cobertura": "RAW ativo, CORE parcial",
        "observacoes": "Guia tecnico confirma freight_methods, mas o path final segue [A CONFIRMAR].",
    },
    "deposits": {
        "dominio": "Logistica",
        "descricao": "Depositos e locais fisicos de estoque.",
        "atual": ["olist_raw.api_payloads (entity_name='deposits')", "olist_admin.sync_runs"],
        "core": ["olist_core.deposits"],
        "mart": ["olist_mart.vw_fact_inventory", "olist_mart.mv_fact_inventory"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Dimensao auxiliar de estoque e pedidos.",
    },
    "intermediators": {
        "dominio": "Vendas",
        "descricao": "Intermediadores e marketplaces ligados aos pedidos.",
        "atual": ["olist_raw.api_payloads (entity_name='intermediators')", "olist_admin.sync_runs"],
        "core": ["olist_core.intermediators"],
        "mart": ["olist_mart.vw_fact_orders", "olist_mart.mv_fact_orders"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Dimensao auxiliar comercial.",
    },
    "price_lists": {
        "dominio": "Catalogo",
        "descricao": "Listas de preco e itens precificados.",
        "atual": ["olist_raw.api_payloads (entity_name='price_lists')", "olist_admin.sync_runs"],
        "core": ["olist_core.price_lists", "olist_core.price_list_items"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Precificacao desacoplada do produto.",
    },
    "services": {
        "dominio": "Operacoes",
        "descricao": "Catalogo de servicos.",
        "atual": ["olist_raw.api_payloads (entity_name='services')", "olist_admin.sync_runs"],
        "core": ["olist_core.services"],
        "mart": ["olist_mart.vw_fact_order_items", "olist_mart.mv_fact_order_items"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Usado em pedidos e ordens de servico.",
    },
    "tag_groups": {
        "dominio": "Catalogo",
        "descricao": "Grupos de tags de produtos.",
        "atual": ["olist_raw.api_payloads (entity_name='tag_groups')", "olist_admin.sync_runs"],
        "core": ["olist_core.tag_groups"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Base para organizacao de tags do catalogo.",
    },
    "product_tags": {
        "dominio": "Catalogo",
        "descricao": "Tags e vinculos com produtos.",
        "atual": ["olist_raw.api_payloads (entity_name='product_tags')", "olist_admin.sync_runs"],
        "core": ["olist_core.product_tags", "olist_core.product_tag_links"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Links finais dependem de tags por produto.",
    },
    "products": {
        "dominio": "Catalogo",
        "descricao": "Produtos, custos, kits, fabricacao, tags e estoque.",
        "atual": [
            "olist_raw.api_payloads (entity_name='products')",
            "olist_admin.sync_runs",
            "olist_admin.sync_watermarks",
            "olist_admin.sync_run_logs",
        ],
        "core": ["olist_core.products", "olist_core.product_variants [A CONFIRMAR payload]", "olist_core.product_tag_links", "olist_core.stock_balances"],
        "mart": ["olist_mart.vw_dim_products", "olist_mart.mv_dim_products", "olist_mart.vw_fact_inventory", "olist_mart.mv_fact_inventory"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Incremental por dataAlteracao; parte dos subobjetos permanece em JSONB.",
    },
    "orders": {
        "dominio": "Vendas",
        "descricao": "Pedidos, itens, parcelas, pagamentos integrados, despacho e marcadores.",
        "atual": [
            "olist_raw.api_payloads (entity_name='orders')",
            "olist_admin.sync_runs",
            "olist_admin.sync_watermarks",
            "olist_admin.sync_run_logs",
        ],
        "core": ["olist_core.orders", "olist_core.order_items", "olist_core.order_installments", "olist_core.order_integrated_payments", "olist_core.order_shipping", "olist_core.order_markers", "olist_core.order_operations"],
        "mart": ["olist_mart.vw_fact_orders", "olist_mart.mv_fact_orders", "olist_mart.vw_fact_order_items", "olist_mart.mv_fact_order_items"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Entidade central do dominio comercial.",
    },
    "accounts_receivable": {
        "dominio": "Financeiro",
        "descricao": "Titulos a receber, recebimentos e marcadores.",
        "atual": [
            "olist_raw.api_payloads (entity_name='accounts_receivable')",
            "olist_admin.sync_runs",
            "olist_admin.sync_watermarks",
            "olist_admin.sync_run_logs",
        ],
        "core": ["olist_core.accounts_receivable", "olist_core.accounts_receivable_receipts", "olist_core.accounts_receivable_markers"],
        "mart": ["olist_mart.vw_fact_receivables", "olist_mart.mv_fact_receivables"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Incremental por janela de emissao.",
    },
    "accounts_payable": {
        "dominio": "Financeiro",
        "descricao": "Titulos a pagar, pagamentos e marcadores.",
        "atual": [
            "olist_raw.api_payloads (entity_name='accounts_payable')",
            "olist_admin.sync_runs",
            "olist_admin.sync_watermarks",
            "olist_admin.sync_run_logs",
        ],
        "core": ["olist_core.accounts_payable", "olist_core.accounts_payable_receipts", "olist_core.accounts_payable_markers"],
        "mart": ["olist_mart.vw_fact_payables", "olist_mart.mv_fact_payables"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Incremental por janela de emissao.",
    },
    "invoices": {
        "dominio": "Fiscal",
        "descricao": "Notas fiscais, itens, links, XML e marcadores.",
        "atual": ["olist_raw.api_payloads (entity_name='invoices')", "olist_admin.sync_runs", "olist_admin.sync_run_logs"],
        "core": ["olist_core.invoices", "olist_core.invoice_items", "olist_core.invoice_markers"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Parte dos detalhes complementares segue em payload bruto.",
    },
    "shipments": {
        "dominio": "Logistica",
        "descricao": "Agrupamentos de expedicao, expedicoes e etiquetas.",
        "atual": ["olist_raw.api_payloads (entity_name='shipments')", "olist_admin.sync_runs", "olist_admin.sync_run_logs"],
        "core": ["olist_core.shipment_groups", "olist_core.shipments"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Relaciona pedidos com rastreio e forma de frete.",
    },
    "separations": {
        "dominio": "Logistica",
        "descricao": "Separacoes e itens preparados para expedicao.",
        "atual": ["olist_raw.api_payloads (entity_name='separations')", "olist_admin.sync_runs", "olist_admin.sync_run_logs"],
        "core": ["olist_core.separations", "olist_core.separation_items"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Usa packed_by_olist_user_id e itens por produto.",
    },
    "crm_stages": {
        "dominio": "CRM",
        "descricao": "Estagios do pipeline comercial.",
        "atual": ["olist_raw.api_payloads (entity_name='crm_stages')", "olist_admin.sync_runs"],
        "core": ["olist_core.crm_stages"],
        "mart": ["olist_mart.vw_crm_pipeline", "olist_mart.mv_crm_pipeline"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Dimensao de apoio para assuntos do CRM.",
    },
    "crm_subjects": {
        "dominio": "CRM",
        "descricao": "Assuntos, acoes, anotacoes e marcadores do funil comercial.",
        "atual": [
            "olist_raw.api_payloads (entity_name='crm_subjects')",
            "olist_admin.sync_runs",
            "olist_admin.sync_watermarks",
            "olist_admin.sync_run_logs",
        ],
        "core": ["olist_core.crm_subjects", "olist_core.crm_actions", "olist_core.crm_notes", "olist_core.crm_markers", "olist_core.crm_subject_markers"],
        "mart": ["olist_mart.vw_crm_pipeline", "olist_mart.mv_crm_pipeline"],
        "cobertura": "RAW ativo, CORE/MART modelados",
        "observacoes": "Incremental por dataAtualizacao nos assuntos.",
    },
    "purchase_orders": {
        "dominio": "Operacoes",
        "descricao": "Ordens de compra, itens e marcadores.",
        "atual": ["olist_raw.api_payloads (entity_name='purchase_orders')", "olist_admin.sync_runs", "olist_admin.sync_run_logs"],
        "core": ["olist_core.purchase_orders", "olist_core.purchase_order_items", "olist_core.purchase_order_markers"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Cabecalho operacional de compras.",
    },
    "service_orders": {
        "dominio": "Operacoes",
        "descricao": "Ordens de servico, itens e marcadores.",
        "atual": ["olist_raw.api_payloads (entity_name='service_orders')", "olist_admin.sync_runs", "olist_admin.sync_run_logs"],
        "core": ["olist_core.service_orders", "olist_core.service_order_items", "olist_core.service_order_markers"],
        "mart": [],
        "cobertura": "RAW ativo, CORE modelado",
        "observacoes": "Cabecalho operacional de servicos.",
    },
}


def badge(label: str, kind: str) -> str:
    return f'<span class="badge {kind}">{html.escape(label)}</span>'


def render_list(items: list[str], kind: str) -> str:
    if not items:
        return '<span class="muted">n/a</span>'
    return "".join(badge(item, kind) for item in items)


def build_inventory() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for workflow in WORKFLOWS:
        endpoints: list[str] = []
        for step in workflow.steps:
            value = f"GET {step.endpoint_path}"
            if value not in endpoints:
                endpoints.append(value)
        meta = WORKFLOW_META.get(
            workflow.entity_name,
            {
                "dominio": "Nao classificado",
                "descricao": "Sem resumo executivo consolidado.",
                "atual": [f"olist_raw.api_payloads (entity_name='{workflow.entity_name}')", "olist_admin.sync_runs"],
                "core": ["[A CONFIRMAR]"],
                "mart": [],
                "cobertura": "RAW ativo",
                "observacoes": "[A CONFIRMAR] na documentacao consolidada.",
            },
        )
        rows.append(
            {
                "dominio": meta["dominio"],
                "workflow": workflow.entity_name,
                "descricao": meta["descricao"],
                "endpoints": endpoints,
                "atual": meta["atual"],
                "core": meta["core"],
                "mart": meta["mart"],
                "cobertura": meta["cobertura"],
                "observacoes": meta["observacoes"],
            }
        )
    return rows


def build_html() -> str:
    inventory = build_inventory()
    endpoint_total = sum(len(row["endpoints"]) for row in inventory)
    current_tables = sorted({item for row in inventory for item in row["atual"]})
    modeled_tables = sorted({item for row in inventory for item in row["core"] if "[A CONFIRMAR]" not in item})
    mart_tables = sorted({item for row in inventory for item in row["mart"]})
    generated_at = datetime.now().strftime("%d/%m/%Y")

    executive_html = []
    for row in EXECUTIVE_ROWS:
        executive_html.append(
            "<tr>"
            f"<td>{html.escape(row.get('Domínio', ''))}</td>"
            f"<td>{html.escape(row.get('Fonte ERP Olist', ''))}</td>"
            f"<td><code>{html.escape(row.get('RAW', ''))}</code></td>"
            f"<td><code>{html.escape(row.get('CORE', ''))}</code></td>"
            f"<td><code>{html.escape(row.get('MART', ''))}</code></td>"
            "</tr>"
        )

    inventory_html = []
    for row in inventory:
        inventory_html.append(
            "<tr>"
            f"<td>{html.escape(str(row['dominio']))}</td>"
            "<td>"
            f"<strong>{html.escape(str(row['workflow']))}</strong>"
            f"<div class='muted'>{html.escape(str(row['descricao']))}</div>"
            "</td>"
            f"<td>{render_list(list(row['endpoints']), 'endpoint')}</td>"
            f"<td>{render_list(list(row['atual']), 'current')}</td>"
            f"<td>{render_list(list(row['core']), 'modeled')}</td>"
            f"<td>{render_list(list(row['mart']), 'mart')}</td>"
            f"<td><span class='coverage'>{html.escape(str(row['cobertura']))}</span></td>"
            f"<td>{html.escape(str(row['observacoes']))}</td>"
            "</tr>"
        )

    field_html = []
    for row in FIELD_ROWS:
        cobertura = row.get("Cobertura", "")
        coverage_class = "full" if cobertura == "FULL" else "partial"
        search_text = " ".join(row.values()).lower()
        field_html.append(
            f"<tr data-search='{html.escape(search_text)}'>"
            f"<td>{html.escape(row.get('Dominio', ''))}</td>"
            f"<td>{html.escape(row.get('Entidade', ''))}</td>"
            f"<td>{html.escape(row.get('Endpoint', ''))}</td>"
            f"<td><code>{html.escape(row.get('Campo Olist', ''))}</code></td>"
            f"<td><code>{html.escape(row.get('Tabela Destino', ''))}</code></td>"
            f"<td><code>{html.escape(row.get('Coluna Destino', ''))}</code></td>"
            f"<td>{html.escape(row.get('Transformacao', ''))}</td>"
            f"<td><span class='coverage {coverage_class}'>{html.escape(cobertura)}</span></td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Albertina · Fluxo de Dados da Extração Olist</title>
  <style>
    :root {{
      --bg: #eef4ff;
      --panel: rgba(255, 255, 255, 0.88);
      --panel-strong: rgba(241, 247, 255, 0.98);
      --line: rgba(39, 92, 176, 0.16);
      --text: #11233f;
      --muted: #5f7394;
      --blue: #1f63d8;
      --cyan: #0f8c8f;
      --gold: #b56a00;
      --green: #0d8a49;
      --shadow: 0 26px 64px rgba(51, 80, 129, 0.14);
      --radius: 24px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(116, 200, 255, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(255, 206, 138, 0.24), transparent 32%),
        linear-gradient(180deg, #f6f9ff 0%, #ebf2ff 100%);
    }}
    .shell {{ max-width: 1680px; margin: 0 auto; padding: 40px 28px 72px; }}
    .hero {{
      position: relative;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 32px;
      background: linear-gradient(135deg, rgba(232, 241, 255, 0.96), rgba(250, 252, 255, 0.98));
      box-shadow: var(--shadow);
      padding: 34px;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: -20% auto auto 60%;
      width: 420px;
      height: 420px;
      background: radial-gradient(circle, rgba(83, 152, 255, 0.18), transparent 65%);
      filter: blur(12px);
      pointer-events: none;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.22em;
      color: var(--cyan);
      margin-bottom: 16px;
    }}
    .eyebrow::before {{ content: ""; width: 40px; height: 1px; background: currentColor; }}
    h1 {{ margin: 0; font-size: clamp(36px, 6vw, 68px); line-height: 0.96; max-width: 11ch; }}
    .hero p {{ max-width: 78ch; color: var(--muted); font-size: 17px; line-height: 1.7; margin: 20px 0 0; }}
    .hero-grid {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr); gap: 28px; align-items: end; }}
    .hero-note {{
      border-radius: 24px;
      padding: 22px;
      background: rgba(255, 255, 255, 0.74);
      border: 1px solid rgba(39, 92, 176, 0.14);
      backdrop-filter: blur(10px);
    }}
    .hero-note strong {{ display: block; margin-bottom: 10px; font-size: 17px; }}
    .grid {{ display: grid; gap: 18px; }}
    .stats {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 22px; }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 22px;
      box-shadow: var(--shadow);
    }}
    .stats .card {{
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(233, 242, 255, 0.96));
      border-color: rgba(31, 99, 216, 0.18);
      box-shadow: 0 20px 42px rgba(32, 74, 145, 0.16);
    }}
    .stats .card:nth-child(1) {{ border-top: 4px solid rgba(31, 99, 216, 0.85); }}
    .stats .card:nth-child(2) {{ border-top: 4px solid rgba(15, 140, 143, 0.82); }}
    .stats .card:nth-child(3) {{ border-top: 4px solid rgba(181, 106, 0, 0.78); }}
    .stats .card:nth-child(4) {{ border-top: 4px solid rgba(13, 138, 73, 0.78); }}
    .card strong.value {{ display: block; font-size: 36px; margin-top: 10px; }}
    .stats .card strong.value {{ color: #0d2140; }}
    .card p, .muted {{ color: var(--muted); }}
    .section {{ margin-top: 22px; }}
    .section-head {{ display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 14px; }}
    .section-head h2 {{ margin: 0; font-size: 28px; }}
    .section-head p {{ margin: 0; color: var(--muted); max-width: 76ch; }}
    .flow-grid {{ grid-template-columns: repeat(5, minmax(0, 1fr)); }}
    .flow-card {{ position: relative; min-height: 210px; }}
    .flow-card::after {{
      content: "→";
      position: absolute;
      top: 26px;
      right: -12px;
      color: var(--gold);
      font-size: 28px;
    }}
    .flow-card:last-child::after {{ display: none; }}
    .flow-step {{ color: var(--gold); font-size: 13px; text-transform: uppercase; letter-spacing: 0.18em; }}
    .flow-card h3 {{ margin: 12px 0 10px; font-size: 22px; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 7px 12px;
      margin: 0 8px 8px 0;
      font-size: 12px;
      line-height: 1.35;
      border: 1px solid transparent;
    }}
    .endpoint {{ background: rgba(31, 99, 216, 0.10); border-color: rgba(31, 99, 216, 0.18); color: #13408e; }}
    .current {{ background: rgba(15, 140, 143, 0.10); border-color: rgba(15, 140, 143, 0.18); color: #0b6769; }}
    .modeled {{ background: rgba(181, 106, 0, 0.12); border-color: rgba(181, 106, 0, 0.18); color: #8b5000; }}
    .mart {{ background: rgba(13, 138, 73, 0.10); border-color: rgba(13, 138, 73, 0.16); color: #0a6c3a; }}
    .source {{ background: rgba(255,255,255,0.82); border-color: rgba(39, 92, 176, 0.12); color: var(--muted); }}
    .coverage {{ font-weight: 700; color: var(--text); }}
    .coverage.full {{ color: var(--green); }}
    .coverage.partial {{ color: var(--gold); }}
    .table-card {{ overflow: hidden; padding: 0; }}
    .table-toolbar {{ display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: center; padding: 20px 22px; border-bottom: 1px solid var(--line); }}
    .table-toolbar input {{
      width: min(420px, 100%);
      padding: 13px 16px;
      border-radius: 14px;
      border: 1px solid rgba(39, 92, 176, 0.14);
      background: rgba(255,255,255,0.92);
      color: var(--text);
      outline: none;
    }}
    .table-wrap {{ overflow: auto; max-height: 820px; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
    th, td {{ text-align: left; vertical-align: top; padding: 14px 16px; border-bottom: 1px solid rgba(39, 92, 176, 0.08); }}
    thead tr {{
      background: linear-gradient(180deg, rgba(224, 236, 255, 0.98), rgba(210, 227, 253, 0.98));
      box-shadow: inset 0 -1px 0 rgba(31, 99, 216, 0.08);
    }}
    th {{
      position: sticky;
      top: 0;
      background: transparent;
      z-index: 2;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      color: #28466f;
      font-weight: 800;
    }}
    tbody tr:nth-child(odd) {{ background: rgba(255, 255, 255, 0.72); }}
    tbody tr:nth-child(even) {{ background: rgba(237, 244, 255, 0.88); }}
    tbody tr:hover {{ background: rgba(223, 236, 255, 0.95); }}
    td code {{ color: #173f8a; font-family: "Cascadia Code", "Consolas", monospace; font-size: 12px; }}
    .legend {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    .sources {{ margin-top: 24px; display: flex; flex-wrap: wrap; gap: 10px; }}
    .footer {{ margin-top: 28px; color: var(--muted); font-size: 13px; }}
    @media (max-width: 1200px) {{
      .stats, .flow-grid, .legend {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .hero-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 760px) {{
      .shell {{ padding: 20px 14px 56px; }}
      .stats, .flow-grid, .legend {{ grid-template-columns: 1fr; }}
      .hero {{ padding: 24px; }}
      h1 {{ max-width: none; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">Albertina · Olist ERP · Supabase</div>
          <h1>Fluxo de dados da extração Olist para o Supabase</h1>
          <p>
            Documento visual amplo da extração Olist no projeto Albertina. Ele mostra a trilha operacional entre UI, API,
            controle incremental, camada RAW, destino relacional modelado em CORE e consumo analítico em MART. A leitura deixa
            explícito onde cada dataset do ERP está hoje e para onde ele foi desenhado no schema do Supabase.
          </p>
        </div>
        <aside class="hero-note">
          <strong>Como interpretar sem risco de ambiguidade</strong>
          <p>
            A persistência <strong>atual</strong> desta aplicação já grava controle operacional e payload bruto. As tabelas
            <code>olist_core</code> e views <code>olist_mart</code> representam o <strong>destino modelado confirmado</strong>
            nas migrations e guias técnicos. Sempre que um path ou payload ainda não estiver fechado, o item permanece marcado
            como <code>[A CONFIRMAR]</code>.
          </p>
        </aside>
      </div>
      <div class="grid stats">
        <article class="card"><span class="eyebrow">Workflows</span><strong class="value">{len(inventory):02d}</strong><p>Grupos de extração pública confirmados no catálogo.</p></article>
        <article class="card"><span class="eyebrow">Endpoints</span><strong class="value">{endpoint_total:02d}</strong><p>Rotas GET entre listas, detalhes e coleções filhas.</p></article>
        <article class="card"><span class="eyebrow">RAW Atual</span><strong class="value">{len(current_tables):02d}</strong><p>Tabelas/camadas hoje efetivamente preenchidas.</p></article>
        <article class="card"><span class="eyebrow">Destino Modelado</span><strong class="value">{len(modeled_tables) + len(mart_tables):02d}</strong><p>Tabelas CORE e artefatos MART documentados.</p></article>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>Fluxo operacional</h2>
          <p>O que acontece entre o clique em <em>Iniciar extração</em> e a leitura final no Supabase.</p>
        </div>
      </div>
      <div class="grid flow-grid">
        <article class="card flow-card"><div class="flow-step">01 · Disparo</div><h3>UI e API</h3><p>O menu <code>/extracao</code> aciona <code>POST /api/extraction/run</code>, faz polling de <code>/api/extraction/overview</code>, permite parada segura em <code>/api/extraction/stop</code> e baixa o log completo pelo histórico com <code>/api/extraction/executions/{{execution_id}}</code>.</p></article>
        <article class="card flow-card"><div class="flow-step">02 · Controle</div><h3>Execução</h3><p>O backend registra andamento, logs e checkpoint incremental em <code>olist_admin.sync_runs</code>, <code>sync_run_logs</code> e <code>sync_watermarks</code>.</p></article>
        <article class="card flow-card"><div class="flow-step">03 · RAW</div><h3>Payload integral</h3><p>Cada resposta confirmada da API pública entra em <code>olist_raw.api_payloads</code> com payload JSON completo, ids externos e timestamp de origem.</p></article>
        <article class="card flow-card"><div class="flow-step">04 · CORE</div><h3>Modelo relacional</h3><p>As migrations já definem o destino em <code>olist_core</code> para cadastros, vendas, logística, fiscal, financeiro, CRM e operações.</p></article>
        <article class="card flow-card"><div class="flow-step">05 · MART</div><h3>Analytics</h3><p>Views e materialized views em <code>olist_mart</code> consolidam fatos e dimensões para análise e consumo futuro.</p></article>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div><h2>Mapa executivo por domínio</h2><p>Resumo técnico consolidado entre fonte ERP, RAW, CORE e MART.</p></div>
      </div>
      <article class="card table-card">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Domínio</th><th>Fonte ERP Olist</th><th>RAW</th><th>CORE</th><th>MART</th></tr></thead>
            <tbody>{''.join(executive_html)}</tbody>
          </table>
        </div>
      </article>
    </section>

    <section class="section">
      <div class="section-head">
        <div><h2>Inventário amplo por workflow</h2><p>Cada workflow extraído, seus endpoints públicos e o destino atual/modelado no Supabase.</p></div>
      </div>
      <article class="card table-card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Domínio</th><th>Workflow</th><th>Endpoints públicos</th><th>Persistência atual</th>
                <th>Destino modelado</th><th>MART</th><th>Cobertura</th><th>Observações</th>
              </tr>
            </thead>
            <tbody>{''.join(inventory_html)}</tbody>
          </table>
        </div>
      </article>
    </section>

    <section class="section">
      <div class="section-head">
        <div><h2>Matriz detalhada de campos confirmados</h2><p>Campos do ERP Olist já mapeados documentalmente para colunas de destino no Supabase.</p></div>
      </div>
      <article class="card table-card">
        <div class="table-toolbar">
          <div><strong>Filtro rápido</strong><div class="muted">Busque por domínio, entidade, endpoint, tabela ou coluna.</div></div>
          <input id="matrix-search" type="search" placeholder="Ex.: contatos, order_items, dataAtualizacao, crm" />
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Domínio</th><th>Entidade</th><th>Endpoint</th><th>Campo Olist</th><th>Tabela destino</th><th>Coluna destino</th><th>Transformação</th><th>Cobertura</th></tr>
            </thead>
            <tbody id="matrix-body">{''.join(field_html)}</tbody>
          </table>
        </div>
      </article>
    </section>

    <section class="section">
      <div class="section-head">
        <div><h2>Legenda de leitura</h2><p>Como diferenciar o que já é operacional do que está modelado para normalização futura.</p></div>
      </div>
      <div class="grid legend">
        <article class="card"><strong>Persistência atual</strong><p>Camada de banco já gravada hoje: <code>olist_admin.*</code> para controle e <code>olist_raw.api_payloads</code> para payload integral.</p></article>
        <article class="card"><strong>Destino modelado</strong><p>Tabelas <code>olist_core</code> criadas nas migrations para a carga relacional normalizada.</p></article>
        <article class="card"><strong>MART</strong><p>Views e materialized views analíticas em <code>olist_mart</code> para consumo e reporting.</p></article>
        <article class="card"><strong>[A CONFIRMAR]</strong><p>Path ou payload ainda parcialmente documentado, mantido explicitamente com ressalva para não inventar comportamento.</p></article>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div><h2>Fontes que sustentam este HTML</h2><p>Arquivos usados para consolidar os destinos do ERP Olist no Supabase.</p></div>
      </div>
      <div class="sources">
        <span class="badge source">backend/olist_extraction/catalog.py</span>
        <span class="badge source">docs/olist_mapping_guide.md</span>
        <span class="badge source">docs/olist_mapping_matrix_consolidated.md</span>
        <span class="badge source">docs/olist_etl_guide.md</span>
        <span class="badge source">supabase/migrations/20260626103000_olist_erp_foundation.sql</span>
        <span class="badge source">supabase/migrations/20260626104000_olist_erp_master_data.sql</span>
        <span class="badge source">supabase/migrations/20260626105000_olist_erp_sales_and_logistics.sql</span>
        <span class="badge source">supabase/migrations/20260626110000_olist_erp_finance_and_operations.sql</span>
        <span class="badge source">supabase/migrations/20260626111000_olist_erp_mart_views.sql</span>
      </div>
      <div class="footer">Gerado a partir do estado atual do repositório em {generated_at}. Atualize este documento sempre que catálogo, schema, interface operacional ou carga normalizada evoluírem.</div>
    </section>
  </div>
  <script>
    const searchInput = document.getElementById('matrix-search');
    const rows = Array.from(document.querySelectorAll('#matrix-body tr'));
    searchInput.addEventListener('input', () => {{
      const term = searchInput.value.trim().toLowerCase();
      rows.forEach((row) => {{
        const haystack = row.dataset.search || row.textContent.toLowerCase();
        row.style.display = haystack.includes(term) ? '' : 'none';
      }});
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    OUTPUT.write_text(build_html(), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
