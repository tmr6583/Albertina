# Debug Session: extraction-ui-stall

- Status: OPEN
- Started At: 30/06/2026 00:00:00
- Scope: investigar por que a tela de extracao nao muda de estado apos clicar em "Iniciar incremental", apesar da mensagem de sucesso do backend.

## Sintoma

- O usuario informou que, ao clicar em `Iniciar incremental`, a tela nao reflete execucao ativa.
- Apenas aparece a mensagem `A execução incremental foi iniciada em background.`.

## Hipoteses

- H1: o `POST /api/extraction/run` inicia a execucao, mas o `GET /api/extraction/overview` devolve payload sem `running=true`.
- H2: a UI inicia corretamente, mas o estado local de `overview` nao e atualizado por incompatibilidade de campos novos no payload.
- H3: o backend inicia a thread, mas a execucao falha antes de criar/atualizar `sync_runs`, deixando a tela sem evidencias para renderizar.
- H4: houve regressao na regra de polling/refresh da tela, e a execucao existe no backend, mas a UI nao a busca corretamente apos o clique.
- H5: o novo `executionType` entrou no fluxo de start, mas o overview ou a serializacao da execucao ativa nao ficou compativel com o frontend atual.

## Plano

1. Ler o fluxo frontend de start e refresh da tela.
2. Ler o fluxo backend de start e overview.
3. Instrumentar pontos minimos no frontend e backend para confirmar onde o estado some.
4. Reproduzir o clique e coletar evidencias.
5. Corrigir apenas com base nas evidencias coletadas.

## Evidencias

- Evidencia coletada em `Albertina.backend.err.log`:
  - a thread `_run_background` inicia e falha no primeiro `create_sync_run`
  - erro confirmado: `psycopg2.errors.CheckViolation: sync_runs_mode_check`
  - linha rejeitada: `sync_mode = 'snapshot'` com `execution_type = 'incremental'`
- Hipotese confirmada:
  - H3 confirmada: o backend inicia a thread, mas a execucao falha antes de consolidar `sync_runs` por incompatibilidade do novo `sync_mode` com a constraint existente do banco
- Hipoteses rejeitadas por evidencia:
  - H2 rejeitada
  - H4 rejeitada
  - H5 rejeitada como causa primaria da falha visivel

## Correcao Aplicada

- Atualizada a rotina de schema em `backend/olist_extraction/load.py` para recriar a constraint `sync_runs_mode_check` aceitando:
  - `full`
  - `incremental`
  - `snapshot`
  - `reconciliation`

## Proxima Verificacao

- Reiniciar o backend para aplicar a migracao automatica de schema.
- Reproduzir o clique em `Iniciar incremental`.
- Confirmar se o `overview` passa a refletir `running=true` e a execucao ativa.
