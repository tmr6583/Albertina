# Albertina

Aplicação administrativa para autenticação própria, gestão de usuários e preparação da futura integração com o ERP Olist. O projeto já possui frontend React/Vite e backend FastAPI operacionais, com persistência local em SQLite e foco em evolução posterior para integrações reais com a API da Olist e armazenamento analítico em PostgreSQL/Supabase.

## Resumo Executivo

Estado atual do projeto:

- frontend administrativo funcional em `React + Vite`
- backend funcional em `FastAPI`
- autenticação própria por e-mail e senha
- persistência local em `SQLite`
- sessões autenticadas via token Bearer
- trilha de auditoria administrativa
- páginas reais para usuários, conexão Olist e auditoria
- integração Olist ainda em estágio preparatório, sem OAuth real implementado

Objetivo de evolução:

- conectar a aplicação a uma conta Olist via `OAuth 2 Authorization Code`
- consumir entidades reais da API pública da Olist
- persistir dados operacionais e analíticos em `PostgreSQL / Supabase`
- implementar sincronizações full e incrementais com rastreabilidade

## Status Atual

O repositório já implementa os seguintes recursos:

- tela de login com autenticação própria
- restauração de sessão autenticada no frontend
- logout com revogação de sessão
- página de administração de usuários
- criação de usuário administrativo
- exclusão de usuário administrativo
- alteração de senha de usuário
- ativação e desativação de usuários
- bloqueio para impedir exclusão do usuário autenticado
- bloqueio para impedir desativação do usuário autenticado
- bloqueio de login para usuários inativos
- página de auditoria com eventos recentes
- página de visão geral da integração Olist
- auditoria básica persistida no backend
- identidade visual em PT-BR com título da aba fixo em `Albertina`

O que ainda não está implementado:

- fluxo OAuth real com a Olist
- armazenamento seguro de `client_secret`, `access_token` e `refresh_token`
- sincronização real de entidades ERP
- persistência em PostgreSQL/Supabase
- catálogo de recursos da API Olist
- checkpoints de sincronização
- jobs manuais e incrementais de extração/carga

## Arquitetura Atual

Fluxo da aplicação hoje:

1. O usuário acessa o frontend em `http://localhost:3500`.
2. O login envia credenciais para o backend em `http://localhost:8000/api/auth/login`.
3. O backend valida o e-mail, verifica o hash da senha e cria uma sessão.
4. O token da sessão é retornado ao frontend e armazenado em `localStorage`.
5. O frontend reutiliza esse token nas chamadas autenticadas via header `Authorization: Bearer <token>`.
6. O backend valida a sessão ativa, o prazo de expiração e o status do usuário.
7. As páginas autenticadas consomem usuários, auditoria e visão geral da integração Olist.

Componentes principais:

- `frontend/`: interface administrativa React
- `backend/`: API FastAPI e persistência SQLite
- `backend/data/albertina.db`: banco SQLite local
- `files/`: materiais de apoio e insumos visuais/locais

## Stack Atual

Frontend:

- `React 19`
- `Vite 8`
- `ESLint`
- CSS puro

Backend:

- `Python`
- `FastAPI`
- `Uvicorn`
- `SQLite`
- `Pydantic`

Segurança atual:

- hash de senha com `PBKDF2-HMAC SHA-256`
- hash de token de sessão com `SHA-256`
- comparação segura de hash com `hmac.compare_digest`

Observação importante:

- o código atual usa `PBKDF2-HMAC SHA-256` para senhas
- o uso de `Argon2id` continua sendo uma recomendação para futura evolução

## Estrutura do Repositório

```text
Albertina/
|-- README.md
|-- backend/
|   |-- app.py
|   |-- requirements.txt
|   `-- data/
|       `-- albertina.db
|-- files/
|   |-- Albertina.png
|   |-- Cofre.txt
|   |-- Logo_Azul.jpg
|   `-- ui-test-login.png
`-- frontend/
    |-- index.html
    |-- package.json
    |-- vite.config.js
    |-- public/
    |   |-- albertina.png
    |   |-- favicon.svg
    |   |-- icons.svg
    |   `-- logo-azul.jpg
    `-- src/
        |-- App.css
        |-- App.jsx
        |-- api.js
        |-- index.css
        `-- main.jsx
```

## Frontend Atual

Rotas da aplicação:

- `/`: login
- `/usuarios`: administração de usuários
- `/olist`: visão geral da integração Olist
- `/auditoria`: linha do tempo de auditoria

Comportamentos implementados no frontend:

- controle local de sessão com token em `localStorage`
- roteamento por `history.pushState` e `popstate`
- hidratação automática da sessão via `/api/auth/me`
- carregamento conjunto de usuários, auditoria e overview Olist
- filtragem de usuários por texto e status
- modais para criar usuário e alterar senha
- confirmação antes de excluir usuário
- confirmação antes de ativar ou desativar usuário
- tratamento centralizado de erros HTTP em `src/api.js`

Observações de UI:

- idioma padrão em `pt-BR`
- título da aba fixo em `Albertina`
- fonte base `Arial`
- menu principal no topo alinhado à esquerda
- texto dos botões do menu em uma linha

## Backend Atual

O backend está concentrado em `backend/app.py` e sobe uma API FastAPI única com bootstrap automático da base local.

Inicialização:

- cria o diretório `backend/data/` se necessário
- cria as tabelas SQLite na primeira execução
- cria automaticamente o usuário administrador inicial se a base estiver vazia

Regras de autenticação:

- login sempre por e-mail
- e-mail normalizado para lowercase
- senha mínima de 8 caracteres para criação e troca de senha
- sessão com duração de `12 horas`
- sessão inválida ou expirada retorna `401`
- usuário inativo autenticado retorna `403`

Regras de gestão de usuários:

- todos os usuários criados hoje recebem papel `Administrador`
- o status permitido é `Ativo` ou `Inativo`
- o próprio usuário autenticado não pode ser desativado
- o próprio usuário autenticado não pode ser excluído
- ao desativar um usuário, as sessões ativas desse usuário são revogadas

## Persistência Atual em SQLite

Banco local:

- arquivo: `backend/data/albertina.db`

Tabelas existentes:

### `users`

Campos atuais:

- `id TEXT PRIMARY KEY`
- `email TEXT NOT NULL UNIQUE`
- `password_hash TEXT NOT NULL`
- `role TEXT NOT NULL`
- `status TEXT NOT NULL`
- `initials TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `last_access_at TEXT NULL`

### `sessions`

Campos atuais:

- `id TEXT PRIMARY KEY`
- `user_id TEXT NOT NULL`
- `token_hash TEXT NOT NULL UNIQUE`
- `created_at TEXT NOT NULL`
- `expires_at TEXT NOT NULL`
- `revoked_at TEXT NULL`

### `audits`

Campos atuais:

- `id TEXT PRIMARY KEY`
- `title TEXT NOT NULL`
- `description TEXT NOT NULL`
- `tone TEXT NOT NULL`
- `created_at TEXT NOT NULL`

Observação:

- esta modelagem é a base operacional atual
- a modelagem futura para Supabase/PostgreSQL será mais ampla, incluindo conexão Olist, tokens OAuth, checkpoints e tabelas de domínio ERP

## Credencial Inicial

Por padrão, o bootstrap cria:

- e-mail: `admin@empresa.com`
- senha: `Betin@01012023`

Importante:

- essas credenciais são adequadas apenas para desenvolvimento local inicial
- elas devem ser substituídas por variáveis de ambiente ou rotacionadas em ambiente real

## Variáveis de Ambiente

Variáveis já suportadas pelo backend:

- `ALBERTINA_ADMIN_EMAIL`
  - valor padrão: `admin@empresa.com`
  - uso: define o e-mail do usuário administrador inicial

- `ALBERTINA_ADMIN_PASSWORD`
  - valor padrão: `Betin@01012023`
  - uso: define a senha do usuário administrador inicial

- `OLIST_REDIRECT_URI`
  - valor padrão: `http://localhost:3500/olist/callback`
  - uso: informa o redirect URI exibido no overview da integração

Variável suportada pelo frontend:

- `VITE_API_BASE_URL`
  - valor padrão: `http://localhost:8000/api`
  - uso: altera a URL base da API consumida pelo frontend

## Execução Local

### Requisitos

- `Python 3.11+` ou compatível com FastAPI/Uvicorn usados no projeto
- `Node.js 20+`
- `npm`

### Subindo o backend

No diretório `backend/`:

```bash
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Backend disponível em:

- `http://localhost:8000`

Health check:

- `http://localhost:8000/api/health`

### Subindo o frontend

No diretório `frontend/`:

```bash
npm install
npm run dev
```

Frontend disponível em:

- `http://localhost:3500`

Configuração relevante do Vite:

- porta fixa `3500`
- `strictPort: true`
- host `0.0.0.0`

### Build e lint do frontend

No diretório `frontend/`:

```bash
npm run lint
npm run build
```

## CORS

O backend permite chamadas das seguintes origens:

- `http://localhost:3500`
- `http://127.0.0.1:3500`

Se o frontend for servido em outra origem, essa configuração deverá ser atualizada em `backend/app.py`.

## Endpoints da API Atual

### Saúde da aplicação

- `GET /api/health`
  - retorna o status básico do backend

Exemplo de resposta:

```json
{
  "status": "ok"
}
```

### Autenticação

- `POST /api/auth/login`
  - autentica o usuário e cria uma sessão

Payload:

```json
{
  "email": "admin@empresa.com",
  "password": "Betin@01012023"
}
```

- `GET /api/auth/me`
  - retorna o usuário autenticado
  - requer Bearer token

- `POST /api/auth/logout`
  - revoga a sessão atual
  - requer Bearer token

### Usuários

- `GET /api/users`
  - lista usuários cadastrados
  - requer Bearer token

- `POST /api/users`
  - cria um novo usuário
  - requer Bearer token

Payload:

```json
{
  "email": "novo.admin@empresa.com",
  "password": "SenhaSegura123",
  "status": "Ativo"
}
```

- `PATCH /api/users/{user_id}/password`
  - altera a senha de um usuário
  - requer Bearer token

Payload:

```json
{
  "password": "NovaSenha123",
  "confirmPassword": "NovaSenha123"
}
```

- `PATCH /api/users/{user_id}/status`
  - ativa ou desativa um usuário
  - requer Bearer token

Payload:

```json
{
  "status": "Inativo"
}
```

- `DELETE /api/users/{user_id}`
  - exclui um usuário
  - requer Bearer token

### Auditoria

- `GET /api/audit`
  - retorna até 50 eventos mais recentes
  - requer Bearer token

### Integração Olist

- `GET /api/olist/overview`
  - retorna o estado atual da integração planejada
  - requer Bearer token

Exemplo de resposta:

```json
{
  "status": "Não configurada",
  "apiBaseUrl": "https://api.tiny.com.br/public-api/v3/",
  "redirectUri": "http://localhost:3500/olist/callback",
  "authMode": "OAuth 2 Authorization Code",
  "nextStep": "Implementar a conexão OAuth real com a conta Olist."
}
```

## Comportamentos de Erro Relevantes

Códigos e cenários importantes:

- `401 Unauthorized`
  - sessão ausente
  - sessão inválida
  - sessão expirada
  - credenciais incorretas no login

- `403 Forbidden`
  - tentativa de uso de sessão com usuário inativo
  - tentativa de login com usuário inativo

- `404 Not Found`
  - usuário inexistente nas operações de alteração, status ou exclusão

- `409 Conflict`
  - criação de usuário com e-mail já existente

- `422 Unprocessable Entity`
  - e-mail inválido
  - status diferente de `Ativo` ou `Inativo`
  - confirmação de senha divergente

## Integração Olist

Fontes oficiais de referência:

- `https://api-docs.erp.olist.com/api-reference/`
- `https://api-docs.erp.olist.com/documentacao/comecando/autenticacao`
- `https://api-docs.erp.olist.com/documentacao/comecando/limites-de-consulta`

Fatos já considerados no projeto:

- a API pública usa `OAuth 2 Authorization Code`
- a base pública utilizada é `https://api.tiny.com.br/public-api/v3/`
- as chamadas autenticadas usam `Authorization: Bearer <token>`
- o rate limit é informado por headers da API
- a integração deve respeitar limites por conta

Situação atual da integração:

- ainda não existe endpoint de callback OAuth
- ainda não existe persistência de tokens Olist
- ainda não existe cliente HTTP real para entidades ERP
- a página `Conexão Olist` funciona hoje como overview preparatório e backlog técnico

## Regras e Restrições do Projeto

Diretrizes já definidas:

- nunca inventar endpoints, campos ou comportamentos da API Olist
- qualquer informação não confirmada deve ser marcada como `[A CONFIRMAR]`
- nunca executar `DROP`, `TRUNCATE` ou `DELETE` sem confirmação explícita quando isso envolver dados operacionais relevantes
- login sempre por e-mail
- evitar dados mockados para integração real
- priorizar evolução incremental e idempotente na futura carga para PostgreSQL

## Segurança

Cuidados obrigatórios:

- `files/Cofre.txt` contém segredos locais e não deve ser versionado em repositórios públicos
- credenciais expostas em material de apoio devem ser rotacionadas
- senhas nunca devem ser armazenadas em texto puro
- segredos operacionais devem migrar para `.env` seguro ou cofre apropriado
- tokens Olist, quando implementados, deverão ser protegidos adequadamente

Limitações atuais a considerar:

- a persistência atual é local em SQLite e voltada a desenvolvimento
- ainda não há criptografia de segredos OAuth porque o fluxo Olist real ainda não foi implementado
- ainda não há gestão de múltiplos tenants nem `RLS`

## Roadmap Recomendado

Próxima sequência sugerida para evolução:

1. mover credenciais locais para `.env`
2. implementar conexão OAuth real com a Olist
3. persistir `access_token` e `refresh_token` com proteção adequada
4. criar cliente HTTP para a API Olist com retry e controle de rate limit
5. modelar as primeiras entidades reais do ERP em PostgreSQL/Supabase
6. implementar sincronização full e incremental com checkpoint
7. ampliar a observabilidade técnica para jobs e integrações

## Notas Finais

Este `README` descreve o estado real do projeto no momento atual: uma aplicação administrativa já funcional para autenticação e gestão de usuários, com base local em SQLite, e uma frente de integração Olist ainda em construção. Se o código evoluir em backend, banco ou fluxo OAuth, este documento deve ser atualizado em conjunto para evitar divergência entre documentação e implementação.
