# Extração Olist -> Supabase

Aplicação Python modular responsável por extrair dados da API pública do ERP Olist, aplicar paginação automática, respeitar rate limit, persistir payloads com `upsert` no PostgreSQL/Supabase e expor a orquestração no menu `Extração` da Albertina.

## Estrutura

```text
backend/
|-- .env
|-- .env.example
|-- requirements.txt
`-- olist_extraction/
    |-- __init__.py
    |-- catalog.py
    |-- cli.py
    |-- config.py
    |-- extract.py
    |-- load.py
    |-- logs.py
    |-- service.py
    `-- transform.py
```

## O Que Faz

- Lê endpoints `GET` documentados da API pública Olist.
- Executa paginação automática com `limit` e `offset` quando suportado.
- Trata timeout, retry exponencial e headers `X-RateLimit-*`.
- Persiste payloads em `olist_raw.api_payloads` com `ON CONFLICT`.
- Mantém controle de execução em `olist_admin.sync_runs`, `olist_admin.sync_watermarks`, `olist_admin.sync_run_logs` e `olist_admin.execution_control`.
- Usa sincronização incremental quando a documentação confirma filtros como `dataAtualizacao`, `dataAlteracao` ou janelas por emissão.
- Expõe status, disparo e parada segura pelo menu `Extração` no frontend Albertina.
- Garante apenas uma execução concorrente por vez com trava global no PostgreSQL, lease persistida e heartbeat.

## Pré-Requisitos

- Python `3.11+`
- PostgreSQL / Supabase configurado em `ALBERTINA_DATABASE_URL`
- OAuth Olist já concluído na tela `Conexões`

## Instalação

No diretório `backend/`:

```bash
pip install -r requirements.txt
```

Copie o arquivo de exemplo, se necessário:

```bash
copy .env.example .env
```

Preencha ao menos:

- `ALBERTINA_DATABASE_URL`
- `OLIST_CLIENT_ID`
- `OLIST_CLIENT_SECRET`

## Execução Pela UI

1. Inicie o backend Albertina.
2. Inicie o frontend Albertina.
3. Conecte a aplicação com a Olist na tela `Conexões`.
4. Acesse o menu `Extração`.
5. Escolha `Incremental` ou `Conciliação`.
6. Durante a execução, acompanhe a entidade atual, o progresso por entidade, velocidade e ETA locais, além do card executivo de logs.
7. Use `Parar extração` para solicitar encerramento seguro.
8. No quadro `Histórico`, clique em uma execução concluída para baixar o log completo em arquivo `.txt`.

## Execução Via CLI

No diretório `backend/`:

```bash
python -m olist_extraction.cli --user-id <USER_ID> --actor-email <EMAIL>
```

## Logs

- Arquivo: `backend/logs/olist_extraction.log`
- Formato: `DD/MM/YYYY HH:MM:SS`
- Persistência de trilha: `olist_admin.sync_run_logs`
- A UI faz polling automático para mostrar progresso, entidade atual, ETA local, resumo executivo e últimos eventos.

## Documentação Relacionada

- fluxo visual de dados: `docs/olist_extraction_data_flow.html`
- guia de ETL: `docs/olist_etl_guide.md`
- matriz consolidada de mapeamento: `docs/olist_mapping_matrix_consolidated.md`

## Observações

- A extração exige PostgreSQL/Supabase; o fallback SQLite da Albertina não executa essa rotina.
- A cobertura foi organizada a partir dos endpoints públicos `GET` documentados.
- Quando a API não documenta watermark incremental para determinada entidade, a rotina faz sincronização full dessa entidade.
- A entidade `contacts` usa paginação mais curta para reduzir o tempo entre solicitar `Parar` e a interrupção efetiva.
- Execuções longas rodam em worker dedicado para evitar perda de processamento por reciclagem do servidor web.
