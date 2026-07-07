[OPEN]

# Debug Session: reconciliation-sync

## Objetivo
- Garantir que a conciliacao finalize com sincronismo real com o ERP.
- Corrigir falhas em `accounts_receivable`, `accounts_payable` e `invoices`.
- Reduzir o tempo da proxima conciliacao e das proximas incrementais sem deixar dados faltando.

## Hipoteses Falsificaveis
1. A API da Olist retorna `204 No Content` em `recebimentos`, e o cliente trata isso como JSON invalido; na conciliacao isso aborta desnecessariamente entidades que poderiam ser consideradas cobertas com lista vazia.
2. A lease da execucao expira durante `invoices` porque o heartbeat nao renova em alguns trechos longos ou a janela configurada esta curta para o pior caso operacional.
3. A conciliacao fica lenta porque alguns subpassos estao sendo revisitados integralmente mesmo quando o endpoint raiz nao mudou, sem uma estrategia segura de cobertura por escopo.
4. A proxima incremental nao fica rapida porque a conciliacao nao grava `watermarks`, deixando a primeira incremental apos reconciliacao praticamente fria.
5. O principal custo residual de `invoices` esta no fan-out de `item_detail`, e um mecanismo de checkpoint/skip seguro por mudanca real pode reduzir tempo sem perder integridade.

## Evidencias Ja Observadas
- `accounts_receivable.receipts` e `accounts_payable.receipts` falharam com `status=204`, `preview=<vazio>`.
- `invoices` terminou `cancelled` com `recoveryNote` informando recuperacao automatica por lease expirada.
- `olist_admin.sync_watermarks` esta vazio apos a conciliacao.

## Proximo Passo
- Instrumentar pontos de renovacao de lease, tratamento de respostas vazias e gravacao de watermarks apos conciliacao.

## Evidencia Confirmada
- Hipotese 1 confirmada: `204 No Content` em `recebimentos` era tratado como JSON invalido e abortava a conciliacao sem necessidade.
- Hipotese 2 parcialmente confirmada: a renovacao de lease podia falhar silenciosamente porque `renew_execution_slot()` retornava `False` sem escalacao; alem disso a lease default era curta para execucoes longas.
- Hipotese 4 confirmada: a conciliacao nao aquecia `watermarks`, deixando a proxima incremental fria.
- Hipotese 5 permanece valida como gargalo estrutural de `invoices`, mas a correção atual prioriza integridade, conclusao da execucao e aquecimento das proximas incrementais.

## Correcoes Aplicadas
- `204` passa a ser tratado como escopo vazio, sem retries desnecessarios e sem falha da entidade.
- Conciliacao bem-sucedida agora salva `watermarks` do root e de subpassos com `cooldown`.
- Lease default elevada para `900s`.
- Recuperacao automatica de orfao exige lease expirada e heartbeat stale com janela de graca.
- Falha em renovar lease agora nao passa silenciosamente; o workflow aborta com erro explicito.

## Validacao
- Suíte focada: `python -m unittest backend.tests.test_olist_extraction -v`
- Resultado: `38 tests OK`
