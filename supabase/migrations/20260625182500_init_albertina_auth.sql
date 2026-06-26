-- Albertina: migracao inicial de autenticacao e administracao de usuarios
-- Banco alvo: PostgreSQL / Supabase
-- Observacao: esta migracao usa os mesmos nomes de tabela atualmente utilizados pelo backend

BEGIN;

CREATE TABLE IF NOT EXISTS public.users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL,
  status TEXT NOT NULL,
  initials TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  last_access_at TIMESTAMPTZ NULL,
  CONSTRAINT users_status_check CHECK (status IN ('Ativo', 'Inativo'))
);

COMMENT ON TABLE public.users IS 'Usuarios administrativos da aplicacao Albertina.';
COMMENT ON COLUMN public.users.id IS 'Identificador textual do usuario, gerado pela aplicacao.';
COMMENT ON COLUMN public.users.email IS 'Email de login do usuario, normalizado em lowercase.';
COMMENT ON COLUMN public.users.password_hash IS 'Hash derivado da senha do usuario.';
COMMENT ON COLUMN public.users.role IS 'Papel administrativo atual do usuario.';
COMMENT ON COLUMN public.users.status IS 'Status da conta. Valores esperados: Ativo ou Inativo.';
COMMENT ON COLUMN public.users.initials IS 'Iniciais derivadas do email, usadas na interface.';
COMMENT ON COLUMN public.users.created_at IS 'Data e hora UTC de criacao da conta.';
COMMENT ON COLUMN public.users.updated_at IS 'Data e hora UTC da ultima alteracao cadastral.';
COMMENT ON COLUMN public.users.last_access_at IS 'Data e hora UTC do ultimo login bem-sucedido.';

CREATE INDEX IF NOT EXISTS idx_users_created_at_desc ON public.users (created_at DESC);

CREATE TABLE IF NOT EXISTS public.sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ NULL,
  CONSTRAINT sessions_user_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);

COMMENT ON TABLE public.sessions IS 'Sessoes autenticadas da aplicacao Albertina.';
COMMENT ON COLUMN public.sessions.id IS 'Identificador textual da sessao.';
COMMENT ON COLUMN public.sessions.user_id IS 'Usuario dono da sessao.';
COMMENT ON COLUMN public.sessions.token_hash IS 'Hash SHA-256 do token Bearer emitido pela aplicacao.';
COMMENT ON COLUMN public.sessions.created_at IS 'Data e hora UTC de criacao da sessao.';
COMMENT ON COLUMN public.sessions.expires_at IS 'Data e hora UTC de expiracao da sessao.';
COMMENT ON COLUMN public.sessions.revoked_at IS 'Data e hora UTC da revogacao da sessao, quando aplicavel.';

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON public.sessions (expires_at);

CREATE TABLE IF NOT EXISTS public.audits (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  tone TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE public.audits IS 'Eventos de auditoria administrativa e operacional da aplicacao.';
COMMENT ON COLUMN public.audits.id IS 'Identificador textual do evento de auditoria.';
COMMENT ON COLUMN public.audits.title IS 'Titulo curto do evento.';
COMMENT ON COLUMN public.audits.description IS 'Descricao detalhada da acao auditada.';
COMMENT ON COLUMN public.audits.tone IS 'Tom visual usado pela interface para classificar o evento.';
COMMENT ON COLUMN public.audits.created_at IS 'Data e hora UTC em que o evento foi registrado.';

CREATE INDEX IF NOT EXISTS idx_audits_created_at_desc ON public.audits (created_at DESC);

COMMIT;
