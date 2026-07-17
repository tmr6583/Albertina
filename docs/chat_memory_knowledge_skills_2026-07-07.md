# Memória, Conhecimento E Skills Deste Chat

Este documento consolida o conhecimento produzido neste chat, incluindo decisões, implementações, correções, validações, memórias operacionais e skills/ferramentas usadas durante a sessão.

## Objetivo Deste Registro

- preservar contexto executável da sessão
- reduzir perda de conhecimento entre rodadas
- permitir retomada rápida de arquitetura, backend, frontend e validações
- documentar não só o que foi decidido, mas também o que foi implementado e testado

## Escopo Consolidado Da Sessão

Nesta sessão foi construída e refinada a primeira base funcional da frente de `IA para consulta aos dados do ERP Olist` dentro do projeto `Albertina`, incluindo:

- arquitetura alvo e plano de execução
- documentação funcional e técnica do MVP
- camada semântica no banco `olist_ai`
- evolução analítica da `MART`
- endpoints backend para catálogo e consulta IA
- integração da consulta IA no frontend
- revisão e correção do frontend após regressões percebidas em navegação e carregamento
- refinamento visual da tela `Consulta IA`

## Memória Consolidada Do Projeto Reforçada Neste Chat

- o projeto `Albertina` continua baseado em `Supabase/PostgreSQL`, `FastAPI` e `React + Vite`
- a arquitetura de dados preferencial segue `RAW -> CORE -> MART`
- a `MART` é a camada preferencial para consumo por negócio e por IA
- o serviço `core_sync` continua sendo o mecanismo central de promoção semântica do dado
- o sincronismo por `execution_id` foi mantido como convenção essencial
- o produto deve permanecer em português do Brasil
- a interface deve continuar densa, executiva, compacta e orientada a operação real

## Decisões Funcionais Da IA ERP

### Direção Arquitetural

- a solução deve ser `stateless` onde possível e escalável horizontalmente
- a abordagem principal para ERP deve ser `SQL controlado + function calling`
- `RAG` deve complementar contexto semântico e documental, não substituir consultas estruturadas
- `agente` deve ser restrito e posterior ao catálogo controlado de tools

### Escopo Do MVP

- escopo arquitetural: completo
- autenticação inicial: usuários internos
- domínios do MVP: `vendas`, `estoque`, `financeiro`
- `CRM` fica fora da primeira onda do MVP

### Definições Funcionais Consolidadas

- `faturamento efetivo`:
  - definição funcional validada: soma dos pedidos finalizados com notas fiscais autorizadas ou contas lançadas no período
  - tradução técnica adotada no modelo atual: `order_status = 1` e `billing_date` preenchido
- `data de referência de faturamento`: `billing_date`
- `pedidos emitidos`: continuam usando `order_date`
- `vencidos`: `due_date < hoje` e `open_amount > 0`
- `estoque baixo`: `available_qty <= stock_min_qty`
- `estoque mínimo`:
  - origem atual: `olist_core.products.raw_attributes -> estoque -> minimo`
  - passou a ser exposto na camada analítica para o MVP

## Conhecimento Obtido Com Fontes Externas

### Olist ERP

- a documentação oficial do Olist foi usada para confirmar enums e comportamento funcional
- a IA do Olist foi usada como fonte complementar para esclarecer conceitos de negócio
- foram consolidados status oficiais de:
  - pedidos
  - contas a receber
  - contas a pagar

### Conclusão Reforçada

- a documentação e a IA do Olist ajudam a fechar regras funcionais
- a tradução final para o MVP precisa sempre ser validada no banco e no código do Albertina

## Documentação Criada Ou Consolidada Neste Chat

- [ai_erp_consulta_arquitetura_plano_execucao.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_consulta_arquitetura_plano_execucao.md)
- [ai_erp_mvp_metricas_regras_tools.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_mvp_metricas_regras_tools.md)
- [ai_erp_tabelas_semanticas_especificacao.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_tabelas_semanticas_especificacao.md)
- [ai_erp_tools_especificacao_tecnica.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_tools_especificacao_tecnica.md)
- [ai_erp_backlog_implementacao.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_backlog_implementacao.md)

## Implementações Realizadas No Banco

### Migração Principal

- arquivo criado: [20260707193000_olist_ai_semantic_layer.sql](file:///c:/GitHubLocal/Albertina/supabase/migrations/20260707193000_olist_ai_semantic_layer.sql)

### Schema E Estruturas Criadas

- `olist_ai.ai_metric_catalog`
- `olist_ai.ai_business_glossary`
- `olist_ai.ai_entity_synonyms`
- `olist_ai.ai_query_templates`
- `olist_ai.ai_prompt_policies`
- `olist_ai.ai_query_audit`
- `olist_ai.ai_documents`
- `olist_ai.ai_document_chunks`

### Recursos Técnicos Aplicados

- `pgvector` habilitado
- `RLS` habilitado nas tabelas da camada `olist_ai`
- políticas orientadas por `tenant`
- índices para busca semântica, auditoria e lookup de catálogo
- seeds iniciais de métricas, glossário, templates e políticas

### Evolução Da Camada Analítica

- `olist_mart.vw_fact_orders`:
  - `order_status_name`
  - `is_billed_order`
  - `billed_on`
- `olist_mart.vw_fact_inventory`:
  - `stock_min_qty`
  - `stock_control_enabled`
  - `is_below_min_stock`
- `olist_mart.vw_dim_products`:
  - `stock_min_qty`
  - `stock_max_qty`
  - `stock_control_enabled`
- materialized views impactadas foram recriadas

## Implementações Realizadas No Backend

### Arquivo Principal

- backend alterado em [app.py](file:///c:/GitHubLocal/Albertina/backend/app.py)

### Primeira Camada De Catálogo IA

- `GET /api/ai/overview`
- `GET /api/ai/metrics`
- `GET /api/ai/glossary`
- `GET /api/ai/templates`

### Camada Operacional De Consulta IA

- `POST /api/ai/query`

### Tools Reais Implementadas

- `consultar_resumo_vendas`
- `consultar_estoque_baixo`
- `consultar_receber_vencidos`
- `consultar_pagar_vencidos`
- `buscar_glossario`
- `explicar_metrica`

### Capacidades Adicionais

- resolução de `tenant` do usuário autenticado
- injeção de contexto do usuário no banco
- auditoria automática em `olist_ai.ai_query_audit`
- inferência inicial de tool por palavras-chave
- resposta estruturada com:
  - `summaryText`
  - `summaryMetrics`
  - `resultTable`
  - `appliedFilters`
  - `source`
  - `audit`

### Correções Operacionais De Backend

- inclusão de `http://localhost:5173` e `http://127.0.0.1:5173` no `CORSMiddleware`
- correção importante para permitir login e uso do frontend Vite em ambiente local

## Implementações Realizadas No Frontend

### Arquivos Alterados

- [App.jsx](file:///c:/GitHubLocal/Albertina/frontend/src/App.jsx)
- [App.css](file:///c:/GitHubLocal/Albertina/frontend/src/App.css)
- [api.js](file:///c:/GitHubLocal/Albertina/frontend/src/api.js)

### Integração Da Área Consulta IA

- nova rota: `/consulta-ia`
- novo item de menu: `Consulta IA`
- integração com endpoints do backend para:
  - overview
  - métricas
  - glossário
  - templates
  - query
- histórico curto da sessão
- renderização de resposta estruturada
- tabela de dados com fonte e `auditId`

### Correções Importantes No Frontend

- a carga inicial do dashboard foi desacoplada da chamada `/ai/overview`
- antes disso, qualquer falha da camada IA podia derrubar:
  - usuários
  - logs
  - conexões
  - extração
- o problema foi corrigido deixando a IA isolada do carregamento essencial do painel

### Ajustes De Navegação

- `Consulta IA` foi movido para a primeira posição do menu
- o botão recebeu destaque visual maior

### Ajustes Visuais Mais Recentes

- hero/topo de `Consulta IA` compactado
- área `Pergunta` reorganizada e alinhada
- `Catálogo` movido para baixo da `Resposta`
- `Catálogo` com largura total útil e altura ampliada
- linguagem visual refinada para aproximar a experiência de ambientes modernos de IA

## Problemas Encontrados E Como Foram Resolvidos

### Problema 1: Falha Global No Painel Após Entrar A IA

- sintoma:
  - usuários, logs e outras áreas deixaram de aparecer
- causa:
  - `hydrateAuthenticatedData()` dependia de `/ai/overview`
- correção:
  - isolar a carga da IA em `try/catch` separado

### Problema 2: Login Falhando Em `5173`

- sintoma:
  - sessão não iniciava no frontend Vite
- causa:
  - CORS liberava apenas origem `3500`
- correção:
  - backend passou a aceitar `5173`

### Problema 3: Assinatura Das Views Da MART

- sintoma:
  - falha na aplicação inicial da migração
- causa:
  - tentativa de alterar ordem/assinatura das views existentes
- correção:
  - preservar colunas originais e anexar novas colunas ao final

### Problema 4: Lookup Semântico Restritivo

- sintoma:
  - glossário falhava em perguntas mais naturais
- correção:
  - busca expandida para aliases e presença do termo dentro da pergunta

## Validações Executadas Durante O Chat

### Banco E Backend

- conexão real com PostgreSQL/Supabase: validada
- aplicação da migração no banco: validada
- compilação Python do backend: validada
- consultas reais às tools da IA: validadas

### Frontend

- build com `Vite`: validado repetidamente
- diagnóstico do editor nos arquivos alterados: sem erros
- login real em ambiente local: validado
- reaparição de `Usuários` e `Logs`: validada
- ordem do botão `Consulta IA`: validada

### Verificações Em Navegador

- browser automation foi usada para:
  - verificar login
  - confirmar visibilidade de usuários e logs
  - validar posição do botão `Consulta IA`
  - verificar comportamento visual geral da interface

## Skills E Ferramentas Usadas Nesta Sessão

### Skills Invocadas

- `webapp-testing`
  - usada para orientar validação do frontend e testes da aplicação web
- `frontend-design`
  - usada para orientar refinamento visual e composição mais moderna da tela `Consulta IA`

### Subagentes E Automação

- `browser_use`
  - usado para validação visual e comportamental do frontend
- exploração assistida do código e banco
  - usada para mapear backend, frontend, migrações e comportamento real

### MCPs E Fontes Complementares

- documentação/API/MCP do Olist
  - usados para confirmar conceitos e enums
- IA do Olist
  - usada como fonte complementar de esclarecimento funcional

## Learnings De Implementação

- em ERP, `SQL estruturado` continua sendo o eixo mais confiável para consulta factual
- `RAG` deve ser construído sobre contexto documental e semântico, não sobre fatos transacionais puros
- a camada `MART` precisa continuar sendo o primeiro alvo das tools
- pequenas dependências indevidas no bootstrap do frontend derrubam percepção de estabilidade do produto inteiro
- ao evoluir views já consumidas, preservar ordem e compatibilidade de colunas é obrigatório
- o fluxo correto de evolução é:
  - documentação
  - modelo semântico
  - backend controlado
  - frontend
  - refinamento de UX

## Estado Atual Após Este Chat

- arquitetura da IA documentada: sim
- plano de execução documentado: sim
- matriz de métricas e tools documentada: sim
- camada semântica `olist_ai` implementada: sim
- endpoints backend da IA implementados: sim
- consulta IA inicial funcional: sim
- frontend integrado à consulta IA: sim
- correções de carregamento e CORS: sim
- refinamento visual da tela `Consulta IA`: sim

## Pendências Naturais Para Próximas Rodadas

- integrar `OpenAI` / `LangChain` ou orquestração equivalente sobre o catálogo existente
- persistir histórico de conversas IA de forma mais completa
- ativar carga documental em `ai_documents` e `ai_document_chunks`
- evoluir para `RAG` prático
- expandir catálogo de tools para:
  - mais análises de vendas
  - mais consultas financeiras
  - estoque por depósito, produto e cobertura
- evoluir UX para filtros avançados e experiência conversacional mais madura

## Regra De Uso Deste Documento

Este arquivo deve servir como `snapshot operacional desta sessão`. Em novas rodadas:

- decisões permanentes devem ser refletidas também em [project_memory_knowledge.md](file:///c:/GitHubLocal/Albertina/docs/project_memory_knowledge.md)
- novas implementações devem atualizar os documentos técnicos específicos já criados
- este arquivo pode ser usado como ponto de retomada rápida do contexto completo deste chat
