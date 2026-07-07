# Snapshot De Memória Do Projeto

Data de consolidação: `07/07/2026`

Este arquivo registra, em formato documental, o snapshot das memórias e do contexto operacional relevante no momento da consolidação.

## Memória De Projeto

### Contexto

- Projeto Albertina: integração ERP Olist -> Supabase
- schemas relevantes: `public`, `olist_admin`, `olist_raw`, `olist_core`, `olist_mart`
- extrações longas rodam em worker ou CLI dedicada
- o mapeamento visual ERP x banco está centralizado em `docs/Data_Map.html`

### Restrições

- apenas uma execução por vez
- coordenação por `lease` e `pg_advisory_lock`
- datas em `DD/MM/YYYY HH:MM:SS`
- logs com `Início`, `Término` e `Tempo total`
- o tipo da execução deve aparecer no subtítulo do histórico ao lado de `Resumo da execução concluída`

### Convenções

- tabela de coordenação: `olist_admin.execution_control`
- campos operacionais: `lease`, `heartbeat`, `worker_id`
- o fluxo automático usa `execution_id` para promover apenas o delta atual no `core_sync`
- o refresh da `MART` ocorre automaticamente após o `core_sync` bem-sucedido
- identidade visual clara baseada na marca
- interface textual em português do Brasil

### Lições Aprendidas

- `invoices` e `contacts` são gargalos relevantes
- worker externo é necessário para execuções longas
- conciliações completas podem alcançar cerca de `25h`
- incrementais costumam cair para a faixa de `30min` a `2h` após aquecimento
- `orders` depende de validação por presença em RAW e por `last_seen_execution_id`
- o worker permanece ocupado até concluir `core_sync` e refresh da `MART`, mesmo após `28/28` entidades

## Memória De Perfil Operacional

- perfil de atuação: arquitetura de software sênior e engenharia de dados full-stack
- foco técnico recorrente: APIs, ERP, Python, FastAPI, PostgreSQL, ETL, integração com IA e segurança
- preferência de comunicação: direta e pragmática, em português
- preferência visual: interfaces modernas, densas, executivas e com pouco espaçamento vertical
- preferência de operação: forte visibilidade de métricas, feedback em tempo real e botões críticos em maiúsculas
- restrições recorrentes: datas em `DD/MM/YYYY HH:MM:SS` e polling de `10` segundos

## Memória De Sessão Recente

- foi criado o artefato `docs/Data_Map.html`
- o artefato recebeu refinamento visual com paleta clara alinhada à marca
- o título principal foi reduzido para manter estética compacta
- a área de tabela foi ampliada para melhorar a leitura operacional
- os botões de domínio foram deixados em negrito
- o conteúdo textual foi revisado para português do Brasil
- a documentação do projeto foi atualizada para refletir o estado técnico atual
- a incremental executada pela aplicação validou a cadeia automática `RAW -> CORE -> MART`

## Observação

Este snapshot é complementar ao documento consolidado [project_memory_knowledge.md](file:///c:/GitHubLocal/Albertina/docs/project_memory_knowledge.md), que permanece como base viva de memória e conhecimento do projeto.
