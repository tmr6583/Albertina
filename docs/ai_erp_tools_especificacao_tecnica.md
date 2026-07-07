# Especificacao Tecnica Das Tools Da IA

Documento técnico que define o catálogo inicial de tools da IA, seus contratos de entrada e saída e as regras operacionais para implementação no backend do projeto `Albertina`.

## Objetivo

Estabelecer um catálogo controlado de funções que o modelo pode chamar para responder perguntas sobre o ERP com:

- precisão numérica
- segurança por `tenant`
- auditoria
- contratos previsíveis
- compatibilidade com `FastAPI`, `OpenAI` e `LangChain`

## Princípios Das Tools

- toda tool deve ser determinística
- toda tool deve operar com escopo explícito de `tenant_id`
- nenhuma tool deve aceitar SQL livre
- toda tool deve validar parâmetros e limites
- toda tool deve registrar auditoria
- toda tool deve declarar claramente sua fonte analítica principal

## Contrato Base Comum

Todas as tools devem receber um contexto técnico interno, além dos parâmetros funcionais.

### Contexto Técnico Interno

| Campo | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `tenant_id` | `string(uuid)` | sim | tenant autenticado |
| `user_id` | `string(uuid)` | sim | usuário autenticado |
| `user_profile` | `string` | sim | perfil como `executivo`, `operacional`, `analista`, `admin` |
| `session_id` | `string` | não | identificador da conversa |
| `request_id` | `string` | não | identificador da requisição |

### Estrutura Base De Entrada

```json
{
  "tenant_id": "uuid",
  "user_id": "uuid",
  "user_profile": "analista",
  "session_id": "string-opcional",
  "request_id": "string-opcional",
  "filters": {},
  "options": {}
}
```

### Estrutura Base De Saida

```json
{
  "summary_text": "texto objetivo com a resposta principal",
  "result_table": [],
  "summary_metrics": {},
  "applied_filters": {},
  "source": {
    "schema": "olist_mart",
    "object": "vw_fact_orders"
  },
  "reference_timestamp": "2026-07-07T00:00:00Z",
  "observations": [],
  "audit": {
    "tool_name": "consultar_resumo_vendas",
    "status": "success"
  }
}
```

## Regras Gerais De Validacao

- limites máximos devem ser aplicados em listas e rankings
- datas devem ser validadas e normalizadas
- filtros por texto devem ser saneados
- filtros ausentes devem usar defaults previsíveis
- perfis sem permissão devem receber bloqueio explícito

## Catálogo Inicial De Tools

## 1. `consultar_resumo_vendas`

### Finalidade

Responder perguntas sobre faturamento, quantidade de pedidos e ticket médio.

### Fonte Principal

- `olist_mart.vw_fact_orders`

### Entrada Funcional

```json
{
  "filters": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "vendor_name": "string-opcional",
    "contact_name": "string-opcional",
    "order_origin_name": "string-opcional"
  },
  "options": {
    "time_basis": "billing_date",
    "include_breakdown": true
  }
}
```

### Saida Esperada

```json
{
  "summary_text": "No período informado, o faturamento foi X, com Y pedidos e ticket médio de Z.",
  "summary_metrics": {
    "gross_sales": 0,
    "orders_count": 0,
    "average_ticket": 0
  },
  "result_table": []
}
```

### Observacoes

- faturamento deve refletir a soma dos pedidos finalizados com notas fiscais autorizadas ou contas lançadas no período
- a base temporal padrão do MVP para faturamento deve usar `billing_date`
- no modelo atual, a melhor proxy técnica de pedido finalizado é `order_status = 1`

## 2. `consultar_vendas_por_periodo`

### Finalidade

Gerar série temporal de vendas.

### Fonte Principal

- `olist_mart.vw_fact_orders`

### Entrada Funcional

```json
{
  "filters": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  },
  "options": {
    "granularity": "day",
    "metric": "gross_sales",
    "time_basis": "billing_date"
  }
}
```

### Saida Esperada

```json
{
  "summary_text": "As vendas apresentaram a seguinte evolução no período.",
  "summary_metrics": {
    "gross_sales_total": 0
  },
  "result_table": [
    {
      "period": "2026-07-01",
      "gross_sales": 0
    }
  ]
}
```

## 3. `consultar_top_clientes`

### Finalidade

Rankear clientes por volume de compra.

### Fonte Principal

- `olist_mart.vw_fact_orders`

### Entrada Funcional

```json
{
  "filters": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  },
  "options": {
    "limit": 10,
    "sort_by": "gross_sales"
  }
}
```

## 4. `consultar_top_produtos`

### Finalidade

Rankear produtos por valor ou quantidade.

### Fonte Principal

- `olist_mart.vw_fact_order_items`

### Entrada Funcional

```json
{
  "filters": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  },
  "options": {
    "limit": 10,
    "ranking_mode": "value"
  }
}
```

## 5. `consultar_vendas_por_canal`

### Finalidade

Consolidar vendas por canal de origem.

### Fonte Principal

- `olist_mart.vw_fact_orders`

### Entrada Funcional

```json
{
  "filters": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  },
  "options": {
    "limit": 20
  }
}
```

## 6. `consultar_vendas_por_vendedor`

### Finalidade

Consolidar vendas por vendedor.

### Fonte Principal

- `olist_mart.vw_fact_orders`

## 7. `consultar_pedidos`

### Finalidade

Listar pedidos detalhados com paginação e filtros.

### Fonte Principal

- `olist_mart.vw_fact_orders`

### Entrada Funcional

```json
{
  "filters": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "order_status": 1,
    "contact_name": "string-opcional",
    "vendor_name": "string-opcional",
    "order_origin_name": "string-opcional"
  },
  "options": {
    "page": 1,
    "limit": 50
  }
}
```

## 8. `explicar_status_pedido`

### Finalidade

Explicar o significado do `order_status` com base na documentação oficial do Olist.

### Fonte Principal

- catálogo semântico interno preenchido a partir da documentação oficial do ERP

### Enum Oficial Identificado

| Codigo | Significado |
|---|---|
| `0` | Aberta |
| `1` | Faturada |
| `2` | Cancelada |
| `3` | Aprovada |
| `4` | Preparando Envio |
| `5` | Enviada |
| `6` | Entregue |
| `7` | Pronto Envio |
| `8` | Dados Incompletos |
| `9` | Nao Entregue |

## 9. `consultar_estoque_produtos`

### Finalidade

Consultar posição de estoque por item.

### Fonte Principal

- `olist_mart.vw_fact_inventory`

### Entrada Funcional

```json
{
  "filters": {
    "product_name": "string-opcional",
    "product_code": "string-opcional",
    "deposit_name": "string-opcional"
  },
  "options": {
    "page": 1,
    "limit": 50
  }
}
```

## 10. `consultar_ruptura_estoque`

### Finalidade

Listar produtos sem saldo disponível.

### Regra Inicial

- `available_qty <= 0`

## 11. `consultar_estoque_baixo`

### Finalidade

Listar produtos abaixo do limiar mínimo configurado.

### Observacoes

- a regra funcional é: item em nível baixo quando o saldo atual é igual ou inferior ao parâmetro de estoque mínimo do cadastro
- a implementação depende de validar onde o estoque mínimo está armazenado no banco analítico ou relacional

## 12. `consultar_estoque_por_deposito`

### Finalidade

Consolidar posição de estoque por depósito.

### Fonte Principal

- `olist_mart.vw_fact_inventory`

## 13. `consultar_produtos`

### Finalidade

Consultar o catálogo de produtos.

### Fonte Principal

- `olist_mart.vw_dim_products`

## 14. `consultar_receber_resumo`

### Finalidade

Consolidar recebíveis por período e visão temporal.

### Fonte Principal

- `olist_mart.vw_fact_receivables`

### Status Oficiais Identificados

| Valor | Significado |
|---|---|
| `aberto` | Aberto |
| `cancelada` | Cancelada |
| `pago` | Pago |
| `parcial` | Parcial |
| `prevista` | Prevista |
| `atrasadas` | Atrasadas |
| `emissao` | Emissao |

## 15. `consultar_receber_vencidos`

### Finalidade

Listar títulos vencidos a receber.

### Regra Inicial

- título vencido quando `due_date < data_referencia` e não há registro de quitação; no MVP, materializar como `open_amount > 0`

### Observacoes

- avaliar se o `status` será usado como filtro complementar ou apenas como atributo descritivo

## 16. `consultar_receber_por_cliente`

### Finalidade

Agrupar saldo em aberto por cliente.

### Fonte Principal

- `olist_mart.vw_fact_receivables`

## 17. `consultar_pagar_resumo`

### Finalidade

Consolidar pagáveis por período e visão temporal.

### Fonte Principal

- `olist_mart.vw_fact_payables`

## 18. `consultar_pagar_vencidos`

### Finalidade

Listar contas vencidas a pagar.

### Regra Inicial

- título vencido quando `due_date < data_referencia` e não há registro de quitação; no MVP, materializar como `open_amount > 0`

## Validacoes Funcionais Obtidas No Olist

As definições abaixo foram esclarecidas em interação conceitual com a IA oficial do Olist ERP:

- faturamento: soma dos pedidos finalizados com notas fiscais autorizadas ou contas lançadas no período
- data de referência em vendas: data de finalização do pedido
- vencidos: data de vencimento anterior à data atual sem baixa
- estoque baixo: saldo atual igual ou inferior ao estoque mínimo cadastrado

## Validacoes Tecnicas No Albertina

As validações abaixo foram verificadas no código e no banco atuais:

- `order_date` é derivado do campo Olist `data`
- `billing_date` é derivado do campo Olist `dataFaturamento`
- no dataset atual, `order_status = 1` está associado a `billing_date` preenchido e `olist_invoice_id` informado
- o estoque mínimo existe apenas em `olist_core.products.raw_attributes -> estoque -> minimo`
- o estoque mínimo ainda não está exposto em `olist_mart.vw_dim_products` nem em `olist_mart.vw_fact_inventory`

## 19. `consultar_pagar_por_fornecedor`

### Finalidade

Agrupar saldo em aberto por fornecedor.

### Fonte Principal

- `olist_mart.vw_fact_payables`

## 20. `explicar_metrica`

### Finalidade

Explicar a definição funcional, fórmula e origem de uma métrica.

### Fonte Principal

- `olist_ai.ai_metric_catalog`

## 21. `buscar_glossario`

### Finalidade

Recuperar definição de termos de negócio e sinônimos.

### Fonte Principal

- `olist_ai.ai_business_glossary`

## Padrao De Erro Das Tools

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Parametro invalido.",
    "details": {
      "field": "start_date"
    }
  }
}
```

## Padrao De Auditoria

Para cada execução, registrar em `olist_ai.ai_query_audit`:

- usuário
- tenant
- tool chamada
- intenção normalizada
- filtros aplicados
- objeto consultado
- resumo da resposta
- status final

## Regras De Seguranca Por Perfil

### `executivo`

- acesso a resumos, rankings e consolidados
- não deve receber listagens massivas por padrão

### `operacional`

- acesso a consultas detalhadas e listas paginadas
- pode consultar pedidos, estoque e títulos individualizados conforme escopo

### `analista`

- acesso a resumos e detalhamentos controlados
- pode cruzar filtros mais amplos que o perfil executivo

### `admin`

- acesso administrativo à governança da IA
- não implica exposição irrestrita sem `tenant_id`

## Estrutura Recomendada No Backend

Organização sugerida:

- `app/ai/tools/sales.py`
- `app/ai/tools/inventory.py`
- `app/ai/tools/finance.py`
- `app/ai/tools/semantic.py`
- `app/ai/contracts.py`
- `app/ai/router.py`
- `app/ai/audit.py`
- `app/ai/guards.py`

## Ordem Recomendada De Implementacao

1. implementar contratos base em `contracts.py`
2. implementar camada de guards e validação
3. implementar tools de `vendas`
4. implementar tools de `estoque`
5. implementar tools de `financeiro`
6. implementar tools semânticas
7. integrar auditoria
8. integrar roteamento por intenção

## Resultado Esperado

Ao final desta etapa, o backend terá um catálogo formal de tools que poderá ser exposto ao modelo com segurança e previsibilidade, servindo como base estável para o MVP de IA do `Albertina`.
