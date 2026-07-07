# Registro de debug: unexpected-app-stop
- **Status**: [OPEN]
- **Issue**: A aplicação e a extração pararam mesmo tendo sido deixadas em execução, sem interação manual intencional do usuario.
- **Debug Server**: not-started
- **Log File**: .dbg/trae-debug-log-unexpected-app-stop.ndjson

## Passos de reprodução
1. Subir a aplicação com `Albertina.bat iniciar`.
2. Iniciar a extração pela interface.
3. Deixar a aplicação executando sem interação manual.
4. Observar se ocorre parada inesperada do backend/frontend ou interrupcao da extração.

## Hipóteses e verificação
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | Algum processo automatico externo executou `Albertina.bat encerrar`. | High | Low | Pending |
| B | O backend caiu sozinho e o shutdown foi apenas efeito secundario. | Medium | Low | Pending |
| C | Algum monitor ou automação do ambiente reiniciou a aplicação. | Medium | Medium | Pending |
| D | A extração entrou em timeout/bloqueio e algum mecanismo de protecao matou o processo. | Medium | Medium | Pending |
| E | Alguma ação de frontend ou script auxiliar disparou a parada. | Low | Medium | Pending |

## Evidências de log
- `Albertina.log` mostra `Encerramento via linha de comando` em `27/06/2026 01:16:54`, `01:17:18` e `01:18:29`.
- `Albertina.log` mostra `Inicialização via linha de comando` em `27/06/2026 01:17:01` e `01:17:25`.
- `backend/logs/olist_extraction.log` manteve progresso normal em `contacts.detail` ate `27/06/2026 01:16:43`, sem erro fatal antes da parada.
- `Albertina.backend.err.log` não registrou stack trace, exception nem falha do Uvicorn antes do desligamento.
- A nova instrumentação no `Albertina.bat` registrou que o `iniciar` atual veio de `cmd.exe /c ""C:\GitHubLocal\Albertina\Albertina.bat" iniciar"` encadeado a `pwsh.exe` do terminal integrado do Trae.

## Conclusão da verificação
- Hipotese A: **Confirmada**. Houve invocacoes explicitas de linha de comando ao `Albertina.bat`, e foi isso que derrubou a aplicação.
- Hipotese B: **Rejeitada**. Não ha evidencia de crash espontaneo do backend antes do `encerrar`.
- Hipotese C: **Inconclusiva**. A causa exata do chamador anterior ainda não foi capturada porque os eventos antigos ocorreram antes da instrumentação.
- Hipotese D: **Rejeitada**. A extração seguia avancando normalmente imediatamente antes do desligamento.
- Hipotese E: **Inconclusiva**. Não apareceu evidencia de chamada HTTP de parada; o gatilho observado foi por CLI/batch.
