# Documentação Central Do Projeto Albertina

Este diretório concentra a base documental oficial do projeto `Albertina`.

Objetivo:

- centralizar memória operacional, conhecimento técnico e documentação funcional
- facilitar onboarding, manutenção e continuidade de contexto
- registrar restrições, decisões, convenções e artefatos de referência

## Índice Mestre

### Base de conhecimento e memória

- [project_memory_knowledge.md](file:///c:/GitHubLocal/Albertina/docs/project_memory_knowledge.md): memória consolidada do projeto, restrições, convenções, decisões recentes e contexto operacional
- [memory_snapshot_2026-07-07.md](file:///c:/GitHubLocal/Albertina/docs/memory_snapshot_2026-07-07.md): snapshot literal das memórias consolidadas na data da atualização
- [chat_memory_knowledge_skills_2026-07-07.md](file:///c:/GitHubLocal/Albertina/docs/chat_memory_knowledge_skills_2026-07-07.md): consolidado desta sessão com memória, decisões, implementações, problemas resolvidos, validações e skills usadas

### Guias principais

- [ai_erp_consulta_arquitetura_plano_execucao.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_consulta_arquitetura_plano_execucao.md): arquitetura alvo e plano de execução da IA para consulta em linguagem natural sobre os dados do ERP
- [ai_erp_mvp_metricas_regras_tools.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_mvp_metricas_regras_tools.md): matriz operacional do MVP com métricas, regras funcionais, fontes e tools da IA
- [ai_erp_tabelas_semanticas_especificacao.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_tabelas_semanticas_especificacao.md): especificação técnica da camada semântica `olist_ai` para métricas, glossário, auditoria e RAG
- [ai_erp_tools_especificacao_tecnica.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_tools_especificacao_tecnica.md): especificação técnica do catálogo inicial de tools da IA, contratos e regras operacionais
- [ai_erp_backlog_implementacao.md](file:///c:/GitHubLocal/Albertina/docs/ai_erp_backlog_implementacao.md): backlog técnico por módulo, arquivo e etapa de implementação da solução de IA
- [olist_mapping_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide.md): guia técnico completo de mapeamento Olist ERP -> banco
- [olist_mapping_guide_executive.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide_executive.md): visão executiva do mapeamento
- [olist_mapping_matrix_consolidated.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_matrix_consolidated.md): matriz consolidada campo a campo
- [olist_etl_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_etl_guide.md): fluxo operacional de ETL por entidade
- [extraction-modes-spec.md](file:///c:/GitHubLocal/Albertina/docs/extraction-modes-spec.md): especificação dos modos `incremental` e `reconciliation`
- [olist_erp_der.md](file:///c:/GitHubLocal/Albertina/docs/olist_erp_der.md): DER lógico e operacional

### Artefatos visuais

- [olist_extraction_data_flow.html](file:///c:/GitHubLocal/Albertina/docs/olist_extraction_data_flow.html): fluxo visual da extração Olist

### Artefatos visuais complementares

- [Data_Map.html](file:///c:/GitHubLocal/Albertina/docs/Data_Map.html): mapa visual ERP Olist x banco consolidado neste diretório

## Regras De Organização

- todo novo conhecimento estrutural do projeto deve ser consolidado também em `project_memory_knowledge.md`
- documentação técnica nova deve ser criada preferencialmente neste diretório
- artefatos visuais podem permanecer fora de `docs/` quando houver decisão explícita anterior, mas devem ser indexados aqui

## Escopo Atual Consolidado

Este diretório passa a ser a referência principal para:

- memória do projeto
- conhecimento técnico consolidado
- guias operacionais
- especificações funcionais
- documentos visuais de apoio

## Estado Documentado Em 07/07/2026

- a extração incremental está operacional e validada ponta a ponta
- o worker executa `core_sync` automático ao final da extração bem-sucedida
- o sincronismo `RAW -> CORE` usa filtro por `execution_id` no fluxo automático para processar apenas o delta da execução
- a camada `MART` é atualizada automaticamente após o `core_sync` com refresh em lote das materialized views
- a documentação visual e textual deste diretório reflete o estado real validado em execução recente pela aplicação
