# Debug Session: incremental-runtime-health

- Status: OPEN
- Started At: 01/07/2026 00:00:00
- Scope: verificar se a execução incremental em andamento está saudável e, se houver falhas, coletar evidências e corrigir para próximas execuções.

## Hipóteses

- H1: a execução parece lenta, mas está viva e avançando (fase pesada como `invoices.*`) com heartbeat recente.
- H2: `orders` falha por `400` em `/pedidos` devido a filtro incremental inválido (`dataAtualizacao`), mesmo existindo suporte documental ao parâmetro.
- H3: `products` falha por queda/transiente de conexão com o Postgres durante `upsert`, exigindo retry transacional no persist.
- H4: a UI não reflete progresso por atraso de polling, mas o banco registra progresso/heartbeat normalmente.

## Evidências

- Execução ativa (via banco): `ACTIVE_EXECUTION_ID: 21eb5742-7b32-43e9-b14c-6bfb898eb350`
- `invoices` em andamento com heartbeat recente e contagem processada/total preenchida.
- `orders` com stack trace de `400 Client Error` em `GET /pedidos?dataAtualizacao=...`
- `products` com stack trace de `psycopg2.OperationalError: server closed the connection unexpectedly`

## Próximas Ações

- Tornar `orders.list` resiliente: fallback automático para filtro por `dataInicial/dataFinal` quando `dataAtualizacao` retornar `400`.
- Tornar persistência resiliente: retry transacional quando ocorrer `OperationalError` durante upsert.

