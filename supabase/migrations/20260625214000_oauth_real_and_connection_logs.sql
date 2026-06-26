-- Albertina: suporte OAuth real da Olist e logs de conexao

BEGIN;

ALTER TABLE public.olist_settings
  ADD COLUMN IF NOT EXISTS access_token_expires_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS refresh_token_expires_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS token_type TEXT NULL,
  ADD COLUMN IF NOT EXISTS scope TEXT NULL,
  ADD COLUMN IF NOT EXISTS oauth_state TEXT NULL,
  ADD COLUMN IF NOT EXISTS oauth_state_expires_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS last_callback_at TIMESTAMPTZ NULL;

CREATE TABLE IF NOT EXISTS public.connection_logs (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  event TEXT NOT NULL,
  status TEXT NOT NULL,
  description TEXT NOT NULL,
  tone TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE public.connection_logs IS 'Logs operacionais da conexao OAuth com provedores externos.';
COMMENT ON COLUMN public.connection_logs.id IS 'Identificador textual do log.';
COMMENT ON COLUMN public.connection_logs.provider IS 'Provedor associado ao evento, por exemplo Olist.';
COMMENT ON COLUMN public.connection_logs.event IS 'Nome curto do evento registrado.';
COMMENT ON COLUMN public.connection_logs.status IS 'Status resumido do evento.';
COMMENT ON COLUMN public.connection_logs.description IS 'Descricao detalhada do evento.';
COMMENT ON COLUMN public.connection_logs.tone IS 'Tom visual do log usado pela interface.';
COMMENT ON COLUMN public.connection_logs.created_at IS 'Data e hora UTC de criacao do log.';

CREATE INDEX IF NOT EXISTS idx_connection_logs_created_at ON public.connection_logs (created_at DESC);

UPDATE public.olist_settings
SET token_type = COALESCE(token_type, 'Bearer'),
    scope = COALESCE(scope, 'openid')
WHERE id = 'default';

COMMIT;
