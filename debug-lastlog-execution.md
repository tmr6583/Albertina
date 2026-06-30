# Debug Session: lastlog-execution

- Status: OPEN
- Started At: 27/06/2026 12:00:00
- Scope: analisar o arquivo `lastlog.txt`, identificar erros reais da execucao final, corrigir o codigo com base em evidencia e avaliar se a proxima execucao sera incremental.

## Sintoma

- O usuario informou que a execucao chegou ao fim e salvou o log final em `c:\GitHubLocal\Albertina\lastlog.txt`.
- E necessario analisar os logs, corrigir todos os erros confirmados, emitir um relatorio resumido da execucao e informar se a proxima execucao sera incremental e mais rapida.

## Hipoteses

- H1: a execucao terminou com erros operacionais transitórios da Olist ainda nao tratados em algum fluxo.
- H2: houve erros de persistencia/consistencia no PostgreSQL ou no fechamento das cargas.
- H3: parte dos erros aparentes no log sao mensagens de status ou ruído de observabilidade, nao falhas reais.
- H4: existe entidade com estrategia incremental/watermark mal aplicada, gerando repeticao ou erro.
- H5: a proxima execucao so sera incremental e mais rapida se os watermarks tiverem sido persistidos corretamente.

## Plano

1. Ler `lastlog.txt` e extrair erros, warnings e status finais.
2. Cruzar os achados com o codigo da extracao.
3. Corrigir apenas os problemas confirmados pela evidencia.
4. Validar por testes/checagens estaticas.
5. Resumir a execucao e avaliar o comportamento esperado da proxima rodada.

## Evidencias

- Evidencia 1: `products` falhou em [lastlog.txt](file:///c:/GitHubLocal/Albertina/lastlog.txt#L261-L277) por `404` no sub-endpoint `/produtos/{idProduto}/fabricado`, apos `3030` persistencias bem-sucedidas da entidade.
- Evidencia 2: `accounts_receivable` falhou em [lastlog.txt](file:///c:/GitHubLocal/Albertina/lastlog.txt#L285-L325) por `JSON invalido` em `/contas-receber/{idContaReceber}/recebimentos`, apos `6216` persistencias.
- Evidencia 3: `accounts_payable` falhou em [lastlog.txt](file:///c:/GitHubLocal/Albertina/lastlog.txt#L333-L373) pelo mesmo padrao em `/contas-pagar/{idContaPagar}/recebimentos`, apos `3699` persistencias.
- Evidencia 4: `invoices` falhou em [lastlog.txt](file:///c:/GitHubLocal/Albertina/lastlog.txt#L381-L397) por `400` em `/notas/{idNota}/xml`, apos `10009` persistencias.
- Evidencia 5: os quatro erros ocorreram em etapas anexas/derivadas, nao no `root_step` das entidades, indicando que anexos opcionais estavam derrubando a entidade inteira.
- Evidencia 6: o catalogo original nao marcava esses sub-endpoints como tolerantes a falhas pontuais.

## Hipoteses Confirmadas / Rejeitadas

- H1: confirmada parcialmente. Nao houve 401/403/429/5xx nos erros finais, mas houve respostas HTTP/JSON anomalias em sub-endpoints especificos da Olist.
- H2: rejeitada. Nao apareceu evidencia de falha de persistencia no PostgreSQL/Supabase; as entidades persistiram milhares de registros antes do erro.
- H3: rejeitada. Os erros eram reais e reprodutiveis por padrao de endpoint, nao mero ruido de observabilidade.
- H4: confirmada. O problema era de modelagem do catalogo e tratamento de erro em etapas opcionais, nao do root incremental.
- H5: confirmada com ressalva. A proxima execucao sera incremental para as entidades incrementais, mas as que falharam nao consolidaram o watermark desta rodada com erro.

## Correcao Aplicada

1. Adicionada instrumentacao runtime em `extract.py` para registrar no Debug Server respostas HTTP problematicas e JSON invalido.
2. Estendido `EndpointStep` com configuracao de tolerancia:
   - `ignore_http_statuses`
   - `ignore_invalid_json`
3. Marcados como opcionais:
   - `products.fabricated`
   - `accounts_receivable.receipts`
   - `accounts_payable.receipts`
   - `invoices.xml`
4. O `WorkflowRunner` agora converte essas falhas opcionais em `WARNING` e segue a entidade, em vez de marcar a entidade inteira como erro.
5. Incluidos testes cobrindo `404` opcional e `JSON invalido` opcional.

## Validacao

- Testes: `python -m unittest backend.tests.test_olist_extraction -v` -> `11` testes `OK`.
- Compilacao: `python -m compileall backend\\olist_extraction backend\\tests\\test_olist_extraction.py` -> `OK`.

## Estado Atual

- Status: OPEN
- Correcao aplicada e validada por teste.
- Debug Server ativo em `http://127.0.0.1:7782` aguardando eventual reproducao pos-fix.

