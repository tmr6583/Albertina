# Registro de debug: lastlog-execution

- Status: REGISTRO HISTÓRICO
- Started At: 27/06/2026 12:00:00
- Scope: analisar o arquivo `last_log.txt`, identificar erros reais da execução final, corrigir o código com base em evidência e avaliar o comportamento esperado das próximas execuções.

## Sintoma

- O usuário informou que a execução chegou ao fim e salvou o log final em `c:\GitHubLocal\Albertina\last_log.txt`.
- Era necessário analisar os logs, corrigir os erros confirmados, emitir um relatório resumido da execução e avaliar o comportamento esperado das próximas rodadas.

## Hipóteses

- H1: a execução terminou com erros operacionais transitórios da Olist ainda não tratados em algum fluxo.
- H2: houve erros de persistência/consistencia no PostgreSQL ou no fechamento das cargas.
- H3: parte dos erros aparentes no log sao mensagens de status ou ruído de observabilidade, não falhas reais.
- H4: existe entidade com estrategia incremental/watermark mal aplicada, gerando repeticao ou erro.
- H5: a próxima execução so será incremental e mais rapida se os watermarks tiverem sido persistidos corretamente.

## Plano

1. Ler `last_log.txt` e extrair erros, warnings e status finais.
2. Cruzar os achados com o código da extração.
3. Corrigir apenas os problemas confirmados pela evidência.
4. Validar por testes e checagens estáticas.
5. Resumir a execução e avaliar o comportamento esperado da próxima rodada.

## Evidências

- Evidencia 1: `products` falhou em [last_log.txt](file:///c:/GitHubLocal/Albertina/last_log.txt#L261-L277) por `404` no sub-endpoint `/produtos/{idProduto}/fabricado`, após `3030` persistências bem-sucedidas da entidade.
- Evidencia 2: `accounts_receivable` falhou em [last_log.txt](file:///c:/GitHubLocal/Albertina/last_log.txt#L285-L325) por `JSON inválido` em `/contas-receber/{idContaReceber}/recebimentos`, após `6216` persistências.
- Evidencia 3: `accounts_payable` falhou em [last_log.txt](file:///c:/GitHubLocal/Albertina/last_log.txt#L333-L373) pelo mesmo padrão em `/contas-pagar/{idContaPagar}/recebimentos`, após `3699` persistências.
- Evidencia 4: `invoices` falhou em [last_log.txt](file:///c:/GitHubLocal/Albertina/last_log.txt#L381-L397) por `400` em `/notas/{idNota}/xml`, após `10009` persistências.
- Evidencia 5: os quatro erros ocorreram em etapas anexas/derivadas, não no `root_step` das entidades, indicando que anexos opcionais estavam derrubando a entidade inteira.
- Evidencia 6: o catálogo original não marcava esses sub-endpoints como tolerantes a falhas pontuais.

## Hipóteses Confirmadas / Rejeitadas

- H1: confirmada parcialmente. Não houve 401/403/429/5xx nos erros finais, mas houve respostas HTTP/JSON anomalias em sub-endpoints especificos da Olist.
- H2: rejeitada. Não apareceu evidencia de falha de persistência no PostgreSQL/Supabase; as entidades persistiram milhares de registros antes do erro.
- H3: rejeitada. Os erros eram reais e reprodutiveis por padrao de endpoint, não mero ruido de observabilidade.
- H4: confirmada. O problema era de modelagem do catálogo e tratamento de erro em etapas opcionais, não do root incremental.
- H5: confirmada com ressalva. A próxima execução será incremental para as entidades incrementais, mas as que falharam não consolidaram o watermark desta rodada com erro.

## Correção Aplicada

1. Adicionada instrumentação runtime em `extract.py` para registrar no Debug Server respostas HTTP problematicas e JSON invalido.
2. Estendido `EndpointStep` com configuração de tolerancia:
   - `ignore_http_statuses`
   - `ignore_invalid_json`
3. Marcados como opcionais:
   - `products.fabricated`
   - `accounts_receivable.receipts`
   - `accounts_payable.receipts`
   - `invoices.xml`
4. O `WorkflowRunner` agora converte essas falhas opcionais em `WARNING` e segue a entidade, em vez de marcar a entidade inteira como erro.
5. Incluidos testes cobrindo `404` opcional e `JSON invalido` opcional.

## Validação

- Testes: `python -m unittest backend.tests.test_olist_extraction -v` -> `11` testes `OK`.
- Compilação: `python -m compileall backend\\olist_extraction backend\\tests\\test_olist_extraction.py` -> `OK`.

## Estado Atual

- Status: REGISTRO HISTÓRICO
- Correção aplicada e validada por teste.
- Registro preservado como histórico da sessão de correção.

