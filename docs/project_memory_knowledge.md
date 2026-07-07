# Memória E Base De Conhecimento Do Projeto Albertina

Este documento consolida a memória operacional, o conhecimento técnico recorrente e as decisões importantes do projeto `Albertina`.

## Contexto Do Projeto

- objetivo principal: integrar o ERP Olist ao `PostgreSQL / Supabase`
- camadas principais: `public`, `olist_admin`, `olist_raw`, `olist_core`, `olist_mart`
- arquitetura da aplicação: frontend em `React + Vite` e backend em `FastAPI`
- extrações longas rodam em worker ou CLI dedicada para evitar interrupções por reciclagem do servidor web
- o artefato visual de mapeamento ERP x banco está em [Data_Map.html](file:///c:/GitHubLocal/Albertina/docs/Data_Map.html)

## Estado Atual Da Aplicação

- autenticação própria com sessão Bearer
- gestão administrativa de usuários
- integração OAuth real com a Olist
- tela `Conexões` com operação real
- tela `Extração` com disparo, acompanhamento, histórico, parada segura e download de log
- persistência principal em `PostgreSQL / Supabase`
- fallback local em `SQLite` apenas para desenvolvimento e suporte local

## Restrições Obrigatórias

- apenas uma execução de extração por vez
- bloqueio global controlado por `lease` e `pg_advisory_lock`
- coordenação persistente em `olist_admin.execution_control`
- logs e datas no padrão `DD/MM/YYYY HH:MM:SS`
- resumos operacionais devem apresentar `Início`, `Término` e `Tempo total`
- no quadro `Histórico`, o tipo da execução deve aparecer ao lado de `Resumo da execução concluída`

## Convenções De Engenharia

- `execution_control` usa `lease`, `heartbeat` e `worker_id`
- o fluxo automático usa `execution_id` para promover apenas o delta da execução corrente no `core_sync`
- o modelo bruto fica em `olist_raw.api_payloads`
- a normalização relacional fica em `olist_core.*`
- a leitura analítica fica em `olist_mart.vw_*` e `olist_mart.mv_*`
- o refresh da `MART` ocorre automaticamente ao final do `core_sync` bem-sucedido
- interfaces devem usar paleta clara baseada na marca, com azul, amarelo e ciano
- toda comunicação visual e textual do produto deve permanecer em português do Brasil

## Conhecimento Operacional

### Modos De Extração

- `incremental`: prioriza menor volume com `watermark`, janelas ou `cooldown` quando aplicável
- `reconciliation`: executa leitura ampla, reconcilia ausências e aquece `watermarks` e `cooldowns`
- os dois modos compartilham o mesmo slot global de execução
- a incremental validada pela aplicação já executa `RAW -> CORE -> MART` automaticamente

### Controle E Persistência

- trilha operacional em `olist_admin.sync_runs`
- logs persistidos em `olist_admin.sync_run_logs`
- `watermarks` persistidos em `olist_admin.sync_watermarks`
- coordenação global em `olist_admin.execution_control`
- payloads brutos em `olist_raw.api_payloads`

### Fluxo Funcional Resumido

1. o frontend autentica o usuário
2. a tela `Conexões` realiza OAuth com a Olist
3. a tela `Extração` dispara a sincronização via API
4. o backend coordena a execução e atualiza logs, status e heartbeat
5. a API Olist é consumida com paginação, retry e persistência RAW
6. o `core_sync` promove o delta da execução para `olist_core.*`
7. o fechamento atualiza `olist_mart.*` com refresh automático das materialized views

## Lições Aprendidas

- `invoices` e `contacts` são os maiores gargalos de tempo
- worker externo é mandatório para execuções longas
- uma conciliação completa pode chegar a aproximadamente `25h`
- incrementais tendem a estabilizar entre `30min` e `2h` após aquecimento
- `orders` exige validação por presença no RAW e por `last_seen_execution_id` devido a limitações de filtro na API
- o worker só libera o slot global depois de concluir `core_sync` e o refresh da `MART`

## Preferências Operacionais Consolidadas

As preferências abaixo impactam arquitetura de tela, instrumentação e documentação:

- comunicação direta e pragmática em português
- interfaces densas, executivas e com pouco espaçamento vertical
- feedback visual em tempo real durante processamento
- métricas de execução com alta visibilidade
- botões críticos com rótulos em maiúsculas, como `INCREMENTAL` e `CONCILIAÇÃO`
- polling operacional de `10` segundos

## Decisões Recentes

- o mapeamento visual ERP Olist x banco foi consolidado em [Data_Map.html](file:///c:/GitHubLocal/Albertina/docs/Data_Map.html)
- a documentação técnica foi revisada para refletir o catálogo real de endpoints, entidades e tabelas
- nomes antigos e incorretos foram removidos da documentação, incluindo rotas e `entity_name` desatualizados
- os registros `debug-*` foram reposicionados como histórico documental, não como incidentes abertos
- a incremental executada pela aplicação validou `core_sync` automático, delta por `execution_id` e refresh da `MART`

## Inventário Documental

- índice central: [README.md](file:///c:/GitHubLocal/Albertina/docs/README.md)
- guia técnico: [olist_mapping_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide.md)
- guia executivo: [olist_mapping_guide_executive.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_guide_executive.md)
- matriz consolidada: [olist_mapping_matrix_consolidated.md](file:///c:/GitHubLocal/Albertina/docs/olist_mapping_matrix_consolidated.md)
- guia de ETL: [olist_etl_guide.md](file:///c:/GitHubLocal/Albertina/docs/olist_etl_guide.md)
- especificação dos modos: [extraction-modes-spec.md](file:///c:/GitHubLocal/Albertina/docs/extraction-modes-spec.md)
- fluxo visual: [olist_extraction_data_flow.html](file:///c:/GitHubLocal/Albertina/docs/olist_extraction_data_flow.html)
- DER: [olist_erp_der.md](file:///c:/GitHubLocal/Albertina/docs/olist_erp_der.md)

## Regra De Atualização

Sempre que houver:

- nova decisão arquitetural
- restrição operacional relevante
- mudança no fluxo de extração
- refinamento importante de UI operacional
- aprendizado recorrente em incidentes ou execuções

Este documento deve ser atualizado junto com os guias técnicos afetados.
