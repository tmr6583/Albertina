# Projeto De IA Para Consulta A Dados ERP

Documento consolidado da arquitetura alvo e do plano de execução do projeto de IA para consulta em linguagem natural sobre os dados do ERP Olist no contexto do projeto `Albertina`.

## Objetivo

Construir uma solução onde usuários internos consultam dados do ERP em linguagem natural, com respostas seguras, auditáveis, semanticamente consistentes e baseadas prioritariamente na camada analítica `RAW -> CORE -> MART` já existente no projeto.

## Escopo Definido

- escopo inicial da solução: completo na arquitetura
- autenticação inicial: usuários internos
- domínios do MVP: `vendas`, `estoque` e `financeiro`
- frequência operacional considerada: `lote diário`
- perfil de uso esperado: misto, com usuários executivos, operacionais e analíticos

## Contexto Atual Do Albertina

- a integração Olist -> Supabase já opera com fluxo `RAW -> CORE -> MART`
- o `core_sync` já promove o delta da execução com base em `execution_id`
- a `MART` já está disponível como camada preferencial de leitura analítica
- a base atual observada ainda está em porte pequeno a médio-baixo para dados de negócio, com maior massa em telemetria e staging operacional
- a arquitetura da aplicação já está baseada em `FastAPI` no backend e interface web no frontend

## Visão Geral

Uma arquitetura stateless onde a IA atende perguntas em linguagem natural por meio de `FastAPI`, usa `function calling` como mecanismo principal de acesso seguro aos dados, consulta preferencialmente `olist_mart`, complementa respostas com `RAG` para contexto semântico e restringe agentes a fluxos supervisionados.

## Fluxo Da Solução

1. o usuário autenticado envia uma pergunta pela interface
2. o frontend encaminha a solicitação autenticada ao backend
3. o backend resolve contexto de usuário, tenant e perfil
4. o orquestrador classifica a intenção da pergunta
5. a IA escolhe o caminho adequado:
   - `SQL + function calling` para perguntas estruturadas
   - `RAG` para glossário, documentação e regras
   - fluxo híbrido para perguntas com dado + explicação
   - agente restrito para perguntas compostas
6. as tools consultam preferencialmente `olist_mart` e, quando necessário, `olist_core`
7. o backend consolida a resposta, registra auditoria e devolve evidências
8. o frontend exibe resposta, tabela de apoio, filtros e origem dos dados

## Stack Recomendada

### Banco

- `Supabase/PostgreSQL`: base principal do projeto, compatível com o cenário atual, com suporte maduro a autenticação, `RLS`, APIs e operação relacional
- `pgvector`: extensão recomendada para concentrar a camada vetorial no mesmo banco, reduzindo complexidade operacional e mantendo consistência entre dado relacional e semântico

### Backend

- `Python/FastAPI`: aderente à stack do projeto, adequado para APIs stateless, integração com LLMs, tools seguras e orquestração de consulta

### Frontend

- `Next.js/React`: recomendado para a experiência final de consulta, histórico, visualização tabular e painéis executivos com rotas protegidas

### Camada De IA

- `OpenAI`: recomendado para classificação de intenção, síntese de resposta e `function calling`
- `LangChain`: recomendado como orquestrador principal de tools, prompts, roteamento e cadeias híbridas de consulta
- `LlamaIndex`: pode ser usado complementarmente ou como alternativa caso a prioridade futura seja ampliar a camada de recuperação e semântica documental

### Deploy

- `containers` para backend e frontend: opção mais compatível com escalabilidade horizontal e isolamento entre camadas
- jobs Python agendados para sincronização e atualização semântica: mantêm a consulta online desacoplada do pipeline de carga do ERP

## Princípios Arquiteturais

- priorizar `MART` como camada de consumo da IA
- usar `CORE` apenas quando a pergunta exigir detalhe ainda não materializado
- nunca expor `RAW` diretamente para perguntas de negócio
- manter backend e frontend stateless onde possível
- restringir o LLM a um catálogo de tools aprovadas
- auditar toda consulta gerada pela IA
- separar claramente consulta de dados estruturados e recuperação de contexto documental

## Fontes De Dados Prioritárias Do MVP

### Vendas

- `olist_mart.vw_fact_orders`
- `olist_mart.vw_fact_order_items`

### Estoque

- `olist_mart.vw_fact_inventory`
- `olist_mart.vw_dim_products`

### Financeiro

- `olist_mart.vw_fact_receivables`
- `olist_mart.vw_fact_payables`

## Perguntas Prioritárias Do MVP

### Vendas

- qual foi o faturamento no período
- quantos pedidos foram emitidos no período
- qual foi o ticket médio
- quais clientes mais compraram
- quais produtos mais venderam por valor
- quais produtos mais venderam por quantidade
- como evoluíram as vendas por dia, semana ou mês
- qual canal mais faturou
- qual vendedor mais vendeu

### Estoque

- qual é o estoque disponível por produto
- quais produtos estão com estoque baixo
- quais produtos estão sem estoque
- qual depósito concentra mais estoque
- qual é o estoque físico, reservado e disponível por item

### Financeiro

- qual é o total a receber no período
- qual é o total em aberto a receber
- quais títulos estão vencidos
- quais clientes possuem maior valor em aberto
- qual é o total a pagar no período
- qual é o total em aberto a pagar
- quais contas a pagar estão vencidas
- quais fornecedores concentram maior valor a pagar

## Regras Funcionais Ja Esclarecidas

As definições abaixo foram esclarecidas a partir de interação conceitual com a IA do ecossistema Olist e já podem orientar a implementação inicial do MVP:

- `faturamento`: soma dos pedidos finalizados com notas fiscais autorizadas ou contas lançadas no período
- data de referência em vendas: data de finalização do pedido
- títulos vencidos: data de vencimento anterior à data atual e sem registro de quitação
- `estoque baixo`: saldo atual igual ou inferior ao estoque mínimo cadastrado
- `order_status`: legenda oficial do Olist já identificada e pronta para catalogação semântica

## Validacoes Tecnicas Ja Confirmadas

No modelo atual do Albertina, as seguintes validações já foram confirmadas:

- `order_date` vem do campo Olist `data`
- `billing_date` vem do campo Olist `dataFaturamento`
- para faturamento efetivo, a melhor regra técnica atual é usar `billing_date` com `order_status = 1`
- no dataset atual, pedidos com `order_status = 1` possuem `billing_date` e `olist_invoice_id`, enquanto pedidos com `order_status = 0` não possuem `billing_date`
- o estoque mínimo existe em `olist_core.products.raw_attributes -> estoque -> minimo`, mas ainda não está normalizado nem exposto na `MART`

## Modelo De Dados Para A Camada De IA

Além das tabelas já existentes em `olist_core` e `olist_mart`, a solução deve criar uma camada semântica própria para IA.

### Tabelas Recomendadas

- `ai_metric_catalog`: catálogo oficial de métricas, fórmulas, domínio, granularidade e fonte primária
- `ai_business_glossary`: glossário de termos de negócio, sinônimos, definições e observações semânticas
- `ai_entity_synonyms`: mapeamento entre linguagem natural do usuário e entidades reais do banco
- `ai_query_templates`: templates validados de consulta por domínio e intenção
- `ai_prompt_policies`: políticas de instrução, limites e comportamento por perfil
- `ai_query_audit`: trilha de auditoria completa das consultas feitas pela IA
- `ai_documents`: metadados de documentos carregados para contexto semântico
- `ai_document_chunks`: chunks textuais com embeddings para recuperação vetorial

### Indexação Recomendada

- índices `btree` para `tenant_id`, datas, status e IDs principais de entidade
- índices compostos em padrões de acesso como `tenant_id + data`, `tenant_id + status + data`
- índice vetorial em `pgvector` para embeddings da camada semântica

### O Que Vai Para Embedding

- glossário de métricas
- regras de negócio
- documentação do ERP
- documentação interna do projeto
- templates explicativos e descrições semânticas

### O Que Não Deve Ser Embedding Primário

- pedidos transacionais brutos
- contas financeiras como fonte principal de cálculo
- saldos e fatos analíticos que já são melhor respondidos com SQL

## Estratégia De Consulta

### 1. SQL Direto Com Function Calling

Este deve ser o caminho principal do MVP.

Justificativa:

- os dados mais valiosos do ERP são estruturados
- a necessidade de auditoria é alta
- o volume atual permite respostas rápidas sem complexidade excessiva
- perguntas de vendas, estoque e financeiro exigem precisão numérica

### 2. RAG Semântico

Este deve complementar o SQL, não substituí-lo.

Uso ideal:

- explicar métricas
- explicar regras de negócio
- responder dúvidas sobre nomenclatura
- recuperar documentação e contexto operacional

### 3. Agente Restrito

Deve entrar somente após a estabilização das tools principais.

Uso ideal:

- perguntas compostas
- decomposição de uma pergunta em múltiplas consultas
- consolidação de resposta com múltiplas fontes

Restrições:

- sem acesso direto ao banco
- sem SQL arbitrário livre
- apenas tools aprovadas e auditáveis

## Segurança

### Autenticação

- autenticação inicial com usuários internos já existentes no sistema
- uso de `JWT` para sessão e identidade de consulta

### Autorização

- perfis mínimos: `executivo`, `operacional`, `analista`, `admin`
- autorização por domínio funcional e por escopo de dados

### Isolamento

- `RLS` obrigatória no Supabase para tabelas e views expostas à IA
- filtros explícitos por `tenant_id`, `user_id` e, se necessário, `company_id`

### Proteção Do Modelo

- o LLM não acessa credenciais
- o LLM não acessa o banco diretamente
- toda leitura é mediada por tools validadas
- toda resposta relevante deve registrar auditoria

## Roadmap De Execução

## Fase 1. Descoberta Funcional E Governança

### Objetivo

Fechar escopo funcional, perfis, métricas e regras de negócio do MVP.

### Entregáveis

- catálogo inicial de perguntas
- perfis de usuário e permissões
- regras de métrica aprovadas
- escopo oficial do MVP

### Passo A Passo

1. consolidar perguntas prioritárias por domínio
2. definir métricas oficiais e fórmulas
3. confirmar escopo e prioridades do MVP
4. identificar campos sensíveis e restrições de acesso
5. aprovar regras de uso por perfil

### Critério De Saída

- perguntas, métricas e perfis aprovados

## Fase 2. Preparação Da Camada De Dados

### Objetivo

Preparar as fontes analíticas e a base semântica para consumo pela IA.

### Entregáveis

- inventário técnico da `MART` e `CORE`
- mapa semântico pergunta -> fonte
- camada semântica inicial para IA
- `pgvector` habilitado

### Passo A Passo

1. revisar as views analíticas atuais
2. mapear cada pergunta prioritária para fonte real
3. criar tabelas semânticas da IA
4. identificar gaps de visões ou campos faltantes
5. habilitar `pgvector`

### Critério De Saída

- toda pergunta do MVP possui fonte autorizada e definida

## Fase 3. Segurança E Isolamento

### Objetivo

Garantir segregação de acesso e rastreabilidade completa.

### Entregáveis

- estratégia de autenticação da IA
- políticas `RLS`
- perfis e permissões
- trilha de auditoria de consulta

### Passo A Passo

1. revisar modelo de usuários internos
2. definir claims do `JWT`
3. aplicar `RLS` nas views e tabelas expostas
4. modelar `ai_query_audit`
5. validar isolamento entre usuários e tenants

### Critério De Saída

- nenhum usuário consulta dados fora do seu escopo

## Fase 4. Catálogo De Tools E Function Calling

### Objetivo

Transformar perguntas em funções seguras, testáveis e auditáveis.

### Entregáveis

- catálogo inicial de tools
- contratos de entrada e saída
- validação de filtros

### Passo A Passo

1. definir tools por domínio
2. padronizar parâmetros, limites e filtros
3. definir payload de resposta
4. bloquear consultas fora do catálogo
5. validar cenários principais do MVP

### Tools Iniciais Recomendadas

- `consultar_resumo_vendas`
- `consultar_vendas_por_periodo`
- `consultar_top_clientes`
- `consultar_top_produtos`
- `consultar_vendas_por_canal`
- `consultar_vendas_por_vendedor`
- `consultar_estoque_produtos`
- `consultar_ruptura_estoque`
- `consultar_estoque_por_deposito`
- `consultar_receber_resumo`
- `consultar_receber_vencidos`
- `consultar_receber_por_cliente`
- `consultar_pagar_resumo`
- `consultar_pagar_vencidos`
- `consultar_pagar_por_fornecedor`
- `explicar_metrica`
- `buscar_glossario`

### Critério De Saída

- perguntas principais do MVP já podem ser respondidas sem SQL livre

## Fase 5. RAG Semântico

### Objetivo

Adicionar contexto documental e explicativo à IA.

### Entregáveis

- pipeline de embeddings
- índice vetorial no Supabase
- recuperação híbrida com filtros

### Passo A Passo

1. definir fontes documentais
2. normalizar e quebrar documentos em chunks
3. gerar embeddings
4. indexar por `tenant`, domínio, tipo e versão
5. integrar busca vetorial ao backend

### Critério De Saída

- a IA responde perguntas conceituais com base em evidências documentais

## Fase 6. Backend Orquestrador

### Objetivo

Construir a API central que autentica, roteia, consulta e responde.

### Entregáveis

- endpoints de chat e consulta
- roteador de intenção
- integração com LLM, tools e RAG

### Passo A Passo

1. criar endpoint de consulta IA
2. autenticar usuário e resolver contexto
3. classificar intenção da pergunta
4. executar tool, RAG ou fluxo híbrido
5. registrar auditoria e devolver resposta estruturada

### Critério De Saída

- backend responde perguntas do MVP com segurança e rastreabilidade

## Fase 7. Frontend De Consulta

### Objetivo

Entregar a experiência final de uso para público interno.

### Entregáveis

- tela de chat
- área de evidências
- tabela de apoio
- histórico de consultas

### Passo A Passo

1. criar tela principal de pergunta e resposta
2. exibir filtros aplicados e fonte consultada
3. exibir tabelas e resumos executivos
4. criar histórico e feedback do usuário
5. padronizar UI densa e executiva em português

### Critério De Saída

- usuários conseguem consultar e entender de onde veio a resposta

## Fase 8. Agente Restrito E Evolução

### Objetivo

Ampliar capacidade de perguntas compostas sem perder controle.

### Entregáveis

- agente limitado por catálogo de tools
- políticas de segurança e uso
- testes de robustez

### Passo A Passo

1. habilitar agente apenas para composição entre tools
2. restringir atuação por allowlist
3. bloquear ações fora do escopo
4. auditar plano e execução do agente
5. validar perguntas multi-etapas

### Critério De Saída

- perguntas compostas são resolvidas com segurança operacional

## Sequência Recomendada De Execução

1. consolidar tecnicamente as regras funcionais já esclarecidas no modelo analítico do MVP
2. preparar camada semântica e estrutural de dados
3. aplicar segurança e `RLS`
4. construir catálogo de tools
5. implementar backend orquestrador
6. implementar frontend de consulta
7. ativar `RAG` com `pgvector`
8. evoluir para agente restrito

## Riscos Principais

- métricas sem regra oficial geram respostas inconsistentes
- uso precoce de `CORE` ou `RAW` pode aumentar ruído sem necessidade
- ausência de `RLS` e auditoria compromete segurança
- embedding de fatos transacionais puros reduz precisão em consultas numéricas
- agente livre antes do catálogo de tools aumenta risco operacional

## Decisões Já Tomadas

- arquitetura alvo completa
- autenticação inicial com usuários internos
- domínios do MVP: `vendas`, `estoque`, `financeiro`
- leitura principal da IA deve ocorrer em `olist_mart`
- `function calling` será o mecanismo principal de acesso aos dados
- `RAG` será complementar ao SQL

## Pendências De Decisão

- decidir se as consultas de vencidos usarão filtro complementar por `status`
- normalizar o estoque mínimo em coluna ou visão analítica dedicada
- padronizar se a UI e as tools mostrarão `order_status` como código, rótulo ou ambos
- decidir se será criada uma view semântica específica para faturamento efetivo baseada em `billing_date` e `order_status = 1`

## Próximo Passo Prático

Executar a consolidação das regras funcionais do MVP em uma matriz contendo:

- nome da métrica
- definição oficial
- fonte de dados
- filtro temporal
- regra de cálculo
- tool responsável
- perfil autorizado

## Resultado Esperado

Ao final da execução deste plano, o Albertina terá uma camada de IA corporativa para consulta ao ERP com:

- respostas em linguagem natural
- precisão baseada em SQL controlado
- explicação semântica via `RAG`
- segurança multiusuário
- trilha de auditoria
- base evolutiva para agentes restritos
