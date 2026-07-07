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

### Guias principais

- [olist_mapping_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide.md): guia técnico completo de mapeamento Olist ERP -> banco
- [olist_mapping_guide_executive.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide_executive.md): visão executiva do mapeamento
- [olist_mapping_matrix_consolidated.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_matrix_consolidated.md): matriz consolidada campo a campo
- [olist_etl_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_etl_guide.md): fluxo operacional de ETL por entidade
- [extraction-modes-spec.md](file:///c:/GitHubLocal/Albertina/docs/extraction-modes-spec.md): especificação dos modos `incremental` e `reconciliation`
- [olist_erp_der.md](file:///c:/GitHubLocal/Albertina/docs/olist_erp_der.md): DER lógico e operacional

### Artefatos visuais

- [olist_extraction_data_flow.html](file:///c:/GitHubLocal/Albertina/docs/olist_extraction_data_flow.html): fluxo visual da extração Olist

### Artefatos externos referenciados

- [Data_Map.html](file:///c:/GitHubLocal/Albertina/files/Data_Map.html): mapa visual ERP Olist x banco mantido em `files/` por decisão prévia do projeto

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
