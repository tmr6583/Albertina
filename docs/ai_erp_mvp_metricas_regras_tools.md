# Matriz Do MVP De IA Para Consulta A Dados ERP

Documento operacional que consolida as métricas, regras funcionais, fontes de dados e tools do MVP da IA de consulta sobre o ERP no projeto `Albertina`.

## Objetivo

Traduzir o plano arquitetural em uma matriz executável para implementação do MVP, definindo:

- o que a IA deve responder
- de onde cada resposta vem
- qual regra funcional precisa ser aplicada
- qual tool deve atender cada pergunta
- quais pontos ainda dependem de validação de negócio

## Escopo Do MVP

- domínios incluídos: `vendas`, `estoque`, `financeiro`
- autenticação inicial: usuários internos
- camada de leitura preferencial: `olist_mart`
- mecanismo principal de consulta: `function calling`
- uso de `RAG`: complementar para explicações, glossário e regras

## Fontes Analíticas Base

- `olist_mart.vw_fact_orders`
- `olist_mart.vw_fact_order_items`
- `olist_mart.vw_fact_inventory`
- `olist_mart.vw_fact_receivables`
- `olist_mart.vw_fact_payables`
- `olist_mart.vw_dim_products`

## Convenções Da Matriz

- `status_regra = FECHADA`: pode seguir direto para implementação
- `status_regra = PENDENTE`: depende de validação funcional
- `fonte_primaria`: view ou tabela preferencial da consulta
- `tool_responsavel`: função controlada que a IA deve chamar
- `perfil`: perfil mínimo que deve poder acessar a informação

## Matriz De Métricas E Tools

| Dominio | Pergunta / Intencao | Metrica Ou Resposta | Fonte Primaria | Campos Principais | Regra Funcional Inicial | Tool Responsavel | Perfil | Status Regra |
|---|---|---|---|---|---|---|---|---|
| vendas | faturamento no periodo | soma de vendas | `olist_mart.vw_fact_orders` | `billing_date`, `total_order_amount`, `order_status`, `contact_name`, `vendor_name` | faturamento é a soma dos pedidos finalizados com notas fiscais autorizadas ou contas lançadas no período; tecnicamente, no modelo atual usar `sum(total_order_amount)` com `order_status = 1` e base temporal em `billing_date` | `consultar_resumo_vendas` | executivo, analista, operacional | FECHADA |
| vendas | quantidade de pedidos no periodo | total de pedidos | `olist_mart.vw_fact_orders` | `order_id`, `order_date`, `order_status` | contar pedidos distintos por filtro temporal | `consultar_resumo_vendas` | executivo, analista, operacional | FECHADA |
| vendas | ticket medio | valor medio por pedido | `olist_mart.vw_fact_orders` | `order_id`, `total_order_amount`, `order_date` | `sum(total_order_amount) / count(distinct order_id)` no filtro aplicado | `consultar_resumo_vendas` | executivo, analista | FECHADA |
| vendas | top clientes | clientes com maior compra | `olist_mart.vw_fact_orders` | `contact_id`, `contact_name`, `total_order_amount`, `order_date` | agrupar por cliente e ordenar por soma de `total_order_amount` | `consultar_top_clientes` | executivo, analista, operacional | FECHADA |
| vendas | top produtos por valor | produtos com maior venda em valor | `olist_mart.vw_fact_order_items` | `product_id`, `product_name`, `total_amount`, `order_date` | agrupar por produto e ordenar por soma de `total_amount` | `consultar_top_produtos` | executivo, analista, operacional | FECHADA |
| vendas | top produtos por quantidade | produtos com maior venda em volume | `olist_mart.vw_fact_order_items` | `product_id`, `product_name`, `quantity`, `order_date` | agrupar por produto e ordenar por soma de `quantity` | `consultar_top_produtos` | executivo, analista, operacional | FECHADA |
| vendas | evolucao de vendas | serie temporal de vendas | `olist_mart.vw_fact_orders` | `order_date`, `total_order_amount` | agrupar por dia, semana ou mes conforme filtro | `consultar_vendas_por_periodo` | executivo, analista | FECHADA |
| vendas | vendas por canal | faturamento por canal | `olist_mart.vw_fact_orders` | `order_origin_name`, `total_order_amount`, `order_date` | agrupar por `order_origin_name` | `consultar_vendas_por_canal` | executivo, analista | FECHADA |
| vendas | vendas por vendedor | faturamento por vendedor | `olist_mart.vw_fact_orders` | `vendor_id`, `vendor_name`, `total_order_amount`, `order_date` | agrupar por vendedor e ordenar por valor total | `consultar_vendas_por_vendedor` | executivo, analista, operacional | FECHADA |
| vendas | pedidos com filtro detalhado | lista detalhada de pedidos | `olist_mart.vw_fact_orders` | `order_number`, `contact_name`, `vendor_name`, `order_date`, `total_order_amount`, `order_status` | listar com paginação, filtros por data, cliente, vendedor, status e canal; exibir `order_status` com código e rótulo semântico | `consultar_pedidos` | analista, operacional | FECHADA |
| vendas | status do pedido | significado do status numerico | `olist_mart.vw_fact_orders` | `order_status` | usar a legenda oficial do Olist e exibir preferencialmente código + rótulo | `explicar_status_pedido` | analista, operacional | FECHADA |
| estoque | saldo por produto | estoque por item | `olist_mart.vw_fact_inventory` | `product_id`, `product_name`, `deposit_name`, `physical_qty`, `reserved_qty`, `available_qty` | listar saldo por produto e deposito | `consultar_estoque_produtos` | analista, operacional | FECHADA |
| estoque | produtos sem estoque | ruptura de estoque | `olist_mart.vw_fact_inventory` | `product_id`, `product_name`, `available_qty` | considerar ruptura quando `available_qty <= 0` | `consultar_ruptura_estoque` | analista, operacional | FECHADA |
| estoque | produtos com estoque baixo | risco de ruptura | `olist_mart.vw_fact_inventory` | `product_id`, `product_name`, `available_qty` | item em estoque baixo quando o saldo atual é igual ou inferior ao parâmetro de estoque mínimo do cadastro | `consultar_estoque_baixo` | analista, operacional | FECHADA |
| estoque | estoque por deposito | posicao de estoque por local | `olist_mart.vw_fact_inventory` | `deposit_id`, `deposit_name`, `available_qty`, `physical_qty`, `reserved_qty` | agrupar por deposito e consolidar saldos | `consultar_estoque_por_deposito` | analista, operacional | FECHADA |
| estoque | catalogo de produtos | dimensao de produto | `olist_mart.vw_dim_products` | `product_code`, `product_name`, `sku`, `gtin`, `product_type`, `category_name`, `brand_name`, `is_active` | consulta dimensional, com filtros por nome, codigo, marca e categoria | `consultar_produtos` | analista, operacional | FECHADA |
| financeiro | total a receber | valor bruto a receber | `olist_mart.vw_fact_receivables` | `issue_date`, `due_date`, `amount`, `open_amount`, `status`, `contact_name` | usar visão temporal conforme intenção da pergunta; para vencimento e atraso, a data oficial é `due_date`; para emissão, usar `issue_date` | `consultar_receber_resumo` | executivo, analista, operacional | FECHADA |
| financeiro | total em aberto a receber | saldo em aberto a receber | `olist_mart.vw_fact_receivables` | `open_amount`, `due_date`, `status`, `contact_name` | somar `open_amount` no filtro aplicado | `consultar_receber_resumo` | executivo, analista, operacional | FECHADA |
| financeiro | titulos vencidos a receber | inadimplencia / atraso | `olist_mart.vw_fact_receivables` | `due_date`, `open_amount`, `status`, `contact_name`, `invoice_number` | título vencido quando `due_date < hoje` e não há quitação; no MVP, aplicar `due_date < hoje` e `open_amount > 0` | `consultar_receber_vencidos` | executivo, analista, operacional | FECHADA |
| financeiro | clientes com maior saldo em aberto | concentracao de recebiveis | `olist_mart.vw_fact_receivables` | `contact_id`, `contact_name`, `open_amount` | agrupar por cliente e ordenar por soma de `open_amount` | `consultar_receber_por_cliente` | executivo, analista, operacional | FECHADA |
| financeiro | total a pagar | valor bruto a pagar | `olist_mart.vw_fact_payables` | `issue_date`, `due_date`, `amount`, `open_amount`, `status`, `contact_name` | usar visão temporal conforme intenção da pergunta; para vencimento e atraso, a data oficial é `due_date`; para emissão, usar `issue_date` | `consultar_pagar_resumo` | executivo, analista, operacional | FECHADA |
| financeiro | total em aberto a pagar | saldo em aberto a pagar | `olist_mart.vw_fact_payables` | `open_amount`, `due_date`, `status`, `contact_name` | somar `open_amount` no filtro aplicado | `consultar_pagar_resumo` | executivo, analista, operacional | FECHADA |
| financeiro | contas vencidas a pagar | atrasos com fornecedores | `olist_mart.vw_fact_payables` | `due_date`, `open_amount`, `status`, `contact_name` | título vencido quando `due_date < hoje` e não há quitação; no MVP, aplicar `due_date < hoje` e `open_amount > 0` | `consultar_pagar_vencidos` | executivo, analista, operacional | FECHADA |
| financeiro | fornecedores com maior valor a pagar | concentracao de pagaveis | `olist_mart.vw_fact_payables` | `contact_id`, `contact_name`, `open_amount` | agrupar por fornecedor e ordenar por soma de `open_amount` | `consultar_pagar_por_fornecedor` | executivo, analista, operacional | FECHADA |
| semantico | o que significa uma metrica | explicacao textual da metrica | `ai_metric_catalog`, `ai_business_glossary` | `metric_name`, `definition`, `formula`, `source_name`, `business_notes` | buscar definicao oficial, formula e fonte semantica | `explicar_metrica` | executivo, analista, operacional | PENDENTE |
| semantico | o que significa um termo do ERP | glossario de negocio | `ai_business_glossary` | `term`, `definition`, `aliases`, `domain` | buscar termo por nome ou sinonimo | `buscar_glossario` | executivo, analista, operacional | PENDENTE |

## Tools Do MVP

| Tool | Objetivo | Fonte Principal | Parametros Minimos | Saida Esperada |
|---|---|---|---|---|
| `consultar_resumo_vendas` | responder faturamento, pedidos e ticket medio | `olist_mart.vw_fact_orders` | periodo, agrupamento opcional, filtros de canal, vendedor, cliente | resumo textual, totais, tabela agregada, filtros aplicados |
| `consultar_vendas_por_periodo` | responder serie temporal de vendas | `olist_mart.vw_fact_orders` | periodo, granularidade, filtros opcionais | serie temporal, resumo textual, comparativos |
| `consultar_top_clientes` | listar clientes que mais compram | `olist_mart.vw_fact_orders` | periodo, limite, ordenacao, filtros opcionais | ranking, valor total, quantidade de pedidos |
| `consultar_top_produtos` | listar produtos mais vendidos por valor ou quantidade | `olist_mart.vw_fact_order_items` | periodo, criterio, limite, filtros opcionais | ranking, valor, quantidade, produto |
| `consultar_vendas_por_canal` | consolidar vendas por origem | `olist_mart.vw_fact_orders` | periodo, limite, filtros opcionais | tabela por canal, valor, participacao |
| `consultar_vendas_por_vendedor` | consolidar vendas por vendedor | `olist_mart.vw_fact_orders` | periodo, limite, filtros opcionais | tabela por vendedor, valor, pedidos |
| `consultar_pedidos` | listar pedidos detalhados | `olist_mart.vw_fact_orders` | filtros, pagina, limite | tabela detalhada, totais, filtros |
| `explicar_status_pedido` | explicar status numerico e seu significado | catalogo semantico + mapeamento funcional | status ou pedido | definicao textual, regra, observacao |
| `consultar_estoque_produtos` | listar saldo de estoque por produto | `olist_mart.vw_fact_inventory` | produto opcional, deposito opcional, pagina, limite | tabela de saldos, resumo por produto |
| `consultar_ruptura_estoque` | listar itens sem saldo disponivel | `olist_mart.vw_fact_inventory` | filtros opcionais, pagina, limite | lista de ruptura, deposito, saldo |
| `consultar_estoque_baixo` | listar itens abaixo do minimo | `olist_mart.vw_fact_inventory` | threshold ou regra configurada, filtros opcionais | lista de risco, saldo atual, limiar |
| `consultar_estoque_por_deposito` | consolidar estoque por deposito | `olist_mart.vw_fact_inventory` | filtros opcionais | totais por deposito |
| `consultar_produtos` | consultar catalogo de produtos | `olist_mart.vw_dim_products` | nome, codigo, sku, marca, categoria, ativo | lista de produtos e atributos |
| `consultar_receber_resumo` | consolidar recebiveis | `olist_mart.vw_fact_receivables` | periodo, base temporal, filtros opcionais | totais, abertos, recebidos, resumo textual |
| `consultar_receber_vencidos` | listar recebiveis vencidos | `olist_mart.vw_fact_receivables` | data de referencia, filtros opcionais | lista de vencidos, cliente, valor em aberto |
| `consultar_receber_por_cliente` | agrupar recebiveis por cliente | `olist_mart.vw_fact_receivables` | periodo opcional, limite, filtros | ranking de clientes com saldo aberto |
| `consultar_pagar_resumo` | consolidar pagaveis | `olist_mart.vw_fact_payables` | periodo, base temporal, filtros opcionais | totais, abertos, pagos, resumo textual |
| `consultar_pagar_vencidos` | listar pagaveis vencidos | `olist_mart.vw_fact_payables` | data de referencia, filtros opcionais | lista de vencidos, fornecedor, valor em aberto |
| `consultar_pagar_por_fornecedor` | agrupar pagaveis por fornecedor | `olist_mart.vw_fact_payables` | periodo opcional, limite, filtros | ranking de fornecedores com saldo aberto |
| `explicar_metrica` | explicar formula, regra e fonte de metrica | `ai_metric_catalog` | nome da metrica | definicao, formula, fonte, observacoes |
| `buscar_glossario` | recuperar termos e sinonimos de negocio | `ai_business_glossary` | termo | definicao, sinonimos, dominio |

## Contrato Base Das Tools

Todas as tools do MVP devem seguir um contrato comum de resposta:

- `resumo_textual`
- `tabela_resultado`
- `metricas_resumidas`
- `filtros_aplicados`
- `fonte_consultada`
- `data_referencia`
- `perfil_considerado`
- `observacoes_de_regra`

## Regras De Seguranca Para Todas As Tools

- toda tool deve receber contexto de usuário autenticado
- toda tool deve aplicar escopo por `tenant_id`
- nenhuma tool deve permitir SQL arbitrario
- limites de paginação devem ser obrigatorios
- filtros textuais devem ser saneados
- toda execução deve registrar auditoria em `ai_query_audit`

## Estrutura Recomendada Das Tabelas Semanticas

### `ai_metric_catalog`

Campos recomendados:

- `metric_id`
- `tenant_id`
- `metric_name`
- `domain`
- `definition`
- `formula_description`
- `source_schema`
- `source_object`
- `time_basis`
- `status`
- `owner_area`
- `created_at`
- `updated_at`

### `ai_business_glossary`

Campos recomendados:

- `term_id`
- `tenant_id`
- `term`
- `aliases`
- `domain`
- `definition`
- `business_notes`
- `source_reference`
- `created_at`
- `updated_at`

### `ai_query_templates`

Campos recomendados:

- `template_id`
- `tenant_id`
- `tool_name`
- `intent_name`
- `template_description`
- `allowed_filters`
- `default_limit`
- `response_shape`
- `created_at`
- `updated_at`

### `ai_query_audit`

Campos recomendados:

- `audit_id`
- `tenant_id`
- `user_id`
- `session_id`
- `tool_name`
- `question_text`
- `normalized_intent`
- `filters_json`
- `result_summary`
- `row_count`
- `started_at`
- `finished_at`
- `status`

## Enums Oficiais Identificados Na Documentacao Olist

### `order_status` de pedidos

Conforme documentação oficial do Olist para `pedidos`, os códigos de situação identificados são:

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

### `status` de contas a receber e contas a pagar

Conforme documentação oficial do Olist para `contas-receber` e `contas-pagar`, os estados identificados são:

| Valor | Significado |
|---|---|
| `aberto` | Aberto |
| `cancelada` | Cancelada |
| `pago` | Pago |
| `parcial` | Parcial |
| `prevista` | Prevista |
| `atrasadas` | Atrasadas |
| `emissao` | Emissao |

## Validacoes Funcionais Obtidas No Ecossistema Olist

As definições abaixo foram consolidadas a partir de interação direta com a IA do Olist ERP, em modo conceitual, para esclarecer regras de negócio do MVP:

- `faturamento`: soma dos pedidos finalizados com notas fiscais autorizadas ou contas lançadas no período
- data de referência em vendas: usar a data de finalização do pedido para contabilizar o faturamento efetivo
- `vencidos`: título com data de vencimento anterior à data atual e sem registro de quitação
- `estoque baixo`: item com saldo atual igual ou inferior ao parâmetro de estoque mínimo do cadastro

## Validacoes Tecnicas No Modelo Atual

As verificações abaixo foram feitas diretamente no banco e no código atual do Albertina:

- `order_date` é mapeado do campo Olist `data`
- `billing_date` é mapeado do campo Olist `dataFaturamento`
- no dataset atual, todos os pedidos com `order_status = 1` possuem `billing_date` preenchido e `olist_invoice_id` informado
- no dataset atual, os pedidos com `order_status = 0` não possuem `billing_date`
- conclusão técnica do MVP: para métricas de faturamento efetivo, usar `billing_date` e filtrar `order_status = 1`
- o estoque mínimo existe hoje em `olist_core.products.raw_attributes -> estoque -> minimo`
- o estoque mínimo ainda não está normalizado em coluna dedicada nem exposto na `MART`
- no dataset atual, apenas parte dos produtos já traz o objeto `estoque` com `minimo`, portanto será necessária evolução de modelagem para tornar a regra completa e estável

## Pendencias Funcionais Imediatas

As definições abaixo devem ser validadas antes de fechar a implementação completa do MVP:

1. `faturamento`
   - materializar a regra de faturamento efetivo nas tools e, idealmente, em visão analítica própria

2. base temporal de vendas
   - `order_date` não representa a finalização; para faturamento usar `billing_date`
   - avaliar se vale criar um campo derivado ou uma view específica para deixar isso explícito

3. títulos vencidos
   - decidir se haverá filtro complementar por `status` além de `open_amount > 0`

4. estoque baixo
   - normalizar `raw_attributes -> estoque -> minimo` em coluna ou visão analítica dedicada
   - avaliar cobertura real do campo nos produtos já sincronizados

5. exibição de status do pedido
   - padronizar no frontend e nas tools se a saída mostrará sempre código + rótulo

## Ordem Recomendada De Implementacao

1. validar pendencias funcionais
2. criar tabelas semanticas da IA
3. implementar catálogo de métricas e glossário
4. criar tools de `vendas`
5. criar tools de `estoque`
6. criar tools de `financeiro`
7. implementar auditoria das consultas
8. conectar `RAG` para explicações e glossário

## Resultado Esperado Desta Matriz

Este documento deve servir como ponte entre arquitetura, modelagem de dados e implementação das tools, permitindo que o MVP seja construído com:

- escopo claro
- fontes oficiais
- regras explícitas
- segurança previsível
- backlog técnico diretamente acionável
