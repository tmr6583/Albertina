# Guia De ETL Por Entidade Olist ERP

Guia operacional de ETL para a integração entre a API Olist ERP e o banco relacional do projeto `Albertina`.

## Navegação

- [Padrão Geral](#padrão-geral)
- [Contatos](#contatos)
- [Pedidos](#pedidos)
- [Produtos](#produtos)
- [Notas Fiscais](#notas-fiscais)
- [Contas A Receber](#contas-a-receber)
- [Contas A Pagar](#contas-a-pagar)
- [Estoque](#estoque)
- [Expedição](#expedição)
- [Separação](#separação)
- [CRM](#crm)

## Padrão Geral

| Etapa | Descrição |
|---|---|
| Extração | consumir endpoint oficial com autenticação, paginação e retry |
| Transformação | normalizar tipos, resolver chaves externas e preservar subobjetos em JSONB quando necessário |
| Upsert | aplicar `ON CONFLICT` por chave natural Olist + `tenant_id` |
| Refresh | atualizar `vw_*` automaticamente e `mv_*` de forma seletiva |

## Contatos

| Fase | Implementação |
|---|---|
| Extração | `GET /contatos?dataAtualizacao=...&limit=...&offset=...` |
| Transformação | mapear dados principais em `contacts`; preservar `endereco` no payload bruto e expandir o que estiver confirmado |
| Upsert | `olist_core.contacts` por `(tenant_id, olist_contact_id)` |
| Refresh | `olist_mart.refresh_olist_mart_view('mv_dim_contacts', false)` quando houver impacto analítico |

## Pedidos

| Fase | Implementação |
|---|---|
| Extração | `GET /pedidos?dataAtualizacao=...` seguido de `GET /pedidos/{idPedido}` |
| Transformação | gravar cabeçalho em `orders`, rehidratar `itens`, `parcelas`, `pagamentosIntegrados`, `marcadores` e `despacho` |
| Upsert | `olist_core.orders` por `(tenant_id, olist_order_id)` e reconstrução técnica das filhas |
| Refresh | `mv_fact_orders` e `mv_fact_order_items` |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "numeroPedido": "<integer>",
  "origemPedido": "<integer>",
  "cliente": { "id": "<integer>" },
  "valorTotalPedido": "<number>",
  "itens": [
    {
      "produto": { "id": "<integer>" },
      "quantidade": "<number>"
    }
  ]
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.orders` | `olist_order_id`, `order_number`, `contact_id`, `total_order_amount` |
| `olist_core.order_items` | `order_id`, `product_id`, `quantity` |

## Produtos

| Fase | Implementação |
|---|---|
| Extração | `GET /produtos?dataAlteracao=...` `[A CONFIRMAR como watermark definitivo]` |
| Transformação | mapear cabeçalho em `products`; preservar `precos`, `estoque.localizacao` e `tipoVariacao` em `raw_attributes` |
| Upsert | `olist_core.products` por `(tenant_id, olist_product_id)` |
| Refresh | `mv_dim_products` |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "sku": "<string>",
  "descricao": "<string>",
  "tipo": "<string>",
  "gtin": "<string>",
  "precos": {
    "preco": "<number>"
  }
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.products` | `olist_product_id`, `sku`, `product_name`, `product_type`, `gtin`, `raw_attributes` |

## Notas Fiscais

| Fase | Implementação |
|---|---|
| Extração | `GET /notas` e, se necessário, detalhe complementar `[A CONFIRMAR]` |
| Transformação | mapear cabeçalho fiscal; preservar logística, ecommerce e origem em `raw_attributes` |
| Upsert | `olist_core.invoices` por `(tenant_id, olist_invoice_id)` |
| Refresh | sem mart dedicada nesta fase |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "numero": "<string>",
  "serie": "<string>",
  "chaveAcesso": "<string>",
  "dataEmissao": "<string>",
  "valor": "<number>",
  "codigoRastreamento": "<string>"
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.invoices` | `olist_invoice_id`, `invoice_number`, `invoice_series`, `access_key`, `issued_at`, `total_amount`, `tracking_code` |

## Contas A Receber

| Fase | Implementação |
|---|---|
| Extração | `GET /contas-receber` |
| Transformação | mapear título principal; preservar campos bancários e subobjetos em `raw_attributes` e `source_payload` |
| Upsert | `olist_core.accounts_receivable` por `(tenant_id, olist_ar_id)` |
| Refresh | `mv_fact_receivables` |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "situacao": "<string>",
  "data": "<string>",
  "dataVencimento": "<string>",
  "valor": "<number>",
  "saldo": "<number>",
  "cliente": { "id": "<integer>" }
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.accounts_receivable` | `olist_ar_id`, `status`, `issue_date`, `due_date`, `amount`, `open_amount`, `contact_id` |

## Contas A Pagar

| Fase | Implementação |
|---|---|
| Extração | `GET /contas-pagar` |
| Transformação | mapear título principal; preservar `serieDocumento`, `cliente` e `marcadores` em payload bruto quando necessário |
| Upsert | `olist_core.accounts_payable` por `(tenant_id, olist_ap_id)` |
| Refresh | `mv_fact_payables` |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "situacao": "<string>",
  "data": "<string>",
  "dataVencimento": "<string>",
  "valor": "<number>",
  "saldo": "<number>",
  "cliente": { "id": "<integer>" }
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.accounts_payable` | `olist_ap_id`, `status`, `issue_date`, `due_date`, `amount`, `open_amount`, `contact_id` |

## Estoque

| Fase | Implementação |
|---|---|
| Extração | `GET /estoque/{idProduto}` |
| Transformação | gerar linha consolidada do produto e linhas por depósito; preservar `localizacao` e flags complementares em `source_payload` |
| Upsert | `olist_core.stock_balances` por `(tenant_id, product_id, deposit_id)` |
| Refresh | `mv_fact_inventory` |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "saldo": "<number>",
  "reservado": "<number>",
  "disponivel": "<number>",
  "depositos": [
    {
      "id": "<integer>",
      "saldo": "<number>",
      "reservado": "<number>",
      "disponivel": "<number>"
    }
  ]
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.stock_balances` | `product_id`, `deposit_id`, `physical_qty`, `reserved_qty`, `available_qty` |

## Expedição

| Fase | Implementação |
|---|---|
| Extração | `GET /expedicao/{idAgrupamento}` |
| Transformação | separar cabeçalho do agrupamento e expedições filhas; resolver venda e forma de envio/frete quando possível |
| Upsert | `shipment_groups` por `(tenant_id, olist_shipment_group_id)` e `shipments` por `(tenant_id, olist_shipment_id)` |
| Refresh | sem mart dedicada nesta fase |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "identificacao": "<string>",
  "formaEnvio": { "id": "<integer>" },
  "expedicoes": [
    {
      "id": "<integer>",
      "situacao": "<string>",
      "venda": { "id": "<integer>" },
      "logistica": {
        "codigoRastreio": "<string>",
        "urlRastreio": "<string>"
      }
    }
  ]
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.shipment_groups` | `olist_shipment_group_id`, `group_name` |
| `olist_core.shipments` | `olist_shipment_id`, `order_id`, `status`, `tracking_code`, `tracking_url` |

## Separação

| Fase | Implementação |
|---|---|
| Extração | `GET /separacao/{idSeparacao}` |
| Transformação | mapear cabeçalho operacional; gerar itens da separação a partir de `itens[]` |
| Upsert | `separations` por `(tenant_id, olist_separation_id)` e `separation_items` por chave técnica |
| Refresh | sem mart dedicada nesta fase |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "situacao": "<integer>",
  "venda": { "id": "<integer|null>" },
  "itens": [
    {
      "produto": { "id": "<integer|null>" },
      "quantidade": "<number>"
    }
  ]
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.separations` | `olist_separation_id`, `status`, `order_id` |
| `olist_core.separation_items` | `separation_id`, `product_id`, `quantity` |

## CRM

| Fase | Implementação |
|---|---|
| Extração | `GET /crm/assuntos`, `GET /crm/assuntos/{idAssunto}`, `GET /crm/estagios` e endpoints filhos |
| Transformação | gravar assunto principal, estágios, ações, anotações e marcadores; resolver contato e estágio |
| Upsert | `crm_subjects`, `crm_stages`, `crm_actions`, `crm_notes`, `crm_markers` por chaves naturais |
| Refresh | `mv_crm_pipeline` |

Exemplo estrutural:

```json
{
  "id": "<integer>",
  "assunto": "<string>",
  "cliente": { "id": "<integer>" },
  "estagio": { "id": "<integer|null>" },
  "estrela": "<boolean>",
  "arquivado": "<boolean>",
  "dataAtualizacao": "<string|null>"
}
```

Destino:

| Tabela | Colunas principais |
|---|---|
| `olist_core.crm_subjects` | `olist_subject_id`, `subject_title`, `contact_id`, `crm_stage_id`, `is_starred`, `is_archived`, `source_updated_at` |
| `olist_core.crm_stages` | `olist_crm_stage_id`, `stage_name`, `pipeline_position` |
| `olist_core.crm_actions` | `olist_action_id`, `scheduled_at`, `action_status`, `completed_at` |
| `olist_core.crm_notes` | `olist_note_id`, `note_body` |
| `olist_core.crm_markers` | `marker_description`, `color_hex` |

## Referências

- Guia técnico: [olist_mapping_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide.md)
- Matriz consolidada: [olist_mapping_matrix_consolidated.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_matrix_consolidated.md)
