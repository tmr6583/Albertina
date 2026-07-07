# Backlog Tecnico De Implementacao Da IA ERP

Backlog técnico orientado à execução para implementação da camada de IA de consulta ao ERP no projeto `Albertina`.

## Objetivo

Transformar a arquitetura e as especificações em um backlog acionável por módulo, arquivo e responsabilidade.

## Premissas

- backend principal em `FastAPI`
- consumo principal em `olist_mart`
- camada semântica em `olist_ai`
- autenticação inicial com usuários internos
- `function calling` como mecanismo principal
- `RAG` complementar

## Bloco 1. Banco E Migrações

### Entrega

Criar a camada `olist_ai` e preparar o banco para semântica, auditoria e embeddings.

### Arquivos Esperados

- `backend/alembic/versions/<timestamp>_create_olist_ai_schema.py`
- `backend/alembic/versions/<timestamp>_enable_pgvector.py`
- `backend/sql/olist_ai_seed_metric_catalog.sql`
- `backend/sql/olist_ai_seed_glossary.sql`

### Tarefas

- criar schema `olist_ai`
- habilitar extensão `vector`
- criar tabelas:
  - `ai_metric_catalog`
  - `ai_business_glossary`
  - `ai_entity_synonyms`
  - `ai_query_templates`
  - `ai_prompt_policies`
  - `ai_query_audit`
  - `ai_documents`
  - `ai_document_chunks`
- criar índices e chaves
- aplicar `RLS`
- inserir seeds iniciais do MVP

## Bloco 2. Contratos E Tipagem

### Entrega

Formalizar contratos de entrada e saída das tools.

### Arquivos Esperados

- `backend/app/ai/contracts.py`
- `backend/app/ai/schemas.py`
- `backend/app/ai/enums.py`

### Tarefas

- definir modelos Pydantic para contexto comum
- definir modelos de filtro por domínio
- definir modelos de resposta comum
- definir enums de perfil, domínio, status e erro

## Bloco 3. Guards E Seguranca

### Entrega

Centralizar validação, escopo e bloqueios.

### Arquivos Esperados

- `backend/app/ai/guards.py`
- `backend/app/ai/security.py`
- `backend/app/ai/policies.py`

### Tarefas

- validar `tenant_id`
- validar perfil do usuário
- validar filtros permitidos por tool
- limitar paginação
- bloquear ferramentas fora do perfil

## Bloco 4. Repositórios De Leitura

### Entrega

Criar acesso controlado às views analíticas.

### Arquivos Esperados

- `backend/app/ai/repositories/sales_repository.py`
- `backend/app/ai/repositories/inventory_repository.py`
- `backend/app/ai/repositories/finance_repository.py`
- `backend/app/ai/repositories/semantic_repository.py`

### Tarefas

- encapsular queries SQL por domínio
- centralizar joins, agregações e paginação
- padronizar filtros temporais
- evitar duplicação de SQL entre tools

## Bloco 5. Tools De Vendas

### Entrega

Implementar catálogo inicial de vendas.

### Arquivos Esperados

- `backend/app/ai/tools/sales.py`
- `backend/tests/ai/test_sales_tools.py`

### Tarefas

- `consultar_resumo_vendas`
- `consultar_vendas_por_periodo`
- `consultar_top_clientes`
- `consultar_top_produtos`
- `consultar_vendas_por_canal`
- `consultar_vendas_por_vendedor`
- `consultar_pedidos`
- `explicar_status_pedido`

## Bloco 6. Tools De Estoque

### Entrega

Implementar catálogo inicial de estoque.

### Arquivos Esperados

- `backend/app/ai/tools/inventory.py`
- `backend/tests/ai/test_inventory_tools.py`

### Tarefas

- `consultar_estoque_produtos`
- `consultar_ruptura_estoque`
- `consultar_estoque_baixo`
- `consultar_estoque_por_deposito`
- `consultar_produtos`

## Bloco 7. Tools De Financeiro

### Entrega

Implementar catálogo inicial financeiro.

### Arquivos Esperados

- `backend/app/ai/tools/finance.py`
- `backend/tests/ai/test_finance_tools.py`

### Tarefas

- `consultar_receber_resumo`
- `consultar_receber_vencidos`
- `consultar_receber_por_cliente`
- `consultar_pagar_resumo`
- `consultar_pagar_vencidos`
- `consultar_pagar_por_fornecedor`

## Bloco 8. Tools Semanticas

### Entrega

Implementar explicações e glossário.

### Arquivos Esperados

- `backend/app/ai/tools/semantic.py`
- `backend/tests/ai/test_semantic_tools.py`

### Tarefas

- `explicar_metrica`
- `buscar_glossario`
- lookup de sinônimos
- resolução de termos ambíguos

## Bloco 9. Auditoria E Observabilidade

### Entrega

Registrar e monitorar tudo o que a IA faz.

### Arquivos Esperados

- `backend/app/ai/audit.py`
- `backend/app/ai/logging.py`
- `backend/tests/ai/test_audit.py`

### Tarefas

- gravar `ai_query_audit`
- padronizar logs estruturados
- medir duração e volume retornado
- registrar erros e bloqueios

## Bloco 10. Roteador De Intenção

### Entrega

Orquestrar a escolha da tool adequada.

### Arquivos Esperados

- `backend/app/ai/router.py`
- `backend/app/ai/intent_classifier.py`
- `backend/tests/ai/test_router.py`

### Tarefas

- classificar perguntas por domínio e intenção
- selecionar tool adequada
- tratar ambiguidades
- rotear para semântico quando necessário

## Bloco 11. Integracao Com LLM

### Entrega

Conectar o modelo ao catálogo de tools com controle.

### Arquivos Esperados

- `backend/app/ai/llm/openai_client.py`
- `backend/app/ai/llm/tool_registry.py`
- `backend/app/ai/llm/prompt_builder.py`
- `backend/tests/ai/test_llm_integration.py`

### Tarefas

- registrar tools disponíveis
- montar system prompt e políticas
- definir fallback sem tool
- controlar temperatura e formato de resposta

## Bloco 12. RAG E Embeddings

### Entrega

Adicionar recuperação semântica baseada em documentos.

### Arquivos Esperados

- `backend/app/ai/rag/indexer.py`
- `backend/app/ai/rag/retriever.py`
- `backend/app/ai/rag/chunker.py`
- `backend/app/ai/rag/embeddings.py`
- `backend/tests/ai/test_rag.py`

### Tarefas

- importar documentação
- gerar chunks
- gerar embeddings
- indexar em `ai_document_chunks`
- recuperar contexto com filtros por domínio e tenant

## Bloco 13. API De Consulta

### Entrega

Expor o backend da IA por endpoints dedicados.

### Arquivos Esperados

- `backend/app/api/routes/ai.py`
- `backend/tests/api/test_ai_routes.py`

### Tarefas

- `POST /ai/chat`
- `POST /ai/query`
- `GET /ai/history`
- `GET /ai/metrics`
- autenticar e validar contexto do usuário

## Bloco 14. Frontend De Consulta

### Entrega

Construir experiência de consulta em linguagem natural.

### Arquivos Esperados

- `frontend/src/pages/AiConsultaPage.jsx`
- `frontend/src/components/ai/AiChatPanel.jsx`
- `frontend/src/components/ai/AiEvidencePanel.jsx`
- `frontend/src/components/ai/AiResultTable.jsx`
- `frontend/src/services/aiService.js`

### Tarefas

- criar campo de pergunta
- exibir resposta textual
- exibir tabela de apoio
- mostrar filtros aplicados
- mostrar fonte e data de referência
- criar histórico de consultas

## Bloco 15. Seeds E Curadoria Inicial

### Entrega

Popular a camada semântica com conteúdo útil desde o primeiro uso.

### Arquivos Esperados

- `docs/ai_erp_mvp_metricas_regras_tools.md`
- `backend/sql/olist_ai_seed_metric_catalog.sql`
- `backend/sql/olist_ai_seed_glossary.sql`
- `backend/sql/olist_ai_seed_query_templates.sql`

### Tarefas

- cadastrar métricas do MVP
- cadastrar glossário inicial
- cadastrar templates de intenção
- cadastrar enum de `order_status`
- cadastrar status oficiais de recebíveis e pagáveis

## Bloco 16. Testes E Homologacao

### Entrega

Garantir previsibilidade funcional e segurança.

### Arquivos Esperados

- `backend/tests/ai/`
- `frontend/src/components/ai/__tests__/`
- `docs/ai_erp_homologacao.md`

### Tarefas

- testar regras por tool
- testar bloqueios de perfil
- testar escopo por tenant
- testar perguntas ambíguas
- testar consistência entre resposta e tabela

## Sequencia Recomendada

1. banco e migrações
2. contratos e guards
3. repositórios de leitura
4. tools de vendas
5. tools de estoque
6. tools de financeiro
7. auditoria
8. roteador de intenção
9. integração com LLM
10. API
11. frontend
12. RAG
13. testes e homologação

## Dependencias Criticas

- validação funcional de métricas pendentes
- habilitação de `pgvector`
- definição da estrutura real do backend atual
- validação do modelo de autenticação de usuários internos

## Resultado Esperado

Este backlog deve permitir decompor a implementação em entregas curtas, testáveis e alinhadas à arquitetura definida para a IA de consulta do `Albertina`.
