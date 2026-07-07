# Guia executivo de mapeamento Olist ERP x banco de dados

Visão executiva do modelo de integração entre a API do ERP Olist e o banco `Supabase/PostgreSQL` do projeto `Albertina`.

## Navegação

- [Objetivo](#objetivo)
- [Arquitetura resumida](#arquitetura-resumida)
- [Cobertura por entidade](#cobertura-por-entidade)
- [Mapa executivo por domínio](#mapa-executivo-por-domínio)
- [Padrão de carga](#padrão-de-carga)
- [Leitura analítica](#leitura-analítica)
- [Referência técnica](#referência-técnica)

## Objetivo

Este guia responde três perguntas de gestão:

- quais dados do ERP Olist já têm fluxo definido até o banco
- quais entidades já possuem extração operacional e quais ainda estão parcialmente normalizadas
- como o dado percorre as camadas `RAW`, `CORE` e `MART`

## Arquitetura resumida

```mermaid
flowchart LR
    A["API Olist"] --> B["RAW<br/>payload bruto"]
    B --> C["CORE<br/>modelo relacional"]
    C --> D["MART<br/>views e materialized views"]
```

## Cobertura por entidade

Legenda visual:

- `FULL` = extração operacional e mapeamento principal fechados
- `PARTIAL` = extração ativa, mas com parte da normalização ainda parcial
- `LOW` = modelagem prevista ou documentação ainda em consolidação

| Entidade | Cobertura | Leitura executiva | Situação atual |
|---|---|---|---|
| Contatos | `FULL` | cadastro e identificação já bem mapeados | em operação |
| Pedidos | `FULL` | principal entidade comercial já está consolidada | em operação |
| Produtos | `PARTIAL` | catálogo principal cobre o básico, com detalhes ainda em JSONB | em operação |
| Notas fiscais | `PARTIAL` | cabeçalho e anexos já são extraídos, com normalização parcial | em operação |
| Contas a receber | `FULL` | fluxo financeiro principal já está mapeado | em operação |
| Contas a pagar | `FULL` | fluxo financeiro principal já está mapeado | em operação |
| Estoque | `PARTIAL` | saldo e depósitos estão cobertos; movimentos finos seguem evoluindo | em operação |
| Expedição | `PARTIAL` | agrupamentos e expedições já entram, com detalhes ainda mistos | em operação |
| Separação | `PARTIAL` | cabeçalho e itens já entram, com payload complementar parcial | em operação |
| CRM | `PARTIAL` | estágios e assuntos já possuem workflow dedicado | em operação |
| Ordens de compra | `PARTIAL` | workflow ativo com carga relacional ainda evolutiva | em operação |
| Ordens de serviço | `PARTIAL` | workflow ativo com carga relacional ainda evolutiva | em operação |

## Mapa executivo por domínio

| Domínio | Fonte Olist | Destino operacional | Destino analítico |
|---|---|---|---|
| Cadastros | `company_info`, `users`, `vendors`, `contacts`, `brands`, `categories` | `olist_core.companies`, `olist_core.olist_users`, `olist_core.vendors`, `olist_core.contacts`, `olist_core.brands`, `olist_core.categories` | `vw_dim_contacts`, `mv_dim_contacts` |
| Catálogo | `products`, `price_lists`, `services`, `tag_groups`, `product_tags` | `olist_core.products`, `olist_core.price_lists`, `olist_core.services`, `olist_core.tag_groups`, `olist_core.product_tags` | `vw_dim_products`, `mv_dim_products` |
| Vendas | `orders`, `intermediators` | `olist_core.orders` e tabelas filhas | `vw_fact_orders`, `mv_fact_orders`, `vw_fact_order_items`, `mv_fact_order_items` |
| Fiscal | `invoices` | `olist_core.invoices` e tabelas filhas | uso analítico futuro |
| Financeiro | `accounts_receivable`, `accounts_payable`, `payment_methods`, `receipt_methods`, `revenue_expense_categories` | tabelas financeiras em `olist_core.*` | `vw_fact_receivables`, `mv_fact_receivables`, `vw_fact_payables`, `mv_fact_payables` |
| Logística | `shipping_methods`, `deposits`, `products_stock`, `shipments`, `separations` | `shipping_methods`, `deposits`, `stock_balances`, `shipment_groups`, `separations` | `vw_fact_inventory`, `mv_fact_inventory` |
| CRM e operações | `crm_stages`, `crm_subjects`, `purchase_orders`, `service_orders` | `crm_*`, `purchase_orders`, `service_orders` | `vw_crm_pipeline`, `mv_crm_pipeline` |

## Padrão de carga

| Etapa | Descrição |
|---|---|
| 1 | consumir endpoint Olist |
| 2 | persistir payload em `olist_raw.api_payloads` |
| 3 | registrar execução, log e controle global em `olist_admin.*` |
| 4 | normalizar em `olist_core.*` com `upsert` quando aplicável |
| 5 | atualizar `olist_mart.vw_*` e executar refresh seletivo de `mv_*` |

## Leitura analítica

| Necessidade | Objeto |
|---|---|
| visão consolidada de pedidos | `olist_mart.mv_fact_orders` |
| visão por item vendido | `olist_mart.mv_fact_order_items` |
| visão de recebíveis | `olist_mart.mv_fact_receivables` |
| visão de pagáveis | `olist_mart.mv_fact_payables` |
| visão de estoque | `olist_mart.mv_fact_inventory` |
| visão de pipeline CRM | `olist_mart.mv_crm_pipeline` |

## Referência técnica

- Guia técnico completo: [olist_mapping_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide.md)
- Matriz consolidada: [olist_mapping_matrix_consolidated.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_matrix_consolidated.md)
- Guia de ETL: [olist_etl_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_etl_guide.md)
- DER: [olist_erp_der.md](file:///c:/GitHubLocal/Albertina/docs/olist_erp_der.md)
