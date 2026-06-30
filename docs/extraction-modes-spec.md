# Especificacao Tecnica - Modos de Extracao Olist

## Objetivo

O projeto passa a ter dois modos operacionais de sincronizacao:

1. `Incremental`
2. `Conciliacao`

Os dois modos compartilham o mesmo slot global de execucao. Nunca pode existir concorrencia entre execucoes, independentemente do tipo solicitado.

## Definicao Operacional de "Absolutamente Sincronizado"

A execucao de conciliacao sera disparada apenas em janelas em que o ERP Olist nao estara sendo utilizado por operadores humanos nem por outras automacoes de negocio.

Com essa premissa, a conciliacao deve refletir integralmente na base analitica o estado do ERP no intervalo da execucao, inclusive:

- novos registros ja existentes na origem
- registros alterados na origem
- registros que deixaram de existir na origem
- registros que mudaram de status operacional relevante na origem

## Modos de Execucao

### 1. Incremental

Modo operacional do dia a dia, acionado pelo botao `Incremental`.

Comportamento:

- usa watermark e filtros incrementais quando a API documenta `dataAtualizacao`, `dataAlteracao` ou janela equivalente
- continua fazendo `upsert` de novos e alterados na camada RAW
- nao marca ausencias como deletadas
- limpa marcacao de exclusao quando um registro reaparece
- prioriza tempo de execucao

Observacao:

- para entidades sem filtro incremental documental, o sistema pode executar uma leitura snapshot leve para manter a base atualizada, mas sem prometer deteccao de delecao nesse modo

### 2. Conciliacao

Modo de integridade, acionado pelo botao `Conciliação`.

Comportamento:

- executa varredura completa da entidade ou a janela mais ampla suportada pela API
- marca cada payload encontrado como `seen` na execucao atual
- ao fim de cada entidade, marca como deletados os registros que existiam antes e nao foram vistos na conciliacao
- restaura registros marcados como deletados quando eles reaparecem
- e o modo responsavel por fechar o sincronismo com foco em ausencias e delecoes

## Regras de Concorrencia

Existe um unico slot global de execucao.

Regras:

- `incremental` nao concorre com `incremental`
- `incremental` nao concorre com `conciliação`
- `conciliação` nao concorre com `conciliação`

Implementacao:

- trava local em memoria para a instancia atual
- `pg_advisory_lock` global no PostgreSQL para impedir concorrencia entre instancias
- recuperacao de execucoes orfas continua habilitada

## Modelo de Dados

### `olist_admin.sync_runs`

Cada run de entidade passa a registrar:

- `execution_type`: `incremental` ou `reconciliation`
- `sync_mode`: `incremental`, `snapshot`, `reconciliation` ou outro modo tecnico derivado

### `olist_raw.api_payloads`

Cada payload bruto passa a registrar:

- `last_seen_at`
- `last_seen_execution_id`
- `is_deleted`
- `deleted_at`
- `source_status`

Objetivo:

- permitir conciliacao por presenca ou ausencia
- permitir reativacao automatica quando um registro reaparece
- deixar o RAW semanticamente alinhado ao estado atual da origem

## Estrategia por Tipo

### Incremental

- `watermark`: usa a data salva por entidade
- `date_range`: usa a janela incremental atual
- sem suporte incremental documental: executa snapshot leve sem tratar ausencia como delete

### Conciliacao

- `watermark`: remove o filtro para executar leitura completa
- `date_range`: usa janela ampla de seguranca para cobrir historico necessario
- sem suporte incremental documental: executa leitura completa da entidade

## Algoritmo de Conciliacao

Para cada entidade:

1. iniciar o `sync_run` com `execution_type = reconciliation`
2. extrair e persistir todos os registros visiveis da entidade
3. marcar cada registro persistido com:
   - `last_seen_execution_id = execution_id`
   - `last_seen_at = now()`
   - `is_deleted = false`
   - `deleted_at = null`
4. ao terminar a entidade com sucesso, marcar como deletados os registros da mesma entidade que nao foram vistos nessa execucao
5. registrar no log quantos registros foram conciliados como ausentes/deletados

## Logs e Fechamento

O log exportado e o resumo visual da execucao devem mostrar:

- `Inicio`
- `Termino`
- `Tempo total`

O `Tempo total` deve ser exibido imediatamente abaixo das datas.

Formato:

- datas em `DD/MM/YYYY HH:MM:SS`
- duracao em formato humano, por exemplo `15h 02m 11s`

## UX da Tela de Extracao

A tela deve expor:

- botao `Incremental`
- botao `Conciliação`
- botao `Parar extração` apenas quando houver execucao em andamento

O estado da execucao deve deixar claro:

- tipo da execucao ativa
- status atual
- duracao
- previsao quando aplicavel

## Garantias Funcionais

- nenhuma dupla execucao concorrente
- `Incremental` atualiza novos e alterados
- `Conciliação` reconcilia ausencias e delecoes
- reaparecimento limpa `is_deleted`
- duracao da execucao aparece no resumo e no log exportado

