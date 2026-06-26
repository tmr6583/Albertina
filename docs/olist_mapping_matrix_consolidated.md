# Matriz Consolidada De Mapeamento Olist ERP -> Banco

Planilha Markdown única com o mapeamento consolidado entre campos da API Olist ERP e colunas de destino no banco `Albertina`.

## Colunas

| Coluna | Descrição |
|---|---|
| `Dominio` | Agrupamento funcional |
| `Entidade` | Entidade de negócio |
| `Endpoint` | Endpoint oficial consultado |
| `Campo Olist` | Campo publicado na documentação |
| `Tabela Destino` | Tabela no Supabase/PostgreSQL |
| `Coluna Destino` | Coluna de persistência |
| `Transformacao` | Regra de carga |
| `Cobertura` | Nível de fechamento atual |

## Planilha

| Dominio | Entidade | Endpoint | Campo Olist | Tabela Destino | Coluna Destino | Transformacao | Cobertura |
|---|---|---|---|---|---|---|---|
| Cadastros | Contatos | `GET /contatos` | `nome` | `olist_core.contacts` | `contact_name` | cópia direta | FULL |
| Cadastros | Contatos | `GET /contatos` | `codigo` | `olist_core.contacts` | `contact_code` | cópia direta | FULL |
| Cadastros | Contatos | `GET /contatos` | `fantasia` | `olist_core.contacts` | `trade_name` | cópia direta | FULL |
| Cadastros | Contatos | `GET /contatos` | `tipoPessoa` | `olist_core.contacts` | `person_type` | manter enum | FULL |
| Cadastros | Contatos | `GET /contatos` | `cpfCnpj` | `olist_core.contacts` | `cpf_cnpj` | cópia direta | FULL |
| Cadastros | Contatos | `GET /contatos` | `inscricaoEstadual` | `olist_core.contacts` | `state_registration` | cópia direta | FULL |
| Cadastros | Contatos | `GET /contatos` | `telefone` | `olist_core.contacts` | `phone` | cópia direta | FULL |
| Cadastros | Contatos | `GET /contatos` | `celular` | `olist_core.contacts` | `mobile` | cópia direta | FULL |
| Cadastros | Contatos | `GET /contatos` | `email` | `olist_core.contacts` | `email` | cópia direta | FULL |
| Cadastros | Contatos | `GET /contatos` | `endereco` | `olist_core.contacts` | `source_payload` | preservar subobjeto | PARTIAL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `id` | `olist_core.orders` | `olist_order_id` | chave natural | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `numeroPedido` | `olist_core.orders` | `order_number` | cópia direta | FULL |
| Vendas | Pedidos | `GET /pedidos` | `situacao` | `olist_core.orders` | `order_status` | manter código Olist | FULL |
| Vendas | Pedidos | `GET /pedidos` | `origemPedido` | `olist_core.orders` | `order_origin` | manter código Olist | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `data` | `olist_core.orders` | `order_date` | converter para `DATE` | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `dataFaturamento` | `olist_core.orders` | `billing_date` | converter para `TIMESTAMPTZ` | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `valorTotalProdutos` | `olist_core.orders` | `total_products_amount` | numérico | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `valorTotalPedido` | `olist_core.orders` | `total_order_amount` | numérico | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `valorFrete` | `olist_core.orders` | `freight_amount` | numérico | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `cliente.id` | `olist_core.orders` | `contact_id` | resolver por chave externa | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `vendedor.id` | `olist_core.orders` | `vendor_id` | resolver por chave externa | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `itens[]` | `olist_core.order_items` | `source_payload` | rehidratação por pedido | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `pagamento.parcelas[]` | `olist_core.order_installments` | `source_payload` | rehidratação por pedido | FULL |
| Vendas | Pedidos | `GET /pedidos/{idPedido}` | `pagamentosIntegrados[]` | `olist_core.order_integrated_payments` | `source_payload` | rehidratação por pedido | FULL |
| Catalogo | Produtos | `GET /produtos` | `id` | `olist_core.products` | `olist_product_id` | chave natural | FULL |
| Catalogo | Produtos | `GET /produtos` | `sku` | `olist_core.products` | `sku` | cópia direta | FULL |
| Catalogo | Produtos | `GET /produtos` | `descricao` | `olist_core.products` | `product_name` | cópia direta | FULL |
| Catalogo | Produtos | `GET /produtos` | `tipo` | `olist_core.products` | `product_type` | manter enum | FULL |
| Catalogo | Produtos | `GET /produtos` | `dataAlteracao` | `olist_core.products` | `source_updated_at` | watermark candidato | FULL |
| Catalogo | Produtos | `GET /produtos` | `gtin` | `olist_core.products` | `gtin` | cópia direta | FULL |
| Catalogo | Produtos | `GET /produtos` | `precos.preco` | `olist_core.products` | `raw_attributes` | preservar em JSONB | PARTIAL |
| Catalogo | Produtos | `GET /produtos` | `estoque.localizacao` | `olist_core.products` | `raw_attributes` | preservar em JSONB | PARTIAL |
| Fiscal | Notas fiscais | `GET /notas` | `id` | `olist_core.invoices` | `olist_invoice_id` | chave natural | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `situacao` | `olist_core.invoices` | `invoice_status` | cópia direta | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `tipo` | `olist_core.invoices` | `invoice_type` | cópia direta | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `numero` | `olist_core.invoices` | `invoice_number` | cópia direta | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `serie` | `olist_core.invoices` | `invoice_series` | cópia direta | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `chaveAcesso` | `olist_core.invoices` | `access_key` | cópia direta | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `dataEmissao` | `olist_core.invoices` | `issued_at` | converter para `TIMESTAMPTZ` | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `valor` | `olist_core.invoices` | `total_amount` | numérico | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `codigoRastreamento` | `olist_core.invoices` | `tracking_code` | cópia direta | FULL |
| Fiscal | Notas fiscais | `GET /notas` | `urlRastreamento` | `olist_core.invoices` | `tracking_url` | cópia direta | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `id` | `olist_core.accounts_receivable` | `olist_ar_id` | chave natural | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `situacao` | `olist_core.accounts_receivable` | `status` | cópia direta | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `data` | `olist_core.accounts_receivable` | `issue_date` | converter para `DATE` | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `dataVencimento` | `olist_core.accounts_receivable` | `due_date` | converter para `DATE` | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `historico` | `olist_core.accounts_receivable` | `notes` | texto livre | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `valor` | `olist_core.accounts_receivable` | `amount` | numérico | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `saldo` | `olist_core.accounts_receivable` | `open_amount` | numérico | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `numeroDocumento` | `olist_core.accounts_receivable` | `document_number` | cópia direta | FULL |
| Financeiro | Contas a receber | `GET /contas-receber` | `cliente.id` | `olist_core.accounts_receivable` | `contact_id` | resolver por chave externa | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `id` | `olist_core.accounts_payable` | `olist_ap_id` | chave natural | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `situacao` | `olist_core.accounts_payable` | `status` | cópia direta | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `data` | `olist_core.accounts_payable` | `issue_date` | converter para `DATE` | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `dataVencimento` | `olist_core.accounts_payable` | `due_date` | converter para `DATE` | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `historico` | `olist_core.accounts_payable` | `notes` | texto livre | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `valor` | `olist_core.accounts_payable` | `amount` | numérico | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `saldo` | `olist_core.accounts_payable` | `open_amount` | numérico | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `numeroDocumento` | `olist_core.accounts_payable` | `document_number` | cópia direta | FULL |
| Financeiro | Contas a pagar | `GET /contas-pagar` | `cliente.id` | `olist_core.accounts_payable` | `contact_id` | resolver por chave externa | FULL |
| Estoque | Saldo de estoque | `GET /estoque/{idProduto}` | `id` | `olist_core.stock_balances` | `product_id` | resolver por chave externa | FULL |
| Estoque | Saldo de estoque | `GET /estoque/{idProduto}` | `saldo` | `olist_core.stock_balances` | `physical_qty` | numérico | FULL |
| Estoque | Saldo de estoque | `GET /estoque/{idProduto}` | `reservado` | `olist_core.stock_balances` | `reserved_qty` | numérico | FULL |
| Estoque | Saldo de estoque | `GET /estoque/{idProduto}` | `disponivel` | `olist_core.stock_balances` | `available_qty` | numérico | FULL |
| Estoque | Saldo por depósito | `GET /estoque/{idProduto}` | `depositos[].id` | `olist_core.stock_balances` | `deposit_id` | resolver por chave externa | FULL |
| Estoque | Saldo por depósito | `GET /estoque/{idProduto}` | `depositos[].saldo` | `olist_core.stock_balances` | `physical_qty` | linha por depósito | FULL |
| Estoque | Depósito | `GET /estoque/{idProduto}` | `depositos[].nome` | `olist_core.deposits` | `deposit_name` | cópia direta | FULL |
| Logistica | Agrupamento de expedição | `GET /expedicao/{idAgrupamento}` | `id` | `olist_core.shipment_groups` | `olist_shipment_group_id` | chave natural | FULL |
| Logistica | Agrupamento de expedição | `GET /expedicao/{idAgrupamento}` | `identificacao` | `olist_core.shipment_groups` | `group_name` | cópia direta | FULL |
| Logistica | Expedição | `GET /expedicao/{idAgrupamento}` | `expedicoes[].id` | `olist_core.shipments` | `olist_shipment_id` | chave natural | FULL |
| Logistica | Expedição | `GET /expedicao/{idAgrupamento}` | `expedicoes[].situacao` | `olist_core.shipments` | `status` | cópia direta | FULL |
| Logistica | Expedição | `GET /expedicao/{idAgrupamento}` | `expedicoes[].venda.id` | `olist_core.shipments` | `order_id` | resolver por chave externa | FULL |
| Logistica | Expedição | `GET /expedicao/{idAgrupamento}` | `expedicoes[].logistica.codigoRastreio` | `olist_core.shipments` | `tracking_code` | cópia direta | FULL |
| Logistica | Expedição | `GET /expedicao/{idAgrupamento}` | `expedicoes[].logistica.urlRastreio` | `olist_core.shipments` | `tracking_url` | cópia direta | FULL |
| Logistica | Expedição | `GET /expedicao/{idAgrupamento}` | `expedicoes[].logistica.formaFrete.id` | `olist_core.shipments` | `freight_method_id` | resolver por chave externa | FULL |
| Logistica | Expedição | `GET /expedicao/{idAgrupamento}` | `expedicoes[].volume.pesoBruto` | `olist_core.shipments` | `source_payload` | preservar em JSONB | PARTIAL |
| Logistica | Separação | `GET /separacao/{idSeparacao}` | `id` | `olist_core.separations` | `olist_separation_id` | chave natural | FULL |
| Logistica | Separação | `GET /separacao/{idSeparacao}` | `situacao` | `olist_core.separations` | `status` | cópia direta | FULL |
| Logistica | Separação | `GET /separacao/{idSeparacao}` | `idUsuarioEmbalador` | `olist_core.separations` | `packed_by_olist_user_id` | cópia direta | FULL |
| Logistica | Separação | `GET /separacao/{idSeparacao}` | `objOrigem` | `olist_core.separations` | `origin_type` | cópia direta | FULL |
| Logistica | Separação | `GET /separacao/{idSeparacao}` | `dataCriacao` | `olist_core.separations` | `issued_at` | converter para `TIMESTAMPTZ` | FULL |
| Logistica | Separação | `GET /separacao/{idSeparacao}` | `venda.id` | `olist_core.separations` | `order_id` | resolver por chave externa | FULL |
| Logistica | Itens da separação | `GET /separacao/{idSeparacao}` | `itens[].produto.id` | `olist_core.separation_items` | `product_id` | resolver por chave externa | FULL |
| Logistica | Itens da separação | `GET /separacao/{idSeparacao}` | `itens[].quantidade` | `olist_core.separation_items` | `quantity` | numérico | FULL |
| CRM | Assunto | `GET /crm/assuntos` | `id` | `olist_core.crm_subjects` | `olist_subject_id` | chave natural | FULL |
| CRM | Assunto | `GET /crm/assuntos` | `assunto` | `olist_core.crm_subjects` | `subject_title` | cópia direta | FULL |
| CRM | Assunto | `GET /crm/assuntos` | `cliente.id` | `olist_core.crm_subjects` | `contact_id` | resolver por chave externa | FULL |
| CRM | Assunto | `GET /crm/assuntos` | `cliente.statusCrm` | `olist_core.crm_subjects` | `subject_status` | cópia direta | FULL |
| CRM | Assunto | `GET /crm/assuntos` | `estagio.id` | `olist_core.crm_subjects` | `crm_stage_id` | resolver por chave externa | FULL |
| CRM | Assunto | `GET /crm/assuntos` | `estrela` | `olist_core.crm_subjects` | `is_starred` | boolean | FULL |
| CRM | Assunto | `GET /crm/assuntos` | `arquivado` | `olist_core.crm_subjects` | `is_archived` | boolean | FULL |
| CRM | Assunto | `GET /crm/assuntos` | `dataAtualizacao` | `olist_core.crm_subjects` | `source_updated_at` | watermark candidato | FULL |
| CRM | Estágio | `GET /crm/estagios` | `items.id` | `olist_core.crm_stages` | `olist_crm_stage_id` | chave natural | FULL |
| CRM | Estágio | `GET /crm/estagios` | `items.descricao` | `olist_core.crm_stages` | `stage_name` | cópia direta | FULL |
| CRM | Estágio | `GET /crm/estagios` | `items.ordem` | `olist_core.crm_stages` | `pipeline_position` | cópia direta | FULL |
| CRM | Ação | `GET /crm/assuntos/{idAssunto}/acoes` | `itens[].id` | `olist_core.crm_actions` | `olist_action_id` | chave natural | FULL |
| CRM | Ação | `GET /crm/assuntos/{idAssunto}/acoes` | `itens[].descricao` | `olist_core.crm_actions` | `action_type` | cópia direta operacional | FULL |
| CRM | Ação | `GET /crm/assuntos/{idAssunto}/acoes` | `itens[].data` | `olist_core.crm_actions` | `scheduled_at` | converter para `TIMESTAMPTZ` | FULL |
| CRM | Ação | `GET /crm/assuntos/{idAssunto}/acoes` | `itens[].acaoConcluida` | `olist_core.crm_actions` | `action_status` | derivar pendente/concluida | FULL |
| CRM | Ação | `GET /crm/assuntos/{idAssunto}/acoes` | `itens[].dataConcluida` | `olist_core.crm_actions` | `completed_at` | converter para `TIMESTAMPTZ` | FULL |
| CRM | Anotação | `GET /crm/assuntos/{idAssunto}/anotacoes` | `itens[].id` | `olist_core.crm_notes` | `olist_note_id` | chave natural | FULL |
| CRM | Anotação | `GET /crm/assuntos/{idAssunto}/anotacoes` | `itens[].anotacao` | `olist_core.crm_notes` | `note_body` | cópia direta | FULL |
| CRM | Marcador | `GET /crm/assuntos/{idAssunto}/marcadores` | `items.descricao` | `olist_core.crm_markers` | `marker_description` | cópia direta | FULL |
| CRM | Marcador | `GET /crm/assuntos/{idAssunto}/marcadores` | `items.cor` | `olist_core.crm_markers` | `color_hex` | cópia direta | FULL |

## Referências

- Guia técnico: [olist_mapping_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide.md)
- Guia de ETL: [olist_etl_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_etl_guide.md)
