import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import { ApiError, apiRequest, clearStoredToken, getStoredToken, setStoredToken } from './api'


const ROUTES = {
  login: '/',
  users: '/usuarios',
  olist: '/olist',
  audit: '/auditoria',
}

const NAV_ITEMS = [
  {
    key: 'users',
    label: 'Administração de Usuários',
    path: ROUTES.users,
    className: 'nav-users',
  },
  {
    key: 'olist',
    label: 'Conexão Olist',
    path: ROUTES.olist,
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
  if (pathname === ROUTES.olist) {
    return 'olist'
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


function formatAuditTime(value) {
  if (!value) {
    return 'agora'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  const diffMinutes = Math.round((Date.now() - date.getTime()) / 60_000)
  if (diffMinutes <= 1) {
    return 'agora'
  }

  if (diffMinutes < 60) {
    return `há ${diffMinutes} min`
  }

  const diffHours = Math.round(diffMinutes / 60)
  if (diffHours < 24) {
    return `há ${diffHours} h`
  }

  return date.toLocaleDateString('pt-BR')
}


function toneFromAudit(item) {
  return ['accent', 'success', 'danger'].includes(item.tone) ? item.tone : 'neutral'
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
  onLogout,
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
              <h2>Administração de usuários</h2>
            </div>
            <div className="header-actions">
              <button type="button" className="ghost-button" onClick={onLogout}>
                Sair
              </button>
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
                      <p>
                        {user.id} . Criado em {user.createdAt}
                      </p>
                    </div>
                  </div>

                  <span className="role-badge">{user.role}</span>
                  <StatusPill status={user.status} />
                  <span className="last-access">{user.lastAccess}</span>

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
              <h2>Atividade recente</h2>
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


function OlistPage({ overview }) {
  const cards = [
    {
      label: 'Status da conexão',
      value: overview?.status ?? 'Carregando...',
      helper: 'Situação atual da integração',
    },
    {
      label: 'Modo de autenticação',
      value: overview?.authMode ?? 'OAuth 2',
      helper: 'Fluxo previsto para a conta Olist',
    },
    {
      label: 'Próxima etapa',
      value: overview?.nextStep ?? 'Aguardando configuração',
      helper: 'Passo sugerido para avançar',
    },
  ]

  return (
    <section className="page-stack">
      <section className="panel panel-glow">
        <div className="panel-header">
          <div>
            <span className="eyebrow">Integração</span>
            <h2>Conexão Olist</h2>
          </div>
        </div>

        <div className="stats-row stats-row-compact">
          {cards.map((card) => (
            <StatCard key={card.label} {...card} />
          ))}
        </div>
      </section>

      <section className="page-grid">
        <article className="panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Configuração</span>
              <h2>Parâmetros da integração</h2>
            </div>
          </div>

          <div className="key-value-list">
            <div className="key-value-row">
              <span>Base da API</span>
              <strong>{overview?.apiBaseUrl ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Redirect URI</span>
              <strong>{overview?.redirectUri ?? 'Carregando...'}</strong>
            </div>
            <div className="key-value-row">
              <span>Fluxo OAuth</span>
              <strong>{overview?.authMode ?? 'Carregando...'}</strong>
            </div>
          </div>
        </article>

        <article className="panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Próximos passos</span>
              <h2>Backlog imediato</h2>
            </div>
          </div>

          <ul className="detail-list">
            <li>Implementar o redirecionamento para autorização OAuth da Olist.</li>
            <li>Persistir `access_token` e `refresh_token` com proteção adequada.</li>
            <li>Criar teste de saúde da conexão antes da primeira carga de dados.</li>
            <li>Adicionar controle de rate limit e retry por endpoint confirmado.</li>
          </ul>
        </article>
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
      <section className="panel panel-glow">
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

      <section className="panel">
        <div className="panel-header compact">
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
  const [olistOverview, setOlistOverview] = useState(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('Todos')
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [passwordTarget, setPasswordTarget] = useState(null)
  const [loginError, setLoginError] = useState('')
  const [pageError, setPageError] = useState('')
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

  const navigate = useCallback((path, replace = false) => {
    navigateTo(path, replace)
    setActivePage(getPageFromPath(path))
  }, [])

  const hydrateAuthenticatedData = useCallback(async () => {
    const [usersData, auditData, overviewData] = await Promise.all([
      apiRequest('/users'),
      apiRequest('/audit'),
      apiRequest('/olist/overview'),
    ])

    setUsers(usersData)
    setActivity(
      auditData.map((item) => ({
        ...item,
        tone: toneFromAudit(item),
        time: formatAuditTime(item.time),
      })),
    )
    setOlistOverview(overviewData)
    setPageError('')
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
        setOlistOverview(null)
        navigate(ROUTES.login, true)
      } finally {
        setIsBooting(false)
      }
    }

    restoreSession()
  }, [hydrateAuthenticatedData, navigate])
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
      await hydrateAuthenticatedData()
    } catch (error) {
      setPageError(
        error instanceof ApiError ? error.message : 'Não foi possível criar o usuário.',
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
      await hydrateAuthenticatedData()
    } catch (error) {
      setPageError(
        error instanceof ApiError ? error.message : 'Não foi possível excluir o usuário.',
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
      setPageError('')
      await hydrateAuthenticatedData()
    } catch (error) {
      setPageError(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível atualizar o status do usuário.',
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
      setPageError('A nova senha precisa ter ao menos 8 caracteres e confirmação idêntica.')
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
      await hydrateAuthenticatedData()
    } catch (error) {
      setPageError(
        error instanceof ApiError ? error.message : 'Não foi possível atualizar a senha.',
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
      setOlistOverview(null)
      setPageError('')
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

  function renderAuthenticatedPage() {
    if (activePage === 'olist') {
      return <OlistPage overview={olistOverview} />
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
        onLogout={handleLogout}
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
          {pageError ? <p className="page-error">{pageError}</p> : null}
          {renderAuthenticatedPage()}
        </>
      )}

      {isCreateOpen ? (
        <section className="overlay" role="dialog" aria-modal="true" aria-label="Criar usuário">
          <div className="modal-card">
            <div className="panel-header compact">
              <div>
                <span className="eyebrow">Novo usuário</span>
                <h2>Criar acesso administrativo</h2>
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
            <div className="panel-header compact">
              <div>
                <span className="eyebrow">Alterar senha</span>
                <h2>{passwordTarget.email}</h2>
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
