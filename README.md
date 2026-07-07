# Albertina

Aplicação administrativa com autenticação própria, gestão de usuários e integração OAuth real com a Olist. O projeto é composto por frontend em `React + Vite` e backend em `FastAPI`, com persistência principal em `PostgreSQL / Supabase` e fallback local em `SQLite` para desenvolvimento.

## Visão Geral

Estado atual da aplicação:

- autenticação própria por e-mail e senha
- gestão administrativa de usuários
- sessões via token Bearer
- auditoria operacional persistida
- tela `Conexões` com operação real da Olist
- menu `Extração` com disparo da sincronização ERP Olist -> Supabase
- acompanhamento operacional da extração com entidade atual, ETA local, card executivo de logs, historico clicável e parada segura
- OAuth real da Olist já implementado
- persistência validada em `PostgreSQL / Supabase`
- fallback local em `SQLite`
- interface em `pt-BR`, com identidade visual padronizada

O projeto já opera como base administrativa e operacional para sincronização do ERP Olist com persistência estruturada em `PostgreSQL / Supabase`, combinando autenticação, OAuth, extração assistida por UI/API, worker dedicado e documentação técnica de apoio.

## Funcionalidades Implementadas

Recursos já disponíveis no repositório:

- login com autenticação própria
- restauração automática da sessão autenticada
- logout com revogação de sessão
- listagem de usuários
- criação de usuário administrativo
- alteração de senha
- ativação e desativação de usuários
- exclusão de usuário
- bloqueio para impedir exclusão do próprio usuário autenticado
- bloqueio para impedir desativação do próprio usuário autenticado
- bloqueio de login para usuários inativos
- trilha de auditoria administrativa
- tela `Conexões` com status de Olist e banco de dados
- geração da URL oficial de autorização OAuth da Olist
- callback OAuth com validação de `state`
- troca real de código de autorização por `access_token` e `refresh_token`
- renovação real de token via `refresh_token`
- persistência de tokens, expiração, `state` e logs da conexão Olist
- cliente HTTP real inicial para validar a API da Olist
- orquestração de extração completa com logs, controle incremental e persistência raw no Supabase
- download do log completo por execução a partir do quadro `Histórico`

Pendências atuais de evolução:

- expansão da carga relacional `olist_core.*` a partir do RAW já persistido
- refinamento da cobertura documental campo a campo em entidades ainda parciais
- endurecimento de segurança para segredos OAuth em repouso
- observabilidade mais ampla para integrações, worker e refresh analítico
- criptografia dedicada para segredos OAuth em repouso
- automação adicional de publicação e operação fora do ambiente local

## Arquitetura

Fluxo atual da aplicação:

1. O usuário acessa o frontend em `http://localhost:3500`.
2. A tela de login envia credenciais para `POST /api/auth/login`.
3. O backend valida o usuário, cria a sessão e retorna um token Bearer.
4. O frontend armazena o token em `localStorage`.
5. As páginas autenticadas consomem `users`, `connections/overview`, `extraction/overview` e trilhas operacionais quando necessário.
6. A tela `Conexões` opera o fluxo OAuth da Olist e registra os eventos no banco.
7. A API pode validar a integração real por `GET /api/connections/olist/api-test`.
8. A tela `Extração` dispara a sincronização completa, acompanha o status por polling na API, calcula ETA e velocidade localmente e permite parada segura.
9. O quadro `Histórico` consulta `GET /api/extraction/executions/{execution_id}` para baixar o log completo da execução selecionada.

Componentes principais:

- `frontend/`: interface React/Vite
- `backend/`: API FastAPI e regras de negócio
- `backend/data/albertina.db`: base local SQLite de fallback
- `supabase/migrations/`: versionamento de schema PostgreSQL/Supabase
- `files/`: insumos locais, capturas e scripts auxiliares

## Stack

Frontend:

- `React 19`
- `Vite 8`
- `ESLint`
- CSS puro

Backend:

- `Python`
- `FastAPI`
- `Uvicorn`
- `Pydantic`
- `SQLite`
- `PostgreSQL / Supabase`
- `psycopg[binary]`

Segurança atualmente implementada:

- hash de senha com `PBKDF2-HMAC SHA-256`
- hash do token de sessão com `SHA-256`
- comparação segura com `hmac.compare_digest`

## Estrutura do Repositório

```text
Albertina/
|-- README.md
|-- Albertina.bat
|-- backend/
|   |-- app.py
|   |-- bootstrap_supabase.py
|   |-- requirements.txt
|   |-- logs/
|   |-- tests/
|   `-- olist_extraction/
|       |-- README.md
|       |-- catalog.py
|       |-- cli.py
|       |-- extract.py
|       |-- load.py
|       `-- service.py
|-- docs/
|   |-- README.md
|   |-- extraction-modes-spec.md
|   |-- memory_snapshot_2026-07-07.md
|   |-- olist_etl_guide.md
|   |-- olist_erp_der.md
|   |-- olist_extraction_data_flow.html
|   |-- olist_mapping_guide.md
|   |-- olist_mapping_guide_executive.md
|   |-- project_memory_knowledge.md
|   `-- olist_mapping_matrix_consolidated.md
|-- files/
|   |-- Albertina.png
|   |-- Data_Map.html
|   |-- Logo_Azul.jpg
|   `-- Cofre.txt
|-- frontend/
|   |-- README.md
|   |-- package.json
|   |-- vite.config.js
|   |-- public/
|   `-- src/
|-- scripts/
|   |-- generate_olist_extraction_data_flow.py
|   `-- start_extraction_direct.py
`-- supabase/
    `-- migrations/
        |-- 20260625182500_init_albertina_auth.sql
        |-- 20260625202000_add_olist_settings.sql
        |-- 20260625214000_oauth_real_and_connection_logs.sql
        |-- 20260626103000_olist_erp_foundation.sql
        |-- 20260626104000_olist_erp_master_data.sql
        |-- 20260626105000_olist_erp_sales_and_logistics.sql
        |-- 20260626110000_olist_erp_finance_and_operations.sql
        |-- 20260626111000_olist_erp_mart_views.sql
        `-- 20260626112000_olist_erp_mart_materialized_views.sql
```

## Interface Atual

Rotas do frontend:

- `/`: login
- `/usuarios`: administração de usuários
- `/conexoes`: operação e monitoramento das conexões
- `/extração`: execução e acompanhamento da extração Olist
- `/olist/callback`: rota legada do retorno OAuth no frontend

Características visuais e comportamentais:

- idioma em `pt-BR`
- título da aba fixo em `Albertina`
- fonte base `Arial`
- fundo branco com cards azuis
- menu principal no topo
- menu principal com atalhos para Usuários, Conexões e Extração
- botão global `Sair` no cabeçalho autenticado
- datas exibidas em `DD/MM/YYYY HH:MM:SS`
- modais para criação de usuário e troca de senha
- feedback visual padronizado para sucesso e erro

## Base Documental

O diretório `docs/` passa a concentrar a base documental oficial do projeto.

Referências principais:

- índice central da documentação: [README.md](file:///c:/GitHubLocal/Albertina/docs/README.md)
- memória e conhecimento consolidado: [project_memory_knowledge.md](file:///c:/GitHubLocal/Albertina/docs/project_memory_knowledge.md)
- mapa visual ERP x banco: [Data_Map.html](file:///c:/GitHubLocal/Albertina/files/Data_Map.html)

## Backend

O backend está concentrado em `backend/app.py` e sobe uma API FastAPI única com bootstrap automático.

Na inicialização, a aplicação:

- cria as tabelas necessárias
- migra dados de SQLite para PostgreSQL/Supabase quando aplicável
- cria o usuário administrador inicial se a base estiver vazia
- cria a configuração inicial da Olist

Regras atuais:

- login sempre por e-mail
- e-mail normalizado para lowercase
- senha mínima de 8 caracteres
- duração da sessão: `12 horas`
- usuário inativo não consegue autenticar nem operar a API
- todos os usuários criados recebem papel `Administrador`
- o próprio usuário autenticado não pode ser desativado
- o próprio usuário autenticado não pode ser excluído
- ao desativar um usuário, as sessões ativas dele são revogadas

## Persistência

Banco principal recomendado:

- `PostgreSQL / Supabase`

Fallback local:

- `SQLite` em `backend/data/albertina.db`

Tabelas operacionais atuais:

- `users`
- `sessions`
- `audits`
- `olist_settings`
- `connection_logs`

Resumo dos campos principais:

- `users`: identidade, e-mail, hash de senha, status, datas e último acesso
- `sessions`: vínculo com usuário, hash do token, expiração e revogação
- `audits`: título, descrição, tom visual e data do evento
- `olist_settings`: configuração OAuth, tokens, expiração, `state` e status
- `connection_logs`: eventos operacionais da conexão Olist

Migrations versionadas em:

- `supabase/migrations/20260625182500_init_albertina_auth.sql`
- `supabase/migrations/20260625202000_add_olist_settings.sql`
- `supabase/migrations/20260625214000_oauth_real_and_connection_logs.sql`
- `supabase/migrations/20260626103000_olist_erp_foundation.sql`
- `supabase/migrations/20260626104000_olist_erp_master_data.sql`
- `supabase/migrations/20260626105000_olist_erp_sales_and_logistics.sql`
- `supabase/migrations/20260626110000_olist_erp_finance_and_operations.sql`
- `supabase/migrations/20260626111000_olist_erp_mart_views.sql`

Bootstrap de schema no Supabase/PostgreSQL:

- `backend/bootstrap_supabase.py`
- usa `ALBERTINA_DATABASE_URL` ou `DATABASE_URL`
- aplica as migrations em ordem e registra o historico em `public.albertina_schema_migrations`

Exemplo:

```bash
python backend/bootstrap_supabase.py
```

Validação sem aplicar:

```bash
python backend/bootstrap_supabase.py --dry-run
```

Views analíticas criadas em `olist_mart`:

- `vw_dim_contacts`
- `vw_dim_products`
- `vw_fact_orders`
- `vw_fact_order_items`
- `vw_fact_receivables`
- `vw_fact_payables`
- `vw_fact_inventory`
- `vw_crm_pipeline`

Materialized views analíticas criadas em `olist_mart`:

- `mv_dim_contacts`
- `mv_dim_products`
- `mv_fact_orders`
- `mv_fact_order_items`
- `mv_fact_receivables`
- `mv_fact_payables`
- `mv_fact_inventory`
- `mv_crm_pipeline`

Estratégia de refresh:

- refresh padrao em lote pela funcao `select olist_admin.refresh_olist_mart_views(false);`
- refresh padrao unitario pela funcao `select olist_admin.refresh_olist_mart_view('mv_fact_orders', false);`
- refresh concorrente apenas manual, fora de funcao/transação, por exemplo:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY olist_mart.mv_dim_contacts;
```

- historico de refresh persistido em `olist_admin.mart_refresh_log`

## Credencial Inicial

Bootstrap padrão:

- e-mail: `admin@empresa.com`
- senha: `Betin@01012023`

Uso recomendado:

- apenas para desenvolvimento inicial
- rotacionar ou sobrescrever por variáveis de ambiente em ambientes reais

## Variáveis de Ambiente

Backend:

- `ALBERTINA_DATABASE_URL`
  - quando começa com `postgres://` ou `postgresql://`, o backend usa PostgreSQL/Supabase

- `DATABASE_URL`
  - fallback compatível para a URL do banco

- `ALBERTINA_ADMIN_EMAIL`
  - e-mail do administrador inicial

- `ALBERTINA_ADMIN_PASSWORD`
  - senha do administrador inicial

- `OLIST_REDIRECT_URI`
  - padrão: `http://localhost:3500/olist/callback`

- `OLIST_CLIENT_ID`
  - `client_id` usado na geração da URL oficial de autorização

Frontend:

- `VITE_API_BASE_URL`
  - padrão: `http://localhost:8000/api`

## Execução Local

### Requisitos

- `Python 3.11+`
- `Node.js 20+`
- `npm`

### Backend

No diretório `backend/`:

```bash
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Disponível em:

- `http://localhost:8000`

Health check:

- `GET http://localhost:8000/api/health`

Exemplo de resposta:

```json
{
  "status": "ok",
  "database": "postgresql"
}
```

### Frontend

No diretório `frontend/`:

```bash
npm install
npm run dev
```

Disponível em:

- `http://localhost:3500`

### Validação de frontend

No diretório `frontend/`:

```bash
npm run lint
npm run build
```

## CORS

Origens atualmente permitidas no backend:

- `http://localhost:3500`
- `http://127.0.0.1:3500`

Se o frontend for servido em outra origem, a lista precisa ser ajustada em `backend/app.py`.

## API Atual

### Saúde

- `GET /api/health`
  - retorna o status do backend e o mecanismo de banco em uso

### Autenticação

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

Exemplo de login:

```json
{
  "email": "admin@empresa.com",
  "password": "Betin@01012023"
}
```

### Usuários

- `GET /api/users`
- `POST /api/users`
- `PATCH /api/users/{user_id}/password`
- `PATCH /api/users/{user_id}/status`
- `DELETE /api/users/{user_id}`

Exemplo de criação:

```json
{
  "email": "novo.admin@empresa.com",
  "password": "SenhaSegura123",
  "status": "Ativo"
}
```

Exemplo de troca de senha:

```json
{
  "password": "NovaSenha123",
  "confirmPassword": "NovaSenha123"
}
```

Exemplo de mudança de status:

```json
{
  "status": "Inativo"
}
```

### Auditoria

- `GET /api/audit`
  - endpoint operacional ainda usado para trilhas resumidas na interface administrativa

### Conexões

- `GET /api/connections/overview`
- `PATCH /api/connections/olist/settings`
- `POST /api/connections/olist/connect`
- `POST /api/connections/olist/callback`
- `POST /api/connections/olist/renew-token`
- `GET /api/connections/olist/api-test`
- `GET /api/extraction/overview`
- `POST /api/extraction/run`
- `POST /api/extraction/stop`
- `GET /api/extraction/executions/{execution_id}`

Rotas legadas preservadas:

- `GET /api/olist/overview`
- `POST /api/olist/callback`

Exemplo resumido de `GET /api/connections/overview`:

```json
{
  "olist": {
    "status": "Conectada",
    "tokenStatus": "Token ativo",
    "clientId": "tiny-api-...",
    "redirectUri": "http://localhost:3500/olist/callback"
  },
  "supabase": {
    "status": "Conectado",
    "provider": "Supabase"
  },
  "logs": []
}
```

Exemplo resumido de `GET /api/connections/olist/api-test`:

```json
{
  "status": "ok",
  "detail": "A API real da Olist respondeu com sucesso.",
  "resource": "categorias/todas"
}
```

### Reset operacional da Olist

- Para limpar dados operacionais da Olist sem perder o `client_secret`, use:

```bash
python scripts/reset_olist_runtime.py
```

- Para apenas restaurar/aplicar as configuracoes da conexao Olist sem limpar tabelas, use:

```bash
python scripts/reset_olist_runtime.py --settings-only
```

- Para simular antes de executar:

```bash
python scripts/reset_olist_runtime.py --dry-run
```

- O script preserva o `client_secret` atual do banco e, se ele estiver vazio, reutiliza o valor presente em `backend/.env`.
- O reset completo limpa `olist_admin`, `olist_raw`, `olist_core`, `public.connection_logs` e atualiza as materialized views de `olist_mart`.
- So use `--wipe-client-secret` se quiser apagar explicitamente o segredo salvo.

## Integração Olist

Referências oficiais:

- `https://api-docs.erp.olist.com/api-reference/`
- `https://api-docs.erp.olist.com/documentação/comecando/autenticação`
- `https://api-docs.erp.olist.com/documentação/comecando/limites-de-consulta`

Premissas confirmadas no projeto:

- a API pública usa `OAuth 2 Authorization Code`
- a base utilizada é `https://api.tiny.com.br/public-api/v3/`
- as chamadas usam `Authorization: Bearer <token>`
- o rate limit é exposto por headers

Situação atual da integração:

- geração real da URL de autorização
- callback validando `state`
- troca real de código por tokens
- renovação real com `refresh_token`
- persistência de tokens e logs no banco
- validação real da API por recurso documentado
- extração raw com paginação, retry, controle incremental e persistência operacional no Supabase
- garantia de uma única execução concorrente com trava global no PostgreSQL
- parada segura com redução de latência para entidades pesadas como `contacts`
- painel executivo da execução com destaque de erros, velocidade por entidade, ETA local e download do log completo por execução

Recurso atualmente usado para validação:

- `GET https://api.tiny.com.br/public-api/v3/categorias/todas`

## Documentação De Fluxo De Dados

- documento visual amplo da extração: `docs/olist_extraction_data_flow.html`
- matriz consolidada de campos: `docs/olist_mapping_matrix_consolidated.md`
- guia técnico de mapeamento: `docs/olist_mapping_guide.md`

## Erros Mais Relevantes

- `400 Bad Request`
  - tentativa de desativar ou excluir o próprio usuário
  - `state` OAuth inválido ou expirado

- `401 Unauthorized`
  - sessão ausente, inválida ou expirada
  - credenciais incorretas

- `403 Forbidden`
  - usuário inativo

- `404 Not Found`
  - usuário inexistente

- `409 Conflict`
  - e-mail já cadastrado
  - operação da API Olist sem OAuth concluído

- `422 Unprocessable Entity`
  - e-mail inválido
  - senha inválida
  - status inválido
  - callback OAuth incompleto

## Segurança

Cuidados importantes:

- `files/Cofre.txt` contém segredos locais e não deve ir para repositórios públicos
- credenciais expostas em materiais locais devem ser rotacionadas
- senhas não são armazenadas em texto puro
- `client_secret`, `access_token` e `refresh_token` ainda precisam evoluir para criptografia em repouso
- ambientes reais devem usar `.env` seguro ou cofre apropriado

Limitações atuais:

- fallback local em `SQLite` mantido para desenvolvimento
- ausência de `RLS` e multi-tenant
- ausência de criptografia dedicada para segredos OAuth em repouso

## Roadmap

Próximos passos recomendados:

1. ampliar a carga normalizada de `olist_raw.api_payloads` para `olist_core.*` nas entidades já extraídas
2. consolidar migrations versionadas para colunas complementares atualmente garantidas pelo bootstrap runtime
3. criptografar segredos OAuth em repouso
4. ampliar observabilidade de worker, locks, heartbeat e refresh analítico
5. evoluir operação para ambientes não locais com configuração segura e publicação controlada
6. manter documentação técnica e executiva sincronizada com catálogo, schema e interface operacional

## Nota Final

Este documento descreve o estado implementado do projeto no momento atual. Sempre que backend, frontend, banco, OAuth ou integração Olist evoluírem, este `README` deve ser atualizado junto com o código para evitar divergência operacional.
