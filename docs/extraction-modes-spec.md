# Especificação técnica dos modos de extração Olist

## Objetivo

Esta especificação descreve os dois modos operacionais da extração Olist no projeto `Albertina`:

1. `incremental`
2. `reconciliation`

Os dois modos compartilham o mesmo slot global de execução. Em qualquer cenário, só pode existir uma execução ativa por vez.

## Definição operacional

### Incremental

Modo de operação cotidiana, priorizando atualização rápida do ambiente com menor volume de leitura.

Comportamento esperado:

- usa `watermark` quando a API documenta filtros como `dataAtualizacao` ou `dataAlteracao`
- usa janela por faixa de datas quando a entidade trabalha com emissão, vencimento ou período operacional
- usa `cooldown` local quando a API não oferece filtro incremental documental
- faz `upsert` na RAW e mantém o payload mais recente visível
- não marca ausências como exclusão definitiva

### Conciliação

Modo de integridade, acionado para fechamento de sincronismo com a origem.

Comportamento esperado:

- remove filtros incrementais sempre que a estratégia permitir leitura completa ou leitura ampla
- marca cada payload visto na execução atual com `last_seen_at` e `last_seen_execution_id`
- identifica ausências ao final da entidade e marca registros como deletados quando apropriado
- reativa registros quando eles reaparecem em uma execução posterior
- aquece `watermarks` e `cooldowns` ao final de uma conciliação bem-sucedida

## Regras de concorrência

Existe um único slot global de execução.

Garantias:

- `incremental` não concorre com `incremental`
- `incremental` não concorre com `reconciliation`
- `reconciliation` não concorre com `reconciliation`

Implementação atual:

- trava local em memória para a instância ativa
- `pg_advisory_lock` global no PostgreSQL
- controle persistente em `olist_admin.execution_control`
- lease com `heartbeat` para detectar execução órfã e recuperar liveness com segurança

## Modelo de dados relacionado

### `olist_admin.sync_runs`

Cada execução por entidade registra, no mínimo:

- `execution_type`: `incremental` ou `reconciliation`
- `sync_mode`: `incremental`, `snapshot`, `reconciliation` ou outra estratégia técnica derivada
- `status`, tempo de início, término e duração total

### `olist_admin.execution_control`

Tabela de coordenação global da execução:

- garante exclusão mútua entre workers
- registra `lease`, `heartbeat` e `worker_id`
- evita concorrência entre UI, API e processo externo

### `olist_raw.api_payloads`

Cada payload bruto pode registrar:

- `last_seen_at`
- `last_seen_execution_id`
- `is_deleted`
- `deleted_at`
- `source_status`

Objetivo:

- permitir conciliação por presença ou ausência
- reativar automaticamente registros reaparecidos
- manter o RAW semanticamente alinhado ao estado mais recente da origem

## Estratégia por tipo

### Incremental

- `watermark`: usa a data persistida por entidade e por step aplicável
- `date_range`: usa a janela incremental configurada
- `cooldown`: reaproveita sincronização recente para evitar revarredura

### Conciliação

- remove filtros incrementais para leitura completa, quando suportado
- usa janelas amplas quando a API exige faixa temporal
- executa leitura completa da entidade quando não há suporte incremental documental

## Algoritmo resumido da conciliação

Para cada entidade:

1. inicia `sync_run` com `execution_type = reconciliation`
2. extrai e persiste todos os registros visíveis da entidade
3. marca registros vistos com `last_seen_execution_id`, `last_seen_at` e `is_deleted = false`
4. ao concluir a entidade com sucesso, marca como ausentes os registros não vistos na execução
5. registra no log os totais conciliados, excluídos e reativados

## Logs e fechamento

O log exportado e o resumo visual devem mostrar:

- `Início`
- `Término`
- `Tempo total`

Formato:

- datas em `DD/MM/YYYY HH:MM:SS`
- duração em formato humano, por exemplo `15h 02m 11s`

## UX da tela de extração

A interface deve expor:

- botão `Incremental`
- botão `Conciliação`
- botão `Parar extração` apenas durante execução ativa

O estado da execução deve deixar claro:

- tipo da execução ativa
- status atual
- duração
- previsão, quando aplicável

## Garantias funcionais

- nenhuma execução concorrente entre modos diferentes
- `Incremental` atualiza novos e alterados com menor custo operacional
- `Conciliação` reconcilia ausências e deleções quando a estratégia da entidade permite
- reaparecimento limpa `is_deleted`
- duração da execução aparece no resumo e no log exportado
