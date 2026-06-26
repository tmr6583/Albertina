import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import { ApiError, apiRequest, clearStoredToken, getStoredToken, setStoredToken } from './api'


const ROUTES = {
  login: '/',
  users: '/usuarios',
  connections: '/conexoes',
  audit: '/auditoria',
}

const LEGACY_ROUTES = {
  olist: '/olist',
  olistCallback: '/olist/callback',
}

const NAV_ITEMS = [
  {
    key: 'users',
    label: 'Administração de Usuários',
    path: ROUTES.users,
    className: 'nav-users',
  },
  {
    key: 'connections',
    label: 'Conexões',
    path: ROUTES.connections,
    className: 'nav-olist',
  },
  {
    key: 'audit',
    label: 'Auditoria',
    path: ROUTES.audit,
    className: 'nav-audit',
  },
]


function getPageFromPath(pathname) {
  if (pathname === LEGACY_ROUTES.olistCallback) {
    return 'oauth-callback'
  }

  if (pathname === ROUTES.connections || pathname === LEGACY_ROUTES.olist) {
    return 'connections'
  }

  if (pathname === ROUTES.audit) {
    return 'audit'
  }

  if (pathname === ROUTES.users) {
    return 'users'
  }

  return 'login'
}


function navigateTo(path, replace = false) {
  const method = replace ? 'replaceState' : 'pushState'
  window.history[method]({}, '', path)
}


function formatDateTime(value) {
  if (!value) {
    return 'Não disponível'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}


function getConnectionStatusClass(status) {
  if (!status) {
    return 'neutral'
  }

  const normalizedStatus = status.toLowerCase()

  if (normalizedStatus.startsWith('conectad')) {
    return 'success'
  }

  if (normalizedStatus.startsWith('falha')) {
    return 'danger'
  }

  if (normalizedStatus.includes('pendente') || normalizedStatus.includes('aguardando')) {
    return 'warning'
  }

  return 'neutral'
}


function toneFromAudit(item) {
  return ['accent', 'success', 'danger'].includes(item.tone) ? item.tone : 'neutral'
}

function emptyPageFeedback() {
  return { message: '', tone: 'neutral' }
}

function StatusPill({ status }) {
  return (
    <span className={`status-pill ${status === 'Ativo' ? 'is-active' : 'is-inactive'}`}>
      {status}
    </span>
  )
}

function StatCard({ label, value, helper }) {
  return (
    <article className="stat-card">
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      <p>{helper}</p>
    </article>
  )
}

function ActivityItem({ item }) {
  return (
    <li className={`activity-item tone-${item.tone}`}>
      <div>
        <strong>{item.title}</strong>
        <p>{item.description}</p>
      </div>
      <span>{item.time}</span>
    </li>
  )
}

function UsersPage({
  currentUser,
  filteredUsers,
  query,
  setQuery,
  statusFilter,
  setStatusFilter,
  activity,
  onOpenCreate,
  onOpenPasswordFlow,
  onToggleUserStatus,
  onDeleteUser,
}) {
  return (
    <section className="dashboard-grid">
      <div className="dashboard-main">
        <section className="panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Usuários</span>
            </div>
            <div className="header-actions">
              <button type="button" className="primary-button" onClick={onOpenCreate}>
                Novo usuário
              </button>
            </div>
          </div>

          <div className="toolbar">
            <label className="input-shell">
              <span>Buscar</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar por e-mail ou perfil"
              />
            </label>

            <label className="input-shell compact">
              <span>Status</span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
              >
                <option>Todos</option>
                <option>Ativo</option>
                <option>Inativo</option>
              </select>
            </label>
          </div>

          <div className="table-shell">
            <div className="table-head">
              <span>Usuário</span>
              <span>Papel</span>
              <span>Status</span>
              <span>Último acesso</span>
              <span>Ações</span>
            </div>

            <div className="table-body">
              {filteredUsers.map((user) => (
                <article className="user-row compact-row" key={user.id}>
                  <div className="user-cell">
                    <div className="avatar-badge">{user.initials}</div>
                    <div>
                      <strong>{user.email}</strong>
                      <p className="user-meta">
                        {user.id} . Criado em {formatDateTime(user.createdAt)}
                      </p>
                    </div>
                  </div>

                  <span className="role-badge">{user.role}</span>
                  <StatusPill status={user.status} />
                  <span className="last-access">{formatDateTime(user.lastAccess)}</span>

                  <div className="row-actions">
                    <button
                      type="button"
                      className={`ghost-button ${user.status === 'Ativo' ? 'warning' : 'success'}`}
                      onClick={() => onToggleUserStatus(user)}
                      disabled={currentUser?.id === user.id && user.status === 'Ativo'}
                    >
                      {user.status === 'Ativo' ? 'Desativar' : 'Ativar'}
                    </button>
                    <button
                      type="button"
                      className="ghost-button"
                      onClick={() => onOpenPasswordFlow(user)}
                    >
                      Alterar senha
                    </button>
                    <button
                      type="button"
                      className="ghost-button danger"
                      onClick={() => onDeleteUser(user)}
                    >
                      Excluir
                    </button>
                  </div>
                </article>
              ))}

              {filteredUsers.length === 0 ? (
                <div className="empty-state">
                  <strong>Nenhum usuário encontrado</strong>
                  <p>Ajuste os filtros ou cadastre um novo usuário administrativo.</p>
                </div>
              ) : null}
            </div>
          </div>
        </section>
      </div>

      <aside className="dashboard-side">
        <section className="panel side-panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Operação</span>
            </div>
          </div>

          <ul className="activity-list">
            {activity.slice(0, 8).map((item) => (
              <ActivityItem key={item.id} item={item} />
            ))}
          </ul>
        </section>
      </aside>
    </section>
  )
}


function ConnectionsPage({
  overview,
  isSubmitting,
  onSaveOlistSettings,
  onConnectOlist,
  onRenewOlistToken,
  onValidateOlistApi,
}) {
  const supabase = overview?.supabase
  const olist = overview?.olist
  const [clientSecret, setClientSecret] = useState(olist?.clientSecret ?? '')
  const formattedLogs = useMemo(
    () =>
      (overview?.logs ?? []).map((item) => ({
        ...item,
        time: formatDateTime(item.time),
      })),
    [overview?.logs],
  )

  const statusClassName = getConnectionStatusClass(olist?.status)
  const databaseStatusClassName = getConnectionStatusClass(supabase?.status)

  function handleSubmit(event) {
    event.preventDefault()
    onSaveOlistSettings(clientSecret)
  }

  return (
    <section className="page-stack connections-page">
      <section className="page-grid">
        <article className="panel connections-panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Olist</span>
            </div>
            <span className={`connection-status-pill ${statusClassName}`}>
              {olist?.status ?? 'Carregando...'}
            </span>
          </div>

          <div className="key-value-list">
            <div className="key-value-row">
              <span>Status da conexão</span>
              <strong>{olist?.status ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Status do token</span>
              <strong>{olist?.tokenStatus ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Resumo</span>
              <strong>{olist?.message ?? 'Carregando...'}</strong>
            </div>
          </div>

          <form className="form-grid connections-form" onSubmit={handleSubmit}>
            <label className="input-shell">
              <span>Client Secret</span>
              <input
                type="text"
                value={clientSecret}
                onChange={(event) => setClientSecret(event.target.value)}
                placeholder="Informe o Client Secret da aplicação Olist"
              />
            </label>

            <label className="input-shell">
              <span>URL de redirecionamento para configurar no ERP</span>
              <input type="text" value={olist?.redirectUri ?? ''} readOnly />
            </label>

            <div className="key-value-row emphasis-row">
              <span>Orientação</span>
              <strong>{olist?.redirectInstruction ?? 'Carregando...'}</strong>
            </div>

            <div className="key-value-list compact-list">
              <div className="key-value-row">
                <span>Client ID</span>
                <strong>{olist?.clientId ?? 'Carregando...'}</strong>
              </div>
              <div className="key-value-row">
                <span>Base da API</span>
                <strong>{olist?.apiBaseUrl ?? 'Carregando...'}</strong>
              </div>
              <div className="key-value-row">
                <span>Fluxo de OAuth</span>
                <strong>{olist?.authMode ?? 'Carregando...'}</strong>
              </div>
              <div className="key-value-row">
                <span>Último callback recebido</span>
                <strong>{formatDateTime(olist?.lastCallbackAt)}</strong>
              </div>
              <div className="key-value-row">
                <span>Última tentativa de conexão</span>
                <strong>{formatDateTime(olist?.lastConnectAttemptAt)}</strong>
              </div>
              <div className="key-value-row">
                <span>Última renovação registrada</span>
                <strong>{formatDateTime(olist?.lastTokenRefreshAt)}</strong>
              </div>
              <div className="key-value-row">
                <span>Expiração do access token</span>
                <strong>{formatDateTime(olist?.accessTokenExpiresAt)}</strong>
              </div>
              <div className="key-value-row">
                <span>Expiração do refresh token</span>
                <strong>{formatDateTime(olist?.refreshTokenExpiresAt)}</strong>
              </div>
            </div>

            <div className="toolbar connections-actions">
              <button type="submit" className="ghost-button" disabled={isSubmitting}>
                Salvar Client Secret
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={() => onConnectOlist(clientSecret)}
                disabled={isSubmitting || clientSecret.trim().length === 0}
              >
                Conectar
              </button>
              <button
                type="button"
                className="ghost-button"
                onClick={onRenewOlistToken}
                disabled={isSubmitting}
              >
                Renovar token
              </button>
              <button
                type="button"
                className="ghost-button success"
                onClick={onValidateOlistApi}
                disabled={isSubmitting}
              >
                Validar API
              </button>
            </div>
          </form>
        </article>

        <article className="panel connections-traceability-panel">
          <div className="panel-header compact connections-traceability-header">
            <div>
              <span className="eyebrow">Rastreabilidade</span>
            </div>
          </div>

          <div className="connection-log-scroll">
            {formattedLogs.length > 0 ? (
              <ul className="activity-list audit-list connection-log-list">
                {formattedLogs.map((item) => (
                  <ActivityItem key={item.id} item={item} />
                ))}
              </ul>
            ) : (
              <div className="empty-state">
                <strong>Nenhum registro de conexão disponível</strong>
                <p>Os eventos de OAuth da Olist aparecerão aqui.</p>
              </div>
            )}
          </div>
        </article>

        <article className="panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Banco de dados</span>
            </div>
            <span className={`connection-status-pill ${databaseStatusClassName}`}>
              {supabase?.status ?? 'Carregando...'}
            </span>
          </div>

          <div className="key-value-list">
            <div className="key-value-row">
              <span>Status</span>
              <strong>{supabase?.status ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Provedor</span>
              <strong>{supabase?.provider ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Host</span>
              <strong>{supabase?.host ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Banco</span>
              <strong>{supabase?.database ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Usuários persistidos</span>
              <strong>{supabase?.users ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Resumo</span>
              <strong>{supabase?.detail ?? 'Carregando...'}</strong>
            </div>
          </div>
        </article>

      </section>
    </section>
  )
}


function OlistCallbackPage({ phase, message }) {
  const title = phase === 'error' ? 'Falha na conexão Olist' : 'Concluindo conexão Olist'
  const detail =
    message ||
    (phase === 'processing'
      ? 'Aguardando a troca do código de autorização por tokens de acesso.'
      : 'Processando o retorno OAuth da Olist.')

  return (
    <section className="page-stack">
      <section className="panel panel-glow">
        <div className="panel-header">
          <div>
            <span className="eyebrow">OAuth</span>
            <h2>{title}</h2>
          </div>
        </div>
        <div className="key-value-list">
          <div className="key-value-row">
            <span>Status</span>
            <strong>{phase === 'error' ? 'Erro' : 'Processando'}</strong>
          </div>
          <div className="key-value-row">
            <span>Detalhe</span>
            <strong>{detail}</strong>
          </div>
        </div>
      </section>
    </section>
  )
}


function AuditPage({ activity }) {
  const successCount = activity.filter((item) => item.tone === 'success').length
  const dangerCount = activity.filter((item) => item.tone === 'danger').length

  const cards = [
    {
      label: 'Eventos carregados',
      value: String(activity.length).padStart(2, '0'),
      helper: 'Últimos registros disponíveis',
    },
    {
      label: 'Ações concluídas',
      value: String(successCount).padStart(2, '0'),
      helper: 'Eventos positivos recentes',
    },
    {
      label: 'Alertas',
      value: String(dangerCount).padStart(2, '0'),
      helper: 'Itens que exigem atenção',
    },
  ]

  return (
    <section className="page-stack">
      <section className="panel panel-glow audit-summary-panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">Rastreabilidade</span>
            <h2>Auditoria da aplicação</h2>
          </div>
        </div>

        <div className="stats-row stats-row-compact">
          {cards.map((card) => (
            <StatCard key={card.label} {...card} />
          ))}
        </div>
      </section>

      <section className="panel audit-timeline-panel">
        <div className="panel-header compact audit-timeline-header">
          <div>
            <span className="eyebrow">Linha do tempo</span>
            <h2>Eventos recentes</h2>
          </div>
        </div>

        <ul className="activity-list audit-list">
          {activity.map((item) => (
            <ActivityItem key={item.id} item={item} />
          ))}
        </ul>
      </section>
    </section>
  )
}

function App() {
  const [activePage, setActivePage] = useState(() => getPageFromPath(window.location.pathname))
  const [currentUser, setCurrentUser] = useState(null)
  const [users, setUsers] = useState([])
  const [activity, setActivity] = useState([])
  const [connectionsOverview, setConnectionsOverview] = useState(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('Todos')
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [passwordTarget, setPasswordTarget] = useState(null)
  const [loginError, setLoginError] = useState('')
  const [pageFeedback, setPageFeedback] = useState(() => emptyPageFeedback())
  const [oauthCallbackState, setOauthCallbackState] = useState({
    phase: 'idle',
    message: '',
  })
  const [isBooting, setIsBooting] = useState(() => Boolean(getStoredToken()))
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [loginForm, setLoginForm] = useState({
    email: 'admin@empresa.com',
    password: '',
  })
  const [createForm, setCreateForm] = useState({
    email: '',
    password: '',
    status: 'Ativo',
  })
  const [passwordForm, setPasswordForm] = useState({
    password: '',
    confirmPassword: '',
  })

  const isAuthenticated = currentUser !== null

  function clearPageFeedback() {
    setPageFeedback(emptyPageFeedback())
  }

  function showPageFeedback(message, tone = 'danger') {
    setPageFeedback({ message, tone })
  }

  const navigate = useCallback((path, replace = false) => {
    navigateTo(path, replace)
    setActivePage(getPageFromPath(path))
  }, [])

  const hydrateAuthenticatedData = useCallback(async () => {
    const [usersData, auditData, overviewData] = await Promise.all([
      apiRequest('/users'),
      apiRequest('/audit'),
      apiRequest('/connections/overview'),
    ])

    setUsers(usersData)
    setActivity(
      auditData.map((item) => ({
        ...item,
        tone: toneFromAudit(item),
        time: formatDateTime(item.time),
      })),
    )
    setConnectionsOverview(overviewData)
    clearPageFeedback()
  }, [])

  useEffect(() => {
    document.title = 'Albertina'
  }, [])

  useEffect(() => {
    const handlePopState = () => {
      setActivePage(getPageFromPath(window.location.pathname))
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    if (window.location.pathname === LEGACY_ROUTES.olist) {
      window.history.replaceState({}, '', ROUTES.connections)
    }
  }, [])

  useEffect(() => {
    const token = getStoredToken()
    if (!token) {
      if (window.location.pathname !== ROUTES.login) {
        window.history.replaceState({}, '', ROUTES.login)
      }
      return
    }

    async function restoreSession() {
      try {
        const user = await apiRequest('/auth/me')
        setCurrentUser(user)
        if (window.location.pathname === ROUTES.login) {
          navigate(ROUTES.users, true)
        }
        await hydrateAuthenticatedData()
      } catch {
        clearStoredToken()
        setCurrentUser(null)
        setUsers([])
        setActivity([])
        setConnectionsOverview(null)
        clearPageFeedback()
        navigate(ROUTES.login, true)
      } finally {
        setIsBooting(false)
      }
    }

    restoreSession()
  }, [hydrateAuthenticatedData, navigate])

  useEffect(() => {
    if (!isAuthenticated || activePage !== 'oauth-callback' || oauthCallbackState.phase === 'processing') {
      return
    }

    const search = new URLSearchParams(window.location.search)
    const payload = {
      code: search.get('code'),
      state: search.get('state'),
      error: search.get('error'),
      error_description: search.get('error_description'),
    }

    async function finishOAuthCallback() {
      try {
        await apiRequest('/connections/olist/callback', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        showPageFeedback('Conexão Olist concluída com sucesso.', 'success')
        await hydrateAuthenticatedData()
        setOauthCallbackState({
          phase: 'success',
          message: 'Conexão Olist concluída com sucesso.',
        })
        navigate(ROUTES.connections, true)
      } catch (error) {
        const message =
          error instanceof ApiError
            ? error.message
            : 'Não foi possível concluir o callback OAuth da Olist.'
        showPageFeedback(message, 'danger')
        setOauthCallbackState({
          phase: 'error',
          message,
        })
        navigate(ROUTES.connections, true)
      }
    }

    finishOAuthCallback()
  }, [
    activePage,
    hydrateAuthenticatedData,
    isAuthenticated,
    navigate,
    oauthCallbackState.phase,
  ])
  const filteredUsers = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()


    return users.filter((user) => {
      const matchesStatus = statusFilter === 'Todos' || user.status === statusFilter
      const matchesQuery =
        normalizedQuery.length === 0 ||
        user.email.toLowerCase().includes(normalizedQuery) ||
        user.role.toLowerCase().includes(normalizedQuery)

      return matchesStatus && matchesQuery
    })
  }, [query, statusFilter, users])

  async function handleLogin(event) {
    event.preventDefault()

    const email = loginForm.email.trim().toLowerCase()
    const password = loginForm.password.trim()

    if (!email || !password) {
      setLoginError('Informe e-mail e senha para entrar.')
      return
    }

    setIsSubmitting(true)
    try {
      const response = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setStoredToken(response.token)
      setCurrentUser(response.user)
      setLoginForm((current) => ({ ...current, password: '' }))
      setLoginError('')
      navigate(ROUTES.users, true)
      await hydrateAuthenticatedData()
    } catch (error) {
      setLoginError(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível iniciar a sessão agora.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  function resetCreateForm() {
    setCreateForm({
      email: '',
      password: '',
      status: 'Ativo',
    })
  }

  async function handleCreateUser(event) {
    event.preventDefault()

    const email = createForm.email.trim().toLowerCase()
    const password = createForm.password.trim()

    if (!email || !password) {
      return
    }

    setIsSubmitting(true)
    try {
      await apiRequest('/users', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          status: createForm.status,
        }),
      })
      resetCreateForm()
      setIsCreateOpen(false)
      showPageFeedback('Usuário criado com sucesso.', 'success')
      await hydrateAuthenticatedData()
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível criar o usuário.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDeleteUser(user) {
    const confirmed = window.confirm(`Excluir o usuário ${user.email}?`)
    if (!confirmed) {
      return
    }

    setIsSubmitting(true)
    try {
      await apiRequest(`/users/${user.id}`, { method: 'DELETE' })
      showPageFeedback('Usuário excluído com sucesso.', 'success')
      await hydrateAuthenticatedData()
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível excluir o usuário.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleToggleUserStatus(user) {
    const nextStatus = user.status === 'Ativo' ? 'Inativo' : 'Ativo'
    const actionLabel = nextStatus === 'Ativo' ? 'ativar' : 'desativar'
    const confirmed = window.confirm(`${actionLabel} o usuário ${user.email}?`)
    if (!confirmed) {
      return
    }

    setIsSubmitting(true)
    try {
      const updatedUser = await apiRequest(`/users/${user.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: nextStatus }),
      })
      setUsers((current) => current.map((item) => (item.id === updatedUser.id ? updatedUser : item)))
      showPageFeedback(
        nextStatus === 'Ativo' ? 'Usuário ativado com sucesso.' : 'Usuário desativado com sucesso.',
        'success',
      )
      await hydrateAuthenticatedData()
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível atualizar o status do usuário.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  function openPasswordFlow(user) {
    setPasswordTarget(user)
    setPasswordForm({
      password: '',
      confirmPassword: '',
    })
  }

  async function handlePasswordUpdate(event) {
    event.preventDefault()

    if (!passwordTarget) {
      return
    }

    if (
      passwordForm.password.trim().length < 8 ||
      passwordForm.password !== passwordForm.confirmPassword
    ) {
      showPageFeedback('A nova senha precisa ter ao menos 8 caracteres e confirmação idêntica.', 'danger')
      return
    }

    setIsSubmitting(true)
    try {
      await apiRequest(`/users/${passwordTarget.id}/password`, {
        method: 'PATCH',
        body: JSON.stringify(passwordForm),
      })
      setPasswordTarget(null)
      setPasswordForm({
        password: '',
        confirmPassword: '',
      })
      showPageFeedback('Senha atualizada com sucesso.', 'success')
      await hydrateAuthenticatedData()
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível atualizar a senha.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleLogout() {
    try {
      await apiRequest('/auth/logout', { method: 'POST' })
    } catch {
      // A limpeza local da sessão é suficiente mesmo se a API estiver indisponível.
    } finally {
      clearStoredToken()
      setCurrentUser(null)
      setUsers([])
      setActivity([])
      setConnectionsOverview(null)
      clearPageFeedback()
      navigate(ROUTES.login, true)
    }
  }

  function closeCreateModal() {
    setIsCreateOpen(false)
    resetCreateForm()
  }

  function closePasswordModal() {
    setPasswordTarget(null)
    setPasswordForm({
      password: '',
      confirmPassword: '',
    })
  }

  async function handleSaveOlistSettings(clientSecret) {
    setIsSubmitting(true)
    try {
      const olist = await apiRequest('/connections/olist/settings', {
        method: 'PATCH',
        body: JSON.stringify({ clientSecret }),
      })
      setConnectionsOverview((current) => ({ ...current, olist }))
      showPageFeedback('Client Secret salvo com sucesso.', 'success')
      await hydrateAuthenticatedData()
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível salvar a configuração da Olist.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleConnectOlist(clientSecret) {
    setIsSubmitting(true)
    try {
      if (clientSecret.trim().length > 0) {
        await apiRequest('/connections/olist/settings', {
          method: 'PATCH',
          body: JSON.stringify({ clientSecret }),
        })
      }
      const response = await apiRequest('/connections/olist/connect', {
        method: 'POST',
      })
      clearPageFeedback()
      if (response.authorizationUrl) {
        window.location.assign(response.authorizationUrl)
        return
      }
      showPageFeedback('Preparação da conexão Olist concluída.', 'success')
      await hydrateAuthenticatedData()
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível iniciar a conexão Olist.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleRenewOlistToken() {
    setIsSubmitting(true)
    try {
      const response = await apiRequest('/connections/olist/renew-token', {
        method: 'POST',
      })
      setConnectionsOverview((current) => ({ ...current, olist: response.olist }))
      showPageFeedback('Token Olist renovado com sucesso.', 'success')
      await hydrateAuthenticatedData()
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível renovar o token da Olist.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleValidateOlistApi() {
    setIsSubmitting(true)
    try {
      const response = await apiRequest('/connections/olist/api-test')
      setConnectionsOverview((current) => ({ ...current, olist: response.olist }))
      showPageFeedback('API Olist validada com sucesso.', 'success')
      await hydrateAuthenticatedData()
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível validar a API da Olist.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  function renderAuthenticatedPage() {
    if (activePage === 'oauth-callback') {
      return (
        <OlistCallbackPage
          phase={oauthCallbackState.phase === 'error' ? 'error' : 'processing'}
          message={
            oauthCallbackState.phase === 'error'
              ? oauthCallbackState.message
              : 'Concluindo a autorização OAuth da Olist...'
          }
        />
      )
    }

    if (activePage === 'connections') {
      return (
        <ConnectionsPage
          key={[
            connectionsOverview?.olist?.clientSecret ?? '',
            connectionsOverview?.olist?.status ?? '',
            connectionsOverview?.olist?.lastCallbackAt ?? '',
            connectionsOverview?.olist?.lastConnectAttemptAt ?? '',
            connectionsOverview?.olist?.lastTokenRefreshAt ?? '',
            String(connectionsOverview?.logs?.length ?? 0),
          ].join('|')}
          overview={connectionsOverview}
          isSubmitting={isSubmitting}
          onSaveOlistSettings={handleSaveOlistSettings}
          onConnectOlist={handleConnectOlist}
          onRenewOlistToken={handleRenewOlistToken}
          onValidateOlistApi={handleValidateOlistApi}
        />
      )
    }

    if (activePage === 'audit') {
      return <AuditPage activity={activity} />
    }

    return (
      <UsersPage
        currentUser={currentUser}
        filteredUsers={filteredUsers}
        query={query}
        setQuery={setQuery}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        activity={activity}
        onOpenCreate={() => setIsCreateOpen(true)}
        onOpenPasswordFlow={openPasswordFlow}
        onToggleUserStatus={handleToggleUserStatus}
        onDeleteUser={handleDeleteUser}
      />
    )
  }

  if (isBooting) {
    return (
      <main className="app-shell is-login">
        <section className="login-layout">
          <article className="panel login-panel">
            <h1>Carregando</h1>
            <p className="hero-text narrow">Validando a sessão ativa da aplicação.</p>
          </article>
        </section>
      </main>
    )
  }

  return (
    <main className={`app-shell ${isAuthenticated ? 'is-authenticated' : 'is-login'}`}>
      {!isAuthenticated ? (
        <header className="login-brand">
          <img className="login-brand-image" src="/albertina.png" alt="Albertina" />
        </header>
      ) : (
        <header className="topbar">
          <nav className="topbar-nav" aria-label="Menu principal">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`nav-link ${item.className} ${activePage === item.key ? 'active' : ''}`}
                onClick={() => navigate(item.path)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="topbar-actions">
            <button
              type="button"
              className="nav-link nav-users topbar-logout-button"
              onClick={handleLogout}
            >
              Sair
            </button>
          </div>
        </header>
      )}

      {!isAuthenticated ? (
        <section className="login-layout">
          <article className="panel login-panel">
            <h1>Entrar</h1>
            <p className="hero-text narrow">
              Acesse o painel administrativo.
            </p>

            <form className="form-grid" onSubmit={handleLogin}>
              <label className="input-shell">
                <span>E-mail</span>
                <input
                  type="email"
                  value={loginForm.email}
                  onChange={(event) =>
                    setLoginForm((current) => ({
                      ...current,
                      email: event.target.value,
                    }))
                  }
                  placeholder="admin@empresa.com"
                  required
                />
              </label>

              <label className="input-shell">
                <span>Senha</span>
                <input
                  type="password"
                  value={loginForm.password}
                  onChange={(event) =>
                    setLoginForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                  placeholder="Digite sua senha"
                  required
                />
              </label>

              {loginError ? <p className="form-error">{loginError}</p> : null}

              <div className="login-actions">
                <button type="submit" className="primary-button full" disabled={isSubmitting}>
                  Entrar no painel
                </button>
              </div>
            </form>
          </article>
        </section>
      ) : (
        <>
          {pageFeedback.message ? (
            <p className={`page-feedback ${pageFeedback.tone}`}>{pageFeedback.message}</p>
          ) : null}
          {renderAuthenticatedPage()}
        </>
      )}

      {isCreateOpen ? (
        <section className="overlay" role="dialog" aria-modal="true" aria-label="Criar usuário">
          <div className="modal-card">
            <div className="panel-header compact modal-header">
              <div>
                <span className="eyebrow">Novo usuário</span>
                <h2>Criar acesso administrativo</h2>
                <p className="modal-helper">
                  Cadastre um novo acesso com e-mail válido e status inicial definido.
                </p>
              </div>
              <button type="button" className="icon-button" onClick={closeCreateModal}>
                Fechar
              </button>
            </div>

            <form className="form-grid" onSubmit={handleCreateUser}>
              <label className="input-shell">
                <span>E-mail</span>
                <input
                  type="email"
                  value={createForm.email}
                  onChange={(event) =>
                    setCreateForm((current) => ({
                      ...current,
                      email: event.target.value,
                    }))
                  }
                  placeholder="novo.admin@empresa.com"
                  required
                />
              </label>

              <label className="input-shell">
                <span>Senha inicial</span>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(event) =>
                    setCreateForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                  placeholder="Mínimo de 8 caracteres"
                  minLength={8}
                  required
                />
              </label>

              <label className="input-shell">
                <span>Status inicial</span>
                <select
                  value={createForm.status}
                  onChange={(event) =>
                    setCreateForm((current) => ({
                      ...current,
                      status: event.target.value,
                    }))
                  }
                >
                  <option>Ativo</option>
                  <option>Inativo</option>
                </select>
              </label>

              <div className="modal-actions">
                <button type="button" className="ghost-button" onClick={closeCreateModal}>
                  Cancelar
                </button>
                <button type="submit" className="primary-button" disabled={isSubmitting}>
                  Criar usuário
                </button>
              </div>
            </form>
          </div>
        </section>
      ) : null}

      {passwordTarget ? (
        <section
          className="overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Alterar senha do usuário"
        >
          <div className="modal-card">
            <div className="panel-header compact modal-header">
              <div>
                <span className="eyebrow">Alterar senha</span>
                <h2>{passwordTarget.email}</h2>
                <p className="modal-helper">
                  Defina uma nova senha e confirme o valor para concluir a atualização.
                </p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={closePasswordModal}
              >
                Fechar
              </button>
            </div>

            <form className="form-grid" onSubmit={handlePasswordUpdate}>
              <label className="input-shell">
                <span>Nova senha</span>
                <input
                  type="password"
                  value={passwordForm.password}
                  onChange={(event) =>
                    setPasswordForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                  minLength={8}
                  placeholder="Nova senha"
                  required
                />
              </label>

              <label className="input-shell">
                <span>Confirmar senha</span>
                <input
                  type="password"
                  value={passwordForm.confirmPassword}
                  onChange={(event) =>
                    setPasswordForm((current) => ({
                      ...current,
                      confirmPassword: event.target.value,
                    }))
                  }
                  minLength={8}
                  placeholder="Repita a senha"
                  required
                />
              </label>

              <div className="modal-actions">
                <button
                  type="button"
                  className="ghost-button"
                  onClick={closePasswordModal}
                >
                  Cancelar
                </button>
                <button type="submit" className="primary-button" disabled={isSubmitting}>
                  Salvar nova senha
                </button>
              </div>
            </form>
          </div>
        </section>
      ) : null}
    </main>
  )
}

export default App
