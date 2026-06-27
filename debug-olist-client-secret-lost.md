# Debug Session: olist-client-secret-lost
- **Status**: [OPEN]
- **Issue**: A aba Conexoes passou a exibir o `client_secret` da Olist vazio, apesar de ele ja ter sido salvo anteriormente.
- **Debug Server**: not-started
- **Log File**: .dbg/trae-debug-log-olist-client-secret-lost.ndjson

## Reproduction Steps
1. Abrir a aplicacao autenticada.
2. Navegar ate `Conexoes`.
3. Observar que o campo `Client Secret` aparece vazio.

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | O `client_secret` foi zerado no banco durante a limpeza/reset operacional. | High | Low | Pending |
| B | O valor continua salvo no banco, mas a API devolve vazio. | Medium | Low | Pending |
| C | A API devolve corretamente, mas a UI limpa o estado local e renderiza vazio. | Low | Medium | Pending |
| D | Alguma chamada de atualizacao sobrescreveu o valor com string vazia. | Medium | Medium | Pending |

## Log Evidence
- [App.jsx](file:///c:/GitHubLocal/Albertina/frontend/src/App.jsx#L571-L586) inicializa o campo com `olist?.clientSecret` vindo do overview.
- [App.jsx](file:///c:/GitHubLocal/Albertina/frontend/src/App.jsx#L1950-L1967) remonta a tela de `Conexoes` com base em `connectionsOverview?.olist?.clientSecret`, portanto a UI reflete diretamente a resposta da API.
- [app.py](file:///c:/GitHubLocal/Albertina/backend/app.py#L569-L606) devolve `clientSecret` usando `row_value(row, "client_secret")`, sem mascaramento nem limpeza adicional.
- [app.py](file:///c:/GitHubLocal/Albertina/backend/app.py#L1571-L1585) monta `/api/connections/overview` diretamente a partir de `get_olist_settings(db)`.
- Na limpeza operacional anterior, o reset do registro singleton `public.olist_settings` foi executado com `client_secret = ''`, retornando o estado para `Pendente de Client Secret / Nao conectado`.

## Verification Conclusion
- Hipotese A: **Confirmada**. O `client_secret` foi apagado no reset operacional anterior ao voltar `public.olist_settings` para o estado default.
- Hipotese B: **Rejeitada**. A API nao mascara o valor; ela apenas devolve o que esta salvo no banco.
- Hipotese C: **Rejeitada**. A UI so renderiza o valor do overview e nao limpa esse campo por conta propria.
- Hipotese D: **Inconclusiva/nao necessaria**. Nao foi preciso evidenciar um `PATCH` recente, porque a causa ja aparece no reset operacional anterior.
