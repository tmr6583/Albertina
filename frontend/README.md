# Frontend Albertina

Frontend administrativo do projeto Albertina, construído com `React + Vite`. É responsável pela autenticação visual, navegação entre páginas administrativas, consumo da API FastAPI e operação da tela `Conexões` com a integração real da Olist.

## Visão Geral

O frontend implementa hoje:

- login por e-mail e senha
- persistência local do token de sessão
- restauração automática da sessão autenticada
- tela de administração de usuários
- modais de criação de usuário e troca de senha
- tela `Conexões` com operação real da Olist
- tela `Extração` para disparo e acompanhamento da sincronização Olist -> Supabase
- download do log completo por execução a partir do quadro `Histórico`
- feedback visual padronizado de sucesso e erro
- botão global `Sair` no cabeçalho autenticado

URL padrão do frontend:

- `http://localhost:3500`

URL padrão da API consumida:

- `http://localhost:8000/api`

## Stack

- `React 19`
- `Vite 8`
- `ESLint`
- CSS puro

## Scripts

No diretório `frontend/`:

```bash
npm run dev
npm run build
npm run lint
npm run preview
```

Descrição:

- `npm run dev`: sobe o ambiente de desenvolvimento
- `npm run build`: gera a build de produção em `dist/`
- `npm run lint`: executa o lint do projeto
- `npm run preview`: sobe o preview da build

## Execução Local

### Instalação

```bash
npm install
```

### Desenvolvimento

```bash
npm run dev
```

URL esperada:

- `http://localhost:3500`

### Build

```bash
npm run build
```

### Preview

```bash
npm run preview
```

## Configuração do Vite

O frontend usa porta fixa:

- `3500` no modo `dev`
- `3500` no modo `preview`

Características:

- `host: 0.0.0.0`
- `strictPort: true`

Se a porta `3500` estiver ocupada, o Vite não muda automaticamente para outra porta.

## Configuração da API

O cliente HTTP está centralizado em `src/api.js`.

Comportamentos atuais:

- lê o token salvo em `localStorage`
- injeta `Authorization: Bearer <token>` quando existe sessão
- injeta `Content-Type: application/json` quando existe `body`
- normaliza erros através da classe `ApiError`

Chave local da sessão:

- `albertina.auth.token`

Variável suportada:

- `VITE_API_BASE_URL`

Exemplo:

```bash
VITE_API_BASE_URL=http://localhost:8000/api
```

Sem essa variável, o frontend usa:

```text
http://localhost:8000/api
```

## Rotas da Aplicação

Rotas ativas:

- `/`: login
- `/usuarios`: administração de usuários
- `/conexoes`: operação e monitoramento das conexões
- `/extracao`: extração ERP e acompanhamento da execução
- `/olist/callback`: rota legada do retorno OAuth

Observações:

- o roteamento é interno, com `window.history`
- ainda não há `react-router`

## Funcionalidades

### Login e sessão

- autenticação por e-mail e senha
- mensagem de erro retornada pela API
- limpeza da senha após login bem-sucedido
- reidratação da sessão ao carregar a aplicação
- logout com chamada ao backend e limpeza local

### Administração de usuários

- listagem de usuários
- busca por e-mail ou papel
- filtro por status
- criação de usuário administrativo
- alteração de senha
- exclusão de usuário
- ativação e desativação de conta
- confirmação antes de ações destrutivas ou sensíveis

### Conexões

- exibição do status real da conexão Olist
- exibição do status do banco de dados
- edição administrativa do `Client Secret`
- exibição da URL de redirecionamento
- geração da URL oficial de autorização OAuth
- processamento do retorno OAuth no frontend
- renovação de token via backend
- validação da API real da Olist
- rastreabilidade dos eventos da conexão

### Extração

- disparo manual da sincronização completa da API pública Olist
- acompanhamento da execução ativa com polling automático mais frequente durante parada
- exibição da entidade atual, progresso por entidade, velocidade local, ETA local e últimas execuções
- card executivo da execução com consolidação dos logs operacionais
- consulta do detalhamento de execuções e download do log completo pelo histórico
- parada segura por botão `Parar extração`
- formatação de data e hora em `DD/MM/YYYY HH:MM:SS`

## Estrutura Relevante

```text
frontend/
|-- README.md
|-- index.html
|-- package.json
|-- vite.config.js
|-- .env.local
|-- public/
|   |-- albertina.png
|   `-- logo-azul.jpg
`-- src/
    |-- App.css
    |-- App.jsx
    |-- api.js
    |-- index.css
    `-- main.jsx
```

Arquivos principais:

- `src/App.jsx`: rotas, estado global, telas e fluxos principais
- `src/App.css`: layout e padronização visual
- `src/api.js`: cliente HTTP e gerenciamento local do token
- `src/index.css`: estilos globais
- `index.html`: título da aba e favicon

## Diretrizes Visuais Implementadas

Características já refletidas no código:

- interface em `pt-BR`
- título da aba fixo em `Albertina`
- fonte base `Arial`
- fundo branco com cards azuis
- menu principal no topo
- botão global `Sair` no lado direito do cabeçalho autenticado
- botões principais em uma linha
- `Alterar senha` em uma linha na listagem
- metadados de usuário visualmente mais discretos

## Dependência do Backend

Este frontend depende do backend Albertina para funcionar corretamente.

Endpoints consumidos atualmente:

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/users`
- `POST /api/users`
- `PATCH /api/users/{user_id}/password`
- `PATCH /api/users/{user_id}/status`
- `DELETE /api/users/{user_id}`
- `GET /api/audit`
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

Sem o backend disponível, a interface carrega, mas as operações autenticadas não funcionam.

## Limitações Atuais

- não usa `react-router`
- não usa gerenciamento de estado externo
- não possui suíte própria de testes automatizados versionada
- concentra boa parte da lógica em `App.jsx`

## Documentação Relacionada

- fluxo visual da extração: `docs/olist_extraction_data_flow.html`

## Próximos Passos Recomendados

- desacoplar `App.jsx` em componentes e hooks menores
- introduzir testes de interface versionados para fluxos críticos
- considerar `react-router` se a navegação crescer
- continuar a evolução da tela `Conexões` junto com os recursos reais da API Olist
