# Especificacao Tecnica Das Tabelas Semanticas Da IA

Documento técnico para modelagem da camada semântica da IA no projeto `Albertina`, apoiando consultas em linguagem natural sobre os dados do ERP Olist.

## Objetivo

Definir as tabelas semânticas mínimas para:

- explicar métricas e termos de negócio
- mapear linguagem natural para entidades reais do banco
- registrar templates e políticas de consulta
- auditar o comportamento da IA
- sustentar `RAG` com `pgvector`

## Princípios

- o dado transacional continua em `olist_core` e `olist_mart`
- a camada semântica não duplica fatos de negócio sem necessidade
- todo objeto semântico deve ser multiusuário e preparado para `tenant_id`
- a semântica precisa ser versionável, auditável e aderente à operação real
- a camada deve servir tanto para `function calling` quanto para `RAG`

## Schema Recomendado

- schema recomendado: `olist_ai`

Justificativa:

- separa claramente a camada semântica da camada operacional
- facilita governança, permissões e rastreamento
- evita misturar objetos de IA com tabelas de negócio e administração já existentes

## Tabelas Principais

### 1. `olist_ai.ai_metric_catalog`

Finalidade:

- armazenar o catálogo oficial de métricas usadas pela IA
- registrar definição, fórmula, fonte e política de uso

Campos recomendados:

| Campo | Tipo sugerido | Obrigatorio | Descricao |
|---|---|---|---|
| `metric_id` | `uuid` | sim | identificador técnico da métrica |
| `tenant_id` | `uuid` | sim | escopo do tenant |
| `metric_code` | `text` | sim | código estável da métrica |
| `metric_name` | `text` | sim | nome amigável da métrica |
| `domain` | `text` | sim | domínio como `vendas`, `estoque`, `financeiro` |
| `definition` | `text` | sim | definição oficial da métrica |
| `formula_description` | `text` | não | fórmula em linguagem natural |
| `sql_rule_summary` | `text` | não | resumo da regra SQL esperada |
| `source_schema` | `text` | sim | schema da fonte principal |
| `source_object` | `text` | sim | view ou tabela principal |
| `time_basis` | `text` | não | base temporal oficial, como `order_date` ou `due_date` |
| `default_filters` | `jsonb` | não | filtros padrão da métrica |
| `allowed_profiles` | `jsonb` | não | perfis autorizados |
| `status` | `text` | sim | `draft`, `active`, `deprecated` |
| `owner_area` | `text` | não | área dona da métrica |
| `business_notes` | `text` | não | observações semânticas |
| `created_at` | `timestamptz` | sim | data de criação |
| `updated_at` | `timestamptz` | sim | data de atualização |

Índices recomendados:

- `pk(metric_id)`
- `unique(tenant_id, metric_code)`
- `idx_ai_metric_catalog_tenant_domain`
- `idx_ai_metric_catalog_status`

### 2. `olist_ai.ai_business_glossary`

Finalidade:

- guardar glossário oficial de termos do ERP e do negócio
- servir como base para explicações, sinônimos e RAG

Campos recomendados:

| Campo | Tipo sugerido | Obrigatorio | Descricao |
|---|---|---|---|
| `term_id` | `uuid` | sim | identificador técnico do termo |
| `tenant_id` | `uuid` | sim | escopo do tenant |
| `term` | `text` | sim | termo principal |
| `normalized_term` | `text` | sim | termo normalizado para busca |
| `aliases` | `jsonb` | não | lista de sinônimos e variações |
| `domain` | `text` | sim | domínio do termo |
| `definition` | `text` | sim | definição oficial |
| `business_notes` | `text` | não | notas complementares |
| `source_reference` | `text` | não | referência documental da definição |
| `status` | `text` | sim | `draft`, `active`, `deprecated` |
| `created_at` | `timestamptz` | sim | data de criação |
| `updated_at` | `timestamptz` | sim | data de atualização |

Índices recomendados:

- `pk(term_id)`
- `unique(tenant_id, normalized_term)`
- `gin(aliases jsonb_path_ops)` quando aplicável
- `idx_ai_business_glossary_domain`

### 3. `olist_ai.ai_entity_synonyms`

Finalidade:

- mapear linguagem natural do usuário para objetos reais do banco
- reduzir ambiguidade entre nome de negócio e nome físico

Campos recomendados:

| Campo | Tipo sugerido | Obrigatorio | Descricao |
|---|---|---|---|
| `synonym_id` | `uuid` | sim | identificador técnico |
| `tenant_id` | `uuid` | sim | escopo do tenant |
| `entity_type` | `text` | sim | tipo da entidade, como `table`, `view`, `metric`, `field`, `tool` |
| `business_name` | `text` | sim | nome de negócio |
| `normalized_name` | `text` | sim | nome normalizado |
| `synonyms` | `jsonb` | sim | lista de sinônimos |
| `target_schema` | `text` | não | schema alvo |
| `target_object` | `text` | não | tabela, view ou objeto alvo |
| `target_field` | `text` | não | campo alvo se houver |
| `confidence_level` | `numeric` | não | confiança da associação |
| `status` | `text` | sim | `draft`, `active`, `deprecated` |
| `created_at` | `timestamptz` | sim | data de criação |
| `updated_at` | `timestamptz` | sim | data de atualização |

Índices recomendados:

- `pk(synonym_id)`
- `idx_ai_entity_synonyms_tenant_type`
- `gin(synonyms jsonb_path_ops)`
- `idx_ai_entity_synonyms_target`

### 4. `olist_ai.ai_query_templates`

Finalidade:

- armazenar templates validados de consulta
- servir de contrato semântico entre intenção, tool e fonte

Campos recomendados:

| Campo | Tipo sugerido | Obrigatorio | Descricao |
|---|---|---|---|
| `template_id` | `uuid` | sim | identificador técnico |
| `tenant_id` | `uuid` | sim | escopo do tenant |
| `tool_name` | `text` | sim | nome da tool responsável |
| `intent_name` | `text` | sim | nome padronizado da intenção |
| `template_description` | `text` | sim | descrição funcional |
| `domain` | `text` | sim | domínio da consulta |
| `source_schema` | `text` | sim | schema da fonte |
| `source_object` | `text` | sim | view ou tabela principal |
| `allowed_filters` | `jsonb` | não | filtros permitidos |
| `required_filters` | `jsonb` | não | filtros obrigatórios |
| `default_limit` | `integer` | não | limite padrão |
| `max_limit` | `integer` | não | limite máximo |
| `response_shape` | `jsonb` | não | formato da resposta |
| `status` | `text` | sim | `draft`, `active`, `deprecated` |
| `created_at` | `timestamptz` | sim | data de criação |
| `updated_at` | `timestamptz` | sim | data de atualização |

Índices recomendados:

- `pk(template_id)`
- `idx_ai_query_templates_tenant_tool`
- `idx_ai_query_templates_intent`

### 5. `olist_ai.ai_prompt_policies`

Finalidade:

- registrar políticas operacionais para o comportamento do modelo
- separar instruções semânticas do código da aplicação

Campos recomendados:

| Campo | Tipo sugerido | Obrigatorio | Descricao |
|---|---|---|---|
| `policy_id` | `uuid` | sim | identificador técnico |
| `tenant_id` | `uuid` | sim | escopo do tenant |
| `policy_name` | `text` | sim | nome da política |
| `policy_scope` | `text` | sim | escopo como `global`, `domain`, `tool`, `profile` |
| `target_name` | `text` | não | alvo da política |
| `policy_text` | `text` | sim | texto da política |
| `priority_order` | `integer` | não | ordem de precedência |
| `status` | `text` | sim | `draft`, `active`, `deprecated` |
| `created_at` | `timestamptz` | sim | data de criação |
| `updated_at` | `timestamptz` | sim | data de atualização |

Índices recomendados:

- `pk(policy_id)`
- `idx_ai_prompt_policies_scope_target`

### 6. `olist_ai.ai_query_audit`

Finalidade:

- registrar rastreabilidade completa das consultas feitas pela IA
- apoiar auditoria, troubleshooting e governança

Campos recomendados:

| Campo | Tipo sugerido | Obrigatorio | Descricao |
|---|---|---|---|
| `audit_id` | `uuid` | sim | identificador técnico |
| `tenant_id` | `uuid` | sim | escopo do tenant |
| `user_id` | `uuid` | sim | usuário que perguntou |
| `session_id` | `text` | não | sessão lógica da conversa |
| `question_text` | `text` | sim | pergunta original |
| `normalized_intent` | `text` | não | intenção classificada |
| `tool_name` | `text` | não | tool utilizada |
| `source_schema` | `text` | não | schema consultado |
| `source_object` | `text` | não | objeto consultado |
| `filters_json` | `jsonb` | não | filtros efetivamente usados |
| `sql_fingerprint` | `text` | não | hash ou fingerprint do SQL |
| `row_count` | `integer` | não | quantidade de linhas retornadas |
| `result_summary` | `text` | não | resumo da resposta |
| `llm_model` | `text` | não | modelo usado |
| `started_at` | `timestamptz` | sim | início do processamento |
| `finished_at` | `timestamptz` | não | fim do processamento |
| `status` | `text` | sim | `success`, `error`, `blocked` |
| `error_message` | `text` | não | erro quando houver |

Índices recomendados:

- `pk(audit_id)`
- `idx_ai_query_audit_tenant_user_started`
- `idx_ai_query_audit_status`
- `idx_ai_query_audit_tool_name`

### 7. `olist_ai.ai_documents`

Finalidade:

- armazenar metadados dos documentos usados no contexto semântico

Campos recomendados:

| Campo | Tipo sugerido | Obrigatorio | Descricao |
|---|---|---|---|
| `document_id` | `uuid` | sim | identificador técnico |
| `tenant_id` | `uuid` | sim | escopo do tenant |
| `document_type` | `text` | sim | tipo como `glossario`, `guia`, `api`, `faq` |
| `document_title` | `text` | sim | título do documento |
| `source_uri` | `text` | não | origem do documento |
| `source_system` | `text` | não | sistema de origem |
| `domain` | `text` | não | domínio do conteúdo |
| `version_label` | `text` | não | versão lógica |
| `status` | `text` | sim | `draft`, `active`, `archived` |
| `created_at` | `timestamptz` | sim | data de criação |
| `updated_at` | `timestamptz` | sim | data de atualização |

Índices recomendados:

- `pk(document_id)`
- `idx_ai_documents_tenant_type`
- `idx_ai_documents_domain`

### 8. `olist_ai.ai_document_chunks`

Finalidade:

- armazenar chunks indexáveis com embeddings para busca vetorial

Campos recomendados:

| Campo | Tipo sugerido | Obrigatorio | Descricao |
|---|---|---|---|
| `chunk_id` | `uuid` | sim | identificador técnico |
| `tenant_id` | `uuid` | sim | escopo do tenant |
| `document_id` | `uuid` | sim | documento pai |
| `chunk_order` | `integer` | sim | posição do chunk |
| `domain` | `text` | não | domínio do conteúdo |
| `chunk_text` | `text` | sim | texto do chunk |
| `chunk_tokens` | `integer` | não | quantidade estimada de tokens |
| `embedding` | `vector` | sim | embedding vetorial |
| `metadata_json` | `jsonb` | não | metadados adicionais |
| `created_at` | `timestamptz` | sim | data de criação |
| `updated_at` | `timestamptz` | sim | data de atualização |

Índices recomendados:

- `pk(chunk_id)`
- `idx_ai_document_chunks_tenant_document`
- índice vetorial `ivfflat` ou similar sobre `embedding`

## Relacionamentos Recomendados

- `ai_document_chunks.document_id -> ai_documents.document_id`
- `ai_metric_catalog.tenant_id`, `ai_business_glossary.tenant_id`, `ai_entity_synonyms.tenant_id`, `ai_query_templates.tenant_id`, `ai_prompt_policies.tenant_id`, `ai_query_audit.tenant_id`, `ai_documents.tenant_id`, `ai_document_chunks.tenant_id` devem seguir o mesmo escopo de tenant

## Politicas De Seguranca

- aplicar `RLS` em todas as tabelas do schema `olist_ai`
- permitir leitura conforme o `tenant_id` do usuário autenticado
- restringir escrita a perfis administrativos e processos internos autorizados
- impedir que usuários comuns editem definições semânticas diretamente

## Politicas De Atualizacao

- métricas e glossário devem ser versionados por revisão controlada
- documentos importados devem ser reprocessados quando houver nova versão
- embeddings devem ser recalculados apenas para documentos alterados
- logs de auditoria não devem ser sobrescritos

## Estrategia De Povoamento Inicial

1. carregar métricas do MVP em `ai_metric_catalog`
2. carregar termos funcionais e siglas em `ai_business_glossary`
3. carregar sinônimos frequentes em `ai_entity_synonyms`
4. registrar templates iniciais de consulta em `ai_query_templates`
5. registrar políticas globais de comportamento em `ai_prompt_policies`
6. indexar documentação principal do projeto e do Olist em `ai_documents` e `ai_document_chunks`

## DDL De Referencia

Exemplo simplificado para `ai_metric_catalog`:

```sql
create schema if not exists olist_ai;

create table if not exists olist_ai.ai_metric_catalog (
    metric_id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    metric_code text not null,
    metric_name text not null,
    domain text not null,
    definition text not null,
    formula_description text,
    sql_rule_summary text,
    source_schema text not null,
    source_object text not null,
    time_basis text,
    default_filters jsonb,
    allowed_profiles jsonb,
    status text not null default 'draft',
    owner_area text,
    business_notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_ai_metric_catalog unique (tenant_id, metric_code)
);
```

Exemplo simplificado para `ai_document_chunks`:

```sql
create table if not exists olist_ai.ai_document_chunks (
    chunk_id uuid primary key default gen_random_uuid(),
    tenant_id uuid not null,
    document_id uuid not null,
    chunk_order integer not null,
    domain text,
    chunk_text text not null,
    chunk_tokens integer,
    embedding vector(1536) not null,
    metadata_json jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint fk_ai_document_chunks_document
        foreign key (document_id)
        references olist_ai.ai_documents (document_id)
);
```

## Ordem Recomendada De Implementacao

1. criar schema `olist_ai`
2. habilitar `pgvector`
3. criar `ai_metric_catalog`
4. criar `ai_business_glossary`
5. criar `ai_entity_synonyms`
6. criar `ai_query_templates`
7. criar `ai_prompt_policies`
8. criar `ai_query_audit`
9. criar `ai_documents`
10. criar `ai_document_chunks`
11. aplicar `RLS`
12. popular dados iniciais do MVP

## Resultado Esperado

Ao final desta etapa, o projeto terá uma base semântica estruturada para suportar:

- explicação de métricas e termos
- roteamento semântico de perguntas
- auditoria de consulta
- recuperação vetorial com `RAG`
- governança de comportamento da IA
