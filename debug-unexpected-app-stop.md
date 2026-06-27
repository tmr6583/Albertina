# Debug Session: unexpected-app-stop
- **Status**: [OPEN]
- **Issue**: A aplicacao e a extracao pararam mesmo tendo sido deixadas em execucao, sem interacao manual intencional do usuario.
- **Debug Server**: not-started
- **Log File**: .dbg/trae-debug-log-unexpected-app-stop.ndjson

## Reproduction Steps
1. Subir a aplicacao com `Albertina.bat iniciar`.
2. Iniciar a extracao pela interface.
3. Deixar a aplicacao executando sem interacao manual.
4. Observar se ocorre parada inesperada do backend/frontend ou interrupcao da extracao.

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | Algum processo automatico externo executou `Albertina.bat encerrar`. | High | Low | Pending |
| B | O backend caiu sozinho e o shutdown foi apenas efeito secundario. | Medium | Low | Pending |
| C | Algum monitor ou automacao do ambiente reiniciou a aplicacao. | Medium | Medium | Pending |
| D | A extracao entrou em timeout/bloqueio e algum mecanismo de protecao matou o processo. | Medium | Medium | Pending |
| E | Alguma acao de frontend ou script auxiliar disparou a parada. | Low | Medium | Pending |

## Log Evidence
- `Albertina.log` mostra `Encerramento via linha de comando` em `27/06/2026 01:16:54`, `01:17:18` e `01:18:29`.
- `Albertina.log` mostra `Inicializacao via linha de comando` em `27/06/2026 01:17:01` e `01:17:25`.
- `backend/logs/olist_extraction.log` manteve progresso normal em `contacts.detail` ate `27/06/2026 01:16:43`, sem erro fatal antes da parada.
- `Albertina.backend.err.log` nao registrou stack trace, exception nem falha do Uvicorn antes do desligamento.
- A nova instrumentacao no `Albertina.bat` registrou que o `iniciar` atual veio de `cmd.exe /c ""C:\GitHubLocal\Albertina\Albertina.bat" iniciar"` encadeado a `pwsh.exe` do terminal integrado do Trae.

## Verification Conclusion
- Hipotese A: **Confirmada**. Houve invocacoes explicitas de linha de comando ao `Albertina.bat`, e foi isso que derrubou a aplicacao.
- Hipotese B: **Rejeitada**. Nao ha evidencia de crash espontaneo do backend antes do `encerrar`.
- Hipotese C: **Inconclusiva**. A causa exata do chamador anterior ainda nao foi capturada porque os eventos antigos ocorreram antes da instrumentacao.
- Hipotese D: **Rejeitada**. A extracao seguia avancando normalmente imediatamente antes do desligamento.
- Hipotese E: **Inconclusiva**. Nao apareceu evidencia de chamada HTTP de parada; o gatilho observado foi por CLI/batch.
