# MCP-Supabase

MCP local do projeto Albertina para acesso ao PostgreSQL do Supabase com foco em:

- baixo consumo de tokens
- respostas compactas em JSON
- acesso completo ao banco via SQL
- configuracao simples via `python + .env`

## Ferramentas

- `ping`: testa a conexao.
- `ls`: lista tabelas, views e materialized views.
- `cols`: lista colunas.
- `sql`: executa SQL completo.

## Instalar

```powershell
pip install -r c:\GitHubLocal\Albertina\mcp\MCP-Supabase\requirements.txt
```

## Executar

```powershell
python c:\GitHubLocal\Albertina\mcp\MCP-Supabase\server.py
```

## Trae

- Configuracao pronta: `mcp/MCP-Supabase/trae.mcp.json`
- Script de registro: `mcp/MCP-Supabase/install-trae.ps1`
- Arquivo real do cliente: `c:\Users\tmrossi\AppData\Roaming\Trae\User\mcp.json`

## Portabilidade

- Arquivo portavel: `mcp/MCP-Supabase/portable.mcp.json`
- Basta ajustar `<PROJECT_ROOT>` e as variaveis do Supabase.
