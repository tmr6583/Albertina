-- Albertina: configuracao administrativa da conexao Olist

BEGIN;

CREATE TABLE IF NOT EXISTS public.olist_settings (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  client_secret TEXT NOT NULL,
  redirect_uri TEXT NOT NULL,
  api_base_url TEXT NOT NULL,
  auth_mode TEXT NOT NULL,
  status TEXT NOT NULL,
  token_status TEXT NOT NULL,
  message TEXT NOT NULL,
  access_token TEXT NULL,
  refresh_token TEXT NULL,
  last_connect_attempt_at TIMESTAMPTZ NULL,
  last_token_refresh_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE public.olist_settings IS 'Configuracao administrativa da conexao OAuth com a Olist.';
COMMENT ON COLUMN public.olist_settings.id IS 'Identificador singleton da configuracao.';
COMMENT ON COLUMN public.olist_settings.client_id IS 'Client ID da aplicacao cadastrada na Olist.';
COMMENT ON COLUMN public.olist_settings.client_secret IS 'Client Secret atualmente salvo para a aplicacao Olist.';
COMMENT ON COLUMN public.olist_settings.redirect_uri IS 'Redirect URL que deve ser configurada no ERP Olist.';
COMMENT ON COLUMN public.olist_settings.api_base_url IS 'Base da API publica da Olist.';
COMMENT ON COLUMN public.olist_settings.auth_mode IS 'Fluxo OAuth utilizado pela integracao.';
COMMENT ON COLUMN public.olist_settings.status IS 'Status atual da conexao exibido na interface.';
COMMENT ON COLUMN public.olist_settings.token_status IS 'Resumo do estado atual dos tokens OAuth.';
COMMENT ON COLUMN public.olist_settings.message IS 'Mensagem operacional resumida para orientar o usuario.';
COMMENT ON COLUMN public.olist_settings.access_token IS 'Access token persistido, quando disponivel.';
COMMENT ON COLUMN public.olist_settings.refresh_token IS 'Refresh token persistido, quando disponivel.';
COMMENT ON COLUMN public.olist_settings.last_connect_attempt_at IS 'Data e hora UTC da ultima tentativa administrativa de conexao.';
COMMENT ON COLUMN public.olist_settings.last_token_refresh_at IS 'Data e hora UTC da ultima renovacao administrativa registrada.';
COMMENT ON COLUMN public.olist_settings.created_at IS 'Data e hora UTC de criacao do registro.';
COMMENT ON COLUMN public.olist_settings.updated_at IS 'Data e hora UTC da ultima alteracao do registro.';

INSERT INTO public.olist_settings (
  id,
  client_id,
  client_secret,
  redirect_uri,
  api_base_url,
  auth_mode,
  status,
  token_status,
  message,
  created_at,
  updated_at
)
VALUES (
  'default',
  '',
  '',
  'http://localhost:3500/olist/callback',
  'https://api.tiny.com.br/public-api/v3/',
  'OAuth 2 Authorization Code',
  'Pendente de Client Secret',
  'Nao conectado',
  'Informe o Client Secret para preparar a conexao OAuth com a Olist.',
  NOW(),
  NOW()
)
ON CONFLICT (id) DO NOTHING;

COMMIT;
