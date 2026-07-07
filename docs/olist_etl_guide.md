# Guia de ETL por entidade do ERP Olist

Guia operacional da integração entre a API do ERP Olist e o banco relacional do projeto `Albertina`, alinhado ao catálogo real de workflows.

## Navegação

- [Padrão geral](#padrão-geral)
- [Contatos](#contatos)
- [Pedidos](#pedidos)
- [Produtos](#produtos)
- [Notas fiscais](#notas-fiscais)
- [Contas a receber](#contas-a-receber)
- [Contas a pagar](#contas-a-pagar)
- [Estoque](#estoque)
- [Expedição](#expedição)
- [Separação](#separação)
- [CRM](#crm)
- [Referências](#referências)

## Padrão geral

| Etapa | Descrição |
|---|---|
| Extração | consumir endpoint oficial com autenticação, retry, paginação e estratégia incremental compatível |
| Persistência RAW | gravar payload integral em `olist_raw.api_payloads` |
| Controle | registrar execução, logs, `watermarks` e controle global em `olist_admin.*` |
| CORE sync | promover `RAW -> CORE` automaticamente ao final da execução bem-sucedida |
| Transformação | normalizar tipos, resolver chaves externas e preservar subobjetos em JSONB quando necessário |
| Upsert | aplicar `ON CONFLICT` por chave natural Olist e `tenant_id`; reconstruir filhas quando aplicável |
| MART | executar refresh automático das materialized views após o `core_sync` |

## Contatos

| Fase | Implementação atual |
|---|---|
| Extração | `GET /contatos`, `GET /contatos/{idContato}`, `GET /contatos/{idContato}/pessoas` |
| Estratégia | `watermark` por `dataAtualizacao` |
| Transformação | mapear dados principais em `contacts`; preservar `endereco` no payload bruto e expandir o que estiver confirmado |
| Upsert | `olist_core.contacts` por `(tenant_id, olist_contact_id)` |
| Analítico | `mv_dim_contacts`, com refresh automático após o `core_sync` |

## Pedidos

| Fase | Implementação atual |
|---|---|
| Extração | `GET /pedidos`, `GET /pedidos/{idPedido}` e endpoints filhos operacionais |
| Estratégia | `watermark` por `dataAtualizacao` |
| Transformação | gravar cabeçalho em `orders` e reidratar itens, parcelas, pagamentos integrados, despacho e marcadores |
| Upsert | `olist_core.orders` por `(tenant_id, olist_order_id)` e reconstrução técnica das filhas |
| Analítico | `mv_fact_orders` e `mv_fact_order_items`, com refresh automático após o `core_sync` |

## Produtos

| Fase | Implementação atual |
|---|---|
| Extração | `GET /produtos`, detalhe, custos, kit, fabricado, tags e `GET /estoque/{idProduto}` |
| Estratégia | `watermark` por `dataAlteracao` |
| Transformação | mapear cabeçalho em `products`; preservar subobjetos e atributos ainda parciais em `raw_attributes` |
| Upsert | `olist_core.products` por `(tenant_id, olist_product_id)` |
| Analítico | `mv_dim_products` e `mv_fact_inventory`, com refresh automático após o `core_sync` |

## Notas fiscais

| Fase | Implementação atual |
|---|---|
| Extração | `GET /notas`, `GET /notas/{idNota}`, `/link`, `/marcadores`, `/xml` e itens |
| Estratégia | `date_range` por `dataInicial` / `dataFinal`, com sobreposição operacional |
| Transformação | mapear cabeçalho fiscal e preservar anexos, XML e detalhes complementares quando necessário |
| Upsert | `olist_core.invoices` por `(tenant_id, olist_invoice_id)` |
| Analítico | sem mart dedicada |

## Contas a receber

| Fase | Implementação atual |
|---|---|
| Extração | `GET /contas-receber` e detalhes complementares por título |
| Estratégia | `date_range` por emissão (`dataInicialEmissao` / `dataFinalEmissao`) com sobreposição |
| Transformação | mapear título principal; preservar subobjetos bancários, marcadores e recebimentos quando necessário |
| Upsert | `olist_core.accounts_receivable` por `(tenant_id, olist_ar_id)` |
| Analítico | `mv_fact_receivables`, com refresh automático após o `core_sync` |

## Contas a pagar

| Fase | Implementação atual |
|---|---|
| Extração | `GET /contas-pagar` e detalhes complementares por título |
| Estratégia | `date_range` por emissão (`dataInicialEmissao` / `dataFinalEmissao`) com sobreposição |
| Transformação | mapear título principal; preservar subobjetos, marcadores e pagamentos quando necessário |
| Upsert | `olist_core.accounts_payable` por `(tenant_id, olist_ap_id)` |
| Analítico | `mv_fact_payables`, com refresh automático após o `core_sync` |

## Estoque

| Fase | Implementação atual |
|---|---|
| Extração | `GET /estoque/{idProduto}` e workflows auxiliares como `GET /depositos` |
| Estratégia | `cooldown` para referências estáveis e detalhamento por produto em `products_stock` |
| Transformação | gerar linha consolidada do produto e linhas por depósito; preservar subobjetos complementares em `source_payload` |
| Upsert | `olist_core.stock_balances` por `(tenant_id, product_id, deposit_id)` |
| Analítico | `mv_fact_inventory`, com refresh automático após o `core_sync` |

## Expedição

| Fase | Implementação atual |
|---|---|
| Extração | `GET /expedicao`, `GET /expedicao/{idAgrupamento}` e endpoints de etiquetas |
| Estratégia | `date_range` por `dataInicial` / `dataFinal` com detalhamento posterior |
| Transformação | separar cabeçalho do agrupamento e expedições filhas; resolver pedido e forma de frete quando possível |
| Upsert | `olist_core.shipment_groups` e `olist_core.shipments` |
| Analítico | sem mart dedicada |

## Separação

| Fase | Implementação atual |
|---|---|
| Extração | `GET /separacao` e `GET /separacao/{idSeparacao}` |
| Estratégia | `date_range` por `dataInicial` / `dataFinal` com detalhamento por separação |
| Transformação | mapear cabeçalho operacional e gerar `separation_items` a partir de `itens[]` |
| Upsert | `olist_core.separations` e `olist_core.separation_items` |
| Analítico | sem mart dedicada |

## CRM

| Fase | Implementação atual |
|---|---|
| Extração | `GET /crm/estagios`, `GET /crm/assuntos` e endpoints filhos de ações, anotações e marcadores |
| Estratégia | `watermark` por `dataAtualizacao` nos assuntos e `cooldown` em entidades auxiliares |
| Transformação | gravar estágios, assuntos, ações, anotações e marcadores; resolver contato e estágio |
| Upsert | `crm_subjects`, `crm_stages`, `crm_actions`, `crm_notes`, `crm_markers` por chaves naturais |
| Analítico | `mv_crm_pipeline`, com refresh automático após o `core_sync` |

## Referências

- Catálogo de workflows: [catalog.py](file:///c:/GitHubLocal/Albertina/backend/olist_extraction/catalog.py)
- Guia técnico de mapeamento: [olist_mapping_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide.md)
- Matriz consolidada: [olist_mapping_matrix_consolidated.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_matrix_consolidated.md)
- Fluxo visual: [olist_extraction_data_flow.html](file:///c:/GitHubLocal/Albertina/docs/olist_extraction_data_flow.html)
