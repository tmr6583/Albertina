[OPEN]

# Registro de debug: reconciliation-sync

## Objetivo
- Garantir que a conciliação finalize com sincronismo real com o ERP.
- Corrigir falhas em `accounts_receivable`, `accounts_payable` e `invoices`.
- Reduzir o tempo da próxima conciliação e das próximas incrementais sem deixar dados faltando.

## Hipóteses Falsificaveis
1. A API da Olist retorna `204 No Content` em `recebimentos`, e o cliente trata isso como JSON invalido; na conciliação isso aborta desnecessariamente entidades que poderiam ser consideradas cobertas com lista vazia.
2. A lease da execução expira durante `invoices` porque o heartbeat não renova em alguns trechos longos ou a janela configurada esta curta para o pior caso operacional.
3. A conciliação fica lenta porque alguns subpassos estao sendo revisitados integralmente mesmo quando o endpoint raiz não mudou, sem uma estrategia segura de cobertura por escopo.
4. A próxima incremental não fica rapida porque a conciliação não grava `watermarks`, deixando a primeira incremental apos reconciliação praticamente fria.
5. O principal custo residual de `invoices` esta no fan-out de `item_detail`, e um mecanismo de checkpoint/skip seguro por mudanca real pode reduzir tempo sem perder integridade.

## Evidências Ja Observadas
- `accounts_receivable.receipts` e `accounts_payable.receipts` falharam com `status=204`, `preview=<vazio>`.
- `invoices` terminou `cancelled` com `recoveryNote` informando recuperação automatica por lease expirada.
- `olist_admin.sync_watermarks` esta vazio apos a conciliação.

## Proximo Passo
- Instrumentar pontos de renovação de lease, tratamento de respostas vazias e gravação de watermarks apos conciliação.

## Evidencia Confirmada
- Hipotese 1 confirmada: `204 No Content` em `recebimentos` era tratado como JSON invalido e abortava a conciliação sem necessidade.
- Hipotese 2 parcialmente confirmada: a renovação de lease podia falhar silenciosamente porque `renew_execution_slot()` retornava `False` sem escalação; alem disso a lease default era curta para execucoes longas.
- Hipotese 4 confirmada: a conciliação não aquecia `watermarks`, deixando a próxima incremental fria.
- Hipotese 5 permanece valida como gargalo estrutural de `invoices`, mas a correção atual prioriza integridade, conclusao da execução e aquecimento das próximas incrementais.

## Correções Aplicadas
- `204` passa a ser tratado como escopo vazio, sem retries desnecessarios e sem falha da entidade.
- Conciliação bem-sucedida agora salva `watermarks` do root e de subpassos com `cooldown`.
- Lease default elevada para `900s`.
- Recuperação automatica de orfao exige lease expirada e heartbeat stale com janela de graca.
- Falha em renovar lease agora não passa silenciosamente; o workflow aborta com erro explicito.

## Validação
- Suíte focada: `python -m unittest backend.tests.test_olist_extraction -v`
- Resultado: `38 tests OK`
