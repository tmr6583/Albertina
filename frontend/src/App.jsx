import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import { ApiError, apiRequest, clearStoredToken, getStoredToken, setStoredToken } from './api'


const ROUTES = {
  login: '/',
  users: '/usuarios',
  connections: '/conexoes',
  extraction: '/extracao',
}

const LEGACY_ROUTES = {
  olist: '/olist',
  olistCallback: '/olist/callback',
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
    key: 'connections',
    label: 'Conexões',
    path: ROUTES.connections,
    className: 'nav-olist',
  },
  {
    key: 'extraction',
    label: 'Extração',
    path: ROUTES.extraction,
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

  if (pathname === ROUTES.extraction) {
    return 'extraction'
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

  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const year = String(date.getFullYear())
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')

  return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`
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


function toneFromExtractionStatus(status) {
  if (status === 'error') {
    return 'danger'
  }
  if (status === 'cancelled') {
    return 'warning'
  }
  if (status === 'running') {
    return 'accent'
  }
  return 'success'
}


function labelFromExtractionStatus(status) {
  if (status === 'error') {
    return 'Com erro'
  }
  if (status === 'cancelled') {
    return 'Interrompida'
  }
  if (status === 'running') {
    return 'Em andamento'
  }
  return 'Concluída'
}

function labelFromEntityQueueStatus(status) {
  if (status === 'pending') {
    return 'Pendente'
  }

  return labelFromExtractionStatus(status)
}

function toneFromEntityQueueStatus(status) {
  if (status === 'pending') {
    return 'neutral'
  }

  return toneFromExtractionStatus(status)
}


function toTimestamp(value) {
  if (!value) {
    return null
  }
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? null : timestamp
}


function formatDuration(totalSeconds) {
  if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) {
    return '00:00'
  }

  const normalizedSeconds = Math.max(0, Math.round(totalSeconds))
  const hours = Math.floor(normalizedSeconds / 3600)
  const minutes = Math.floor((normalizedSeconds % 3600) / 60)
  const seconds = normalizedSeconds % 60

  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }

  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function formatDurationHuman(totalSeconds) {
  if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) {
    return '--'
  }

  const normalizedSeconds = Math.max(0, Math.round(totalSeconds))
  const hours = Math.floor(normalizedSeconds / 3600)
  const minutes = Math.floor((normalizedSeconds % 3600) / 60)
  const seconds = normalizedSeconds % 60

  if (hours > 0) {
    return `${String(hours).padStart(2, '0')}h ${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`
  }

  if (minutes > 0) {
    return `${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`
  }

  return `${String(seconds).padStart(2, '0')}s`
}

function labelFromExecutionType(executionType) {
  return executionType === 'reconciliation' ? 'Conciliação' : 'Incremental'
}

// #region debug-point extraction-ui-stall-reporting
function reportExtractionDebug(hypothesisId, location, msg, data = {}) {
  fetch('http://127.0.0.1:7777/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionId: 'extraction-ui-stall',
      runId: 'pre-fix',
      hypothesisId,
      location,
      msg,
      data,
      ts: Date.now(),
    }),
  }).catch(() => {})
}
// #endregion

function formatRequestsPerMinute(value) {
  if (!Number.isFinite(value) || value <= 0) {
    return 'Aguardando ritmo'
  }

  return `${value.toFixed(value >= 10 ? 0 : 1)} req/min`
}

function formatEtaLabel(value, fallback = 'Calculando') {
  if (!Number.isFinite(value) || value <= 0) {
    return fallback
  }

  return formatDuration(value)
}

function formatHighlightedErrorCount(value) {
  const normalizedValue = Number(value) || 0
  return normalizedValue > 0 ? `##!!## ${normalizedValue} ##!!##` : String(normalizedValue)
}

function getRunLineProgress(run) {
  const details = run?.details ?? {}
  const processed = Math.max(0, Number(details.sourceContextsProcessed) || 0)
  const total = Math.max(0, Number(details.sourceContextsTotal) || 0)
  const remaining = total > 0 ? Math.max(total - processed, 0) : 0
  const inserted = Math.max(0, Number(details.insertedCount) || 0)
  const updated = Math.max(0, Number(details.updatedCount) || 0)
  const extracted = Math.max(0, Number(details.extractedCount) || 0)

  return {
    processed,
    total,
    remaining,
    inserted,
    updated,
    extracted,
    lineProgressLabel: total > 0 ? `${processed}/${total}` : (processed > 0 ? `${processed}` : '--'),
    lineRemainingLabel: total > 0 ? `${remaining}` : '--',
    persistenceBreakdownLabel: `${inserted} inseridas • ${updated} atualizadas`,
  }
}

function buildExtractionExecutionLogText(payload) {
  const runs = payload?.runs ?? []
  const logs = payload?.logs ?? []
  const lines = [
    'Albertina - Log da Execução de Extração',
    `Execução: ${payload?.executionId ?? 'Não informado'}`,
    `Tipo: ${labelFromExecutionType(payload?.executionType)}`,
    `Início: ${formatDateTime(payload?.startedAt)}`,
    `Fim: ${formatDateTime(payload?.finishedAt)}`,
    `Tempo total: ${payload?.durationLabel ?? formatDurationHuman(payload?.durationSeconds)}`,
    `Requisições: ${payload?.requestCount ?? 0}`,
    `Persistências: ${payload?.successCount ?? 0}`,
    `Erros: ${formatHighlightedErrorCount(payload?.errorCount)}`,
    `Entidades previstas: ${payload?.entityTotal ?? 0}`,
    `Entidades com sucesso: ${payload?.entitiesSuccess ?? 0}`,
    `Entidades interrompidas: ${payload?.entitiesCancelled ?? 0}`,
    `Entidades com erro: ${payload?.entitiesError ?? 0}`,
    '',
    'Entidades processadas',
    '--------------------',
  ]

  if (runs.length === 0) {
    lines.push('Nenhuma entidade registrada nesta execução.')
  } else {
    runs.forEach((item, index) => {
      const lineProgress = getRunLineProgress(item)
      lines.push(
        `${index + 1}. ${item.entityName ?? 'Entidade não informada'}`,
        `   Status: ${labelFromExtractionStatus(item.status)}`,
        `   Modo: ${item.syncMode ?? 'Não informado'}`,
        `   Início: ${formatDateTime(item.startedAt)}`,
        `   Fim: ${formatDateTime(item.finishedAt)}`,
        `   Tempo total: ${item.durationLabel ?? formatDurationHuman(item.durationSeconds)}`,
        `   Requisições: ${item.requestCount ?? 0}`,
        `   Persistências: ${item.successCount ?? 0}`,
        `   Erros: ${formatHighlightedErrorCount(item.errorCount)}`,
      )
      if (lineProgress.total > 0 || lineProgress.processed > 0) {
        lines.push(
          `   Linhas processadas: ${lineProgress.lineProgressLabel}`,
          `   Linhas faltantes: ${lineProgress.lineRemainingLabel}`,
          `   Inserção: ${lineProgress.persistenceBreakdownLabel}`,
        )
      }
      lines.push('')
    })
  }

  lines.push('', 'Eventos do log', '---------------')

  if (logs.length === 0) {
    lines.push('Nenhum evento detalhado registrado.')
  } else {
    logs.forEach((item, index) => {
      const isErrorLog =
        (Number(item.errorCount) || 0) > 0 ||
        String(item.level ?? '').toUpperCase() === 'ERROR' ||
        Boolean(item.stackTrace)

      lines.push(
        `${index + 1}. ${formatDateTime(item.createdAt)} | ${item.level ?? 'INFO'} | ${item.entityName ?? 'Geral'} | ${item.stage ?? 'Etapa não informada'}`,
        `   Mensagem: ${item.message ?? 'Sem mensagem detalhada.'}`,
        `   Extraídos: ${item.extractedCount ?? 0} | Inseridos: ${item.insertedCount ?? 0} | Atualizados: ${item.updatedCount ?? 0} | Erros: ${formatHighlightedErrorCount(item.errorCount)}`,
      )

      if (isErrorLog) {
        lines.push('   ##!!## ERRO DETECTADO ##!!##')
      }

      if (item.stackTrace) {
        lines.push('   Detalhe técnico:', `${item.stackTrace}`)
      }

      lines.push('')
    })
  }

  return lines.join('\n')
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

function ExtractionExecutionSummaryCard({ summary }) {
  return (
    <article className={`extraction-executive-card tone-${summary.tone}`}>
      <header className="extraction-executive-header">
        <div>
          <span className="eyebrow">Resumo executivo</span>
          <strong>{summary.title}</strong>
        </div>
        <div className="extraction-executive-header-side">
          <span className={`extraction-executive-status is-${summary.tone}`}>{summary.statusLabel}</span>
          <span>{summary.time}</span>
        </div>
      </header>

      <div className="extraction-executive-grid">
        {summary.blocks.map((block) => (
          <section
            key={block.label}
            className={`extraction-executive-block ${block.featured ? 'is-featured' : ''} ${block.fullWidth ? 'is-full-width' : ''} ${block.variant ? `is-${block.variant}` : ''}`}
          >
            <span>{block.label}</span>
            {block.metrics ? (
              <div className="extraction-executive-metrics">
                {block.metrics.map((metric) => (
                  <div key={metric.label} className="extraction-executive-metric">
                    <strong>{metric.value}</strong>
                    <small>{metric.label}</small>
                  </div>
                ))}
              </div>
            ) : (
              <strong>{block.value}</strong>
            )}
            <p>{block.detail}</p>
          </section>
        ))}
      </div>
    </article>
  )
}

function ExtractionRunItem({ item }) {
  return (
    <li
      className={`extraction-run-item tone-${item.tone} ${item.isCurrent ? 'is-current' : ''} ${item.statusKey === 'pending' ? 'is-pending' : ''}`}
    >
      <div className="extraction-run-item-header">
        <div>
          <strong>{item.entityName}</strong>
          <p>{item.subtitle}</p>
        </div>
        <div className="extraction-run-item-badges">
          <span className={`extraction-run-status tone-${item.tone}`}>{item.statusLabel}</span>
          {item.isCurrent ? <span className="extraction-run-badge current">Atual</span> : null}
        </div>
      </div>

      <div className="extraction-run-metrics">
        <div>
          <span>Requisições</span>
          <strong>{item.requestCountLabel}</strong>
        </div>
        <div>
          <span>Persistências</span>
          <strong>{item.successCountLabel}</strong>
        </div>
        <div>
          <span>Linhas</span>
          <strong>{item.lineProgressLabel}</strong>
        </div>
        <div>
          <span>Faltantes</span>
          <strong>{item.lineRemainingLabel}</strong>
        </div>
        <div>
          <span>Erros</span>
          <strong>{item.errorCountLabel}</strong>
        </div>
        <div>
          <span>ETA</span>
          <strong>{item.etaLabel}</strong>
        </div>
      </div>

      <div className="extraction-run-meta">
        <span>Velocidade: <strong>{item.speedLabel}</strong></span>
        <span>{item.persistenceBreakdownLabel}</span>
        <span>{item.footnote}</span>
      </div>
    </li>
  )
}

function ExtractionHistoryItem({ item, isDownloading, onDownload }) {
  return (
    <li>
      <button
        type="button"
        className={`history-download-item tone-${item.tone}`}
        onClick={() => onDownload(item.executionId)}
        disabled={isDownloading}
      >
        <div className="history-download-main">
          <strong>{`Execução ${item.executionId.slice(0, 8)}`}</strong>
          <p className="history-download-description">
            <span>{`Entidades com sucesso: ${item.entitiesSuccess}`}</span>
            <span>{`interrompidas: ${item.entitiesCancelled}`}</span>
            <span className={item.entitiesError > 0 ? 'history-error-count' : ''}>
              {`com erro: ${item.entitiesError}`}
            </span>
            <span>{`requisições: ${item.requestCount}`}</span>
          </p>
          <span className="history-download-hint">
            {isDownloading ? 'Preparando arquivo...' : 'Clique para baixar o log completo'}
          </span>
        </div>
        <span>{item.time}</span>
      </button>
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


function ExtractionPage({
  overview,
  isSubmitting,
  onStartIncremental,
  onStartReconciliation,
  onStopExtraction,
  onRefreshExecution,
}) {
  const activeExecution = overview?.activeExecution
  const executionRuns = useMemo(() => activeExecution?.runs ?? [], [activeExecution?.runs])
  const recentExecutions = useMemo(() => overview?.recentExecutions ?? [], [overview?.recentExecutions])
  const recentLogs = useMemo(() => activeExecution?.logs ?? [], [activeExecution?.logs])
  const supportedEntities = useMemo(() => overview?.supportedEntities ?? [], [overview?.supportedEntities])
  const isRunning = Boolean(overview?.running)
  const isStopping = Boolean(overview?.stopRequested)
  const [clockMs, setClockMs] = useState(() => Date.now())
  const [downloadingExecutionId, setDownloadingExecutionId] = useState('')
  const runningRun = executionRuns.find((item) => item.status === 'running') ?? null
  const latestRun = executionRuns.at(-1) ?? null
  const currentRun = runningRun ?? latestRun
  const latestLog = recentLogs.at(-1) ?? null
  const processedEntities = executionRuns.filter((item) => item.status !== 'running').length
  const remainingEntities = Math.max(supportedEntities.length - executionRuns.length, 0)

  useEffect(() => {
    if (!isRunning) {
      return undefined
    }

    const intervalId = window.setInterval(() => {
      setClockMs(Date.now())
    }, 10000)

    return () => window.clearInterval(intervalId)
  }, [isRunning])

  const progressMetrics = useMemo(() => {
    const totalEntities = supportedEntities.length
    const startedAtMs = toTimestamp(activeExecution?.startedAt)
    const finishedAtMs = toTimestamp(activeExecution?.finishedAt)
    const referenceNow = finishedAtMs ?? clockMs
    const elapsedSeconds = startedAtMs ? Math.max(0, (referenceNow - startedAtMs) / 1000) : 0
    const completedRuns = executionRuns.filter((item) => item.status !== 'running')
    const completedUnits = completedRuns.length
    const completedRequests = completedRuns
      .map((item) => Number(item.requestCount) || 0)
      .filter((value) => value > 0)
    const benchmarkRequests =
      completedRequests.length > 0
        ? completedRequests.reduce((sum, value) => sum + value, 0) / completedRequests.length
        : 0
    const runningRequests = Number(runningRun?.requestCount) || 0
    const currentRunLineProgress = getRunLineProgress(currentRun)
    const partialRunningProgress =
      runningRun && benchmarkRequests > 0
        ? Math.min(runningRequests / Math.max(benchmarkRequests, 1), 0.94)
        : runningRun
          ? 0.2
          : 0
    const fractionalUnits = Math.min(totalEntities, completedUnits + partialRunningProgress)
    const progressRatio = totalEntities > 0 ? fractionalUnits / totalEntities : 0
    const requestsPerMinute =
      elapsedSeconds > 0 ? ((Number(activeExecution?.requestCount) || 0) / elapsedSeconds) * 60 : 0
    const estimatedTotalSeconds =
      progressRatio > 0.03 && elapsedSeconds > 0 ? elapsedSeconds / progressRatio : null
    const etaSeconds =
      estimatedTotalSeconds && estimatedTotalSeconds > elapsedSeconds
        ? estimatedTotalSeconds - elapsedSeconds
        : null
    const completionPercent = Math.min(100, Math.max(0, Math.round(progressRatio * 100)))
    const estimatedUnits = Math.max(0, Math.min(totalEntities, Math.round(fractionalUnits)))

    return {
      completionPercent,
      elapsedLabel: formatDuration(elapsedSeconds),
      etaLabel: formatEtaLabel(etaSeconds),
      requestsPerMinuteLabel: formatRequestsPerMinute(requestsPerMinute),
      partialUnitsLabel: `${estimatedUnits}/${totalEntities || 0}`,
      benchmarkRequestsLabel:
        benchmarkRequests > 0 ? `${Math.round(benchmarkRequests)} req/entidade` : 'Sem benchmark ainda',
      currentRequestsLabel: `${runningRequests}`,
      currentSuccessLabel: `${Number(currentRun?.successCount) || 0}`,
      currentLineProgressLabel: currentRunLineProgress.lineProgressLabel,
      currentLineRemainingLabel: currentRunLineProgress.lineRemainingLabel,
      currentPersistenceBreakdownLabel: currentRunLineProgress.persistenceBreakdownLabel,
      currentErrorsLabel: `${Number(currentRun?.errorCount) || 0}`,
      progressRatio,
      benchmarkDurationSeconds:
        completedRuns.length > 0
          ? completedRuns
              .map((item) => {
                const startedAtMs = toTimestamp(item.startedAt)
                const finishedAtMs = toTimestamp(item.finishedAt)

                if (!startedAtMs || !finishedAtMs || finishedAtMs <= startedAtMs) {
                  return 0
                }

                return (finishedAtMs - startedAtMs) / 1000
              })
              .filter((value) => value > 0)
              .reduce((sum, value, _, source) => sum + value / source.length, 0)
          : 0,
      benchmarkRequests,
    }
  }, [
    activeExecution?.finishedAt,
    activeExecution?.requestCount,
    activeExecution?.startedAt,
    clockMs,
    currentRun?.errorCount,
    currentRun?.details,
    currentRun?.successCount,
    executionRuns,
    runningRun,
    supportedEntities.length,
  ])

  const entityProgressItems = useMemo(() => {
    const supportedIndexMap = new Map(supportedEntities.map((entityName, index) => [entityName, index]))
    const referenceNowMs = toTimestamp(activeExecution?.finishedAt) ?? clockMs
    const benchmarkDurationSeconds = Number(progressMetrics.benchmarkDurationSeconds) || 0
    const benchmarkRequests = Number(progressMetrics.benchmarkRequests) || 0

    const runningItemEtaSeconds = (() => {
      if (!runningRun) {
        return 0
      }

      const startedAtMs = toTimestamp(runningRun.startedAt)
      const elapsedSeconds = startedAtMs ? Math.max(0, (referenceNowMs - startedAtMs) / 1000) : 0
      const requestCount = Number(runningRun.requestCount) || 0
      const requestsPerMinute = elapsedSeconds > 0 ? (requestCount / elapsedSeconds) * 60 : 0

      if (requestsPerMinute > 0 && benchmarkRequests > requestCount) {
        return ((benchmarkRequests - requestCount) / requestsPerMinute) * 60
      }

      if (benchmarkDurationSeconds > elapsedSeconds) {
        return benchmarkDurationSeconds - elapsedSeconds
      }

      return 0
    })()

    const runItems = executionRuns.map((item) => {
      const startedAtMs = toTimestamp(item.startedAt)
      const finishedAtMs = toTimestamp(item.finishedAt)
      const referenceMs = finishedAtMs ?? referenceNowMs
      const elapsedSeconds = startedAtMs ? Math.max(0, (referenceMs - startedAtMs) / 1000) : 0
      const requestCount = Number(item.requestCount) || 0
      const lineProgress = getRunLineProgress(item)
      const requestsPerMinute = elapsedSeconds > 0 ? (requestCount / elapsedSeconds) * 60 : 0
      let etaSeconds = null

      if (item.status === 'running') {
        if (requestsPerMinute > 0 && benchmarkRequests > requestCount) {
          etaSeconds = ((benchmarkRequests - requestCount) / requestsPerMinute) * 60
        } else if (benchmarkDurationSeconds > elapsedSeconds) {
          etaSeconds = benchmarkDurationSeconds - elapsedSeconds
        }
      }

      return {
        id: item.syncRunId,
        entityName: item.entityName,
        statusKey: item.status === 'running' ? 'running' : 'done',
        statusLabel: labelFromEntityQueueStatus(item.status),
        tone: toneFromEntityQueueStatus(item.status),
        isCurrent: item.status === 'running',
        requestCountLabel: `${requestCount}`,
        successCountLabel: `${Number(item.successCount) || 0}`,
        lineProgressLabel: lineProgress.lineProgressLabel,
        lineRemainingLabel: lineProgress.lineRemainingLabel,
        persistenceBreakdownLabel: lineProgress.persistenceBreakdownLabel,
        errorCountLabel: `${Number(item.errorCount) || 0}`,
        speedLabel:
          item.status === 'running' || item.status === 'success'
            ? formatRequestsPerMinute(requestsPerMinute)
            : item.status === 'pending'
              ? 'Aguardando'
              : requestsPerMinute > 0
                ? formatRequestsPerMinute(requestsPerMinute)
                : 'Sem ritmo',
        etaLabel:
          item.status === 'running'
            ? formatEtaLabel(etaSeconds, 'Calculando')
            : item.status === 'error'
              ? 'Com erro'
              : item.status === 'cancelled'
                ? 'Interrompida'
                : 'Concluída',
        subtitle:
          item.status === 'running'
            ? 'Entidade em processamento agora'
            : `${item.syncMode} • início ${formatDateTime(item.startedAt)}`,
        footnote:
          item.status === 'running'
            ? `Modo ${item.syncMode} • início ${formatDateTime(item.startedAt)}`
            : `Finalizada em ${formatDateTime(item.finishedAt ?? item.startedAt)}`,
        sortIndex: supportedIndexMap.get(item.entityName) ?? Number.MAX_SAFE_INTEGER,
      }
    })

    const seenEntities = new Set(runItems.map((item) => item.entityName))
    const pendingItems = supportedEntities
      .filter((entityName) => !seenEntities.has(entityName))
      .map((entityName, pendingIndex) => {
        const queueAhead = pendingIndex + (runningRun ? 1 : 0)
        const etaSeconds =
          benchmarkDurationSeconds > 0 ? runningItemEtaSeconds + queueAhead * benchmarkDurationSeconds : null

        return {
          id: `pending-${entityName}`,
          entityName,
          statusKey: 'pending',
          statusLabel: labelFromEntityQueueStatus('pending'),
          tone: toneFromEntityQueueStatus('pending'),
          isCurrent: false,
          requestCountLabel: '--',
          successCountLabel: '--',
          lineProgressLabel: '--',
          lineRemainingLabel: '--',
          persistenceBreakdownLabel: 'Aguardando processamento',
          errorCountLabel: '--',
          speedLabel: 'Aguardando',
          etaLabel: formatEtaLabel(etaSeconds, 'Aguardando benchmark'),
          subtitle: 'Entidade ainda não iniciada nesta execução',
          footnote:
            benchmarkDurationSeconds > 0
              ? `Entrada prevista na fila: ${pendingIndex + 1}`
              : 'Sem benchmark local suficiente para estimar',
          sortIndex: supportedIndexMap.get(entityName) ?? Number.MAX_SAFE_INTEGER,
        }
      })

    return [...runItems, ...pendingItems].sort((left, right) => {
      const rankMap = { running: 0, pending: 1, done: 2 }
      const rankDifference = (rankMap[left.statusKey] ?? 9) - (rankMap[right.statusKey] ?? 9)

      if (rankDifference !== 0) {
        return rankDifference
      }

      return left.sortIndex - right.sortIndex
    })
  }, [
    activeExecution?.finishedAt,
    clockMs,
    executionRuns,
    progressMetrics.benchmarkDurationSeconds,
    progressMetrics.benchmarkRequests,
    runningRun,
    supportedEntities,
  ])

  const executionSummaryLog = useMemo(() => {
    if (!activeExecution) {
      return null
    }

    const touchedEntities = [...new Set(recentLogs.map((item) => item.entityName).filter(Boolean))]
    const touchedStages = [...new Set(recentLogs.map((item) => item.stage).filter(Boolean))]
    const errorEvents = recentLogs.filter((item) => item.level === 'ERROR').length
    const currentRunLineProgress = getRunLineProgress(currentRun)
    const latestEventAt = latestLog?.createdAt ?? activeExecution.finishedAt ?? activeExecution.startedAt
    const executionTone = isRunning
      ? 'accent'
      : (activeExecution.entitiesError ?? 0) > 0
        ? 'danger'
        : (activeExecution.entitiesCancelled ?? 0) > 0
          ? 'warning'
          : 'success'
    const executionStatus = isRunning
      ? 'Em andamento'
      : (activeExecution.entitiesError ?? 0) > 0
        ? 'Concluída com erro'
        : (activeExecution.entitiesCancelled ?? 0) > 0
          ? 'Interrompida'
          : 'Concluída'

    return {
      id: activeExecution.executionId,
      title: `Execução ${activeExecution.executionId.slice(0, 8)} • ${executionStatus}`,
      time: formatDateTime(latestEventAt),
      tone: executionTone,
      statusLabel: executionStatus,
      blocks: [
        {
          label: 'Status',
          value: executionStatus,
          detail: `${remainingEntities} entidades restantes nesta execução`,
        },
        {
          label: 'Tipo',
          value: labelFromExecutionType(activeExecution.executionType),
          detail: 'Modo operacional da execução ativa ou mais recente',
        },
        {
          label: 'Período',
          value: `${formatDateTime(activeExecution.startedAt)} até ${formatDateTime(activeExecution.finishedAt)}`,
          detail: `Tempo total ${activeExecution.durationLabel ?? formatDurationHuman(activeExecution.durationSeconds)}`,
        },
        {
          label: 'Entidades',
          value: `${activeExecution.entitiesSuccess ?? 0} ok • ${activeExecution.entitiesError ?? 0} erro • ${activeExecution.entitiesCancelled ?? 0} interrompidas`,
          detail: `${activeExecution.entityTotal ?? supportedEntities.length ?? 0} entidades previstas no ciclo`,
        },
        {
          label: 'Volume',
          metrics: [
            { label: 'Requisições', value: activeExecution.requestCount ?? 0 },
            { label: 'Persistências', value: activeExecution.successCount ?? 0 },
            { label: 'Linhas', value: currentRunLineProgress.lineProgressLabel },
            { label: 'Faltantes', value: currentRunLineProgress.lineRemainingLabel },
            { label: 'Erros', value: activeExecution.errorCount ?? 0 },
          ],
          detail: currentRun
            ? `${currentRun.entityName} • ${currentRunLineProgress.persistenceBreakdownLabel}`
            : 'Resumo operacional agregado da execução',
          variant: 'volume',
        },
        {
          label: 'Cobertura do log',
          value: `${recentLogs.length} eventos • ${touchedEntities.length} entidades • ${touchedStages.length} etapas`,
          detail: `${errorEvents} eventos de erro identificados na trilha`,
          fullWidth: true,
        },
        {
          label: 'Último evento',
          value: latestLog ? `${latestLog.entityName} / ${latestLog.stage}` : 'Sem eventos detalhados',
          detail: latestLog?.message ?? 'Nenhuma mensagem detalhada disponível para esta execução.',
          featured: true,
        },
      ],
    }
  }, [
    activeExecution,
    currentRun,
    isRunning,
    latestLog,
    recentLogs,
    remainingEntities,
    supportedEntities.length,
  ])

  const cards = [
    {
      label: 'Entidades',
      value: String(supportedEntities.length).padStart(2, '0'),
      helper: 'Cobertura pública configurada',
    },
    {
      label: 'Execução ativa',
      value: isRunning ? 'Sim' : 'Não',
      helper: isStopping
        ? 'Parada solicitada, aguardando encerramento seguro'
        : isRunning
                          ? `${labelFromExecutionType(activeExecution?.executionType)} em andamento`
          : 'Nenhuma rotina ativa agora',
    },
    {
      label: 'Andamento',
      value: `${processedEntities}/${supportedEntities.length || 0}`,
      helper: currentRun
        ? `${currentRun.entityName} • ${labelFromExtractionStatus(currentRun.status)} • linhas ${getRunLineProgress(currentRun).lineProgressLabel}`
        : 'Aguardando primeira execução',
    },
    {
      label: 'Último evento',
      value: latestLog ? latestLog.stage : '--',
      helper: latestLog ? `${latestLog.entityName} em ${formatDateTime(latestLog.createdAt)}` : 'Sem eventos recentes',
    },
  ]

  const handleDownloadExecutionLog = useCallback(async (executionId) => {
    setDownloadingExecutionId(executionId)

    try {
      const payload = await apiRequest(`/extraction/executions/${executionId}`)
      const content = buildExtractionExecutionLogText(payload)
      const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
      const downloadUrl = window.URL.createObjectURL(blob)
      const link = window.document.createElement('a')
      link.href = downloadUrl
      link.download = `albertina-extracao-${executionId}.txt`
      window.document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(downloadUrl)
    } catch (error) {
      window.alert(
        error instanceof ApiError
          ? error.message
          : 'Não foi possível baixar o log desta execução.',
      )
    } finally {
      setDownloadingExecutionId('')
    }
  }, [])

  return (
    <section className="page-stack extraction-page">
      <section className="panel panel-glow extraction-hero-panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">Extração</span>
          </div>
          <div className="toolbar extraction-actions">
            <button type="button" className="ghost-button" onClick={onRefreshExecution} disabled={isSubmitting}>
              Atualizar
            </button>
            {isRunning ? (
              <button
                type="button"
                className="primary-button"
                onClick={onStopExtraction}
                disabled={isSubmitting}
              >
                {isStopping ? 'Parando extração...' : 'Parar extração'}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="primary-button"
                  onClick={onStartIncremental}
                  disabled={isSubmitting}
                >
                  Iniciar incremental
                </button>
                <button
                  type="button"
                  className="ghost-button success"
                  onClick={onStartReconciliation}
                  disabled={isSubmitting}
                >
                  Iniciar conciliação
                </button>
              </>
            )}
          </div>
        </div>

        <div className="stats-row stats-row-compact extraction-hero-stats">
          {cards.map((card) => (
            <StatCard key={card.label} {...card} />
          ))}
        </div>
      </section>

      <section className="page-grid extraction-grid">
        <article className="panel extraction-log-panel">
          <div className="panel-header compact extraction-log-header">
            <div>
              <span className="eyebrow">Logs</span>
            </div>
          </div>
          {executionSummaryLog ? (
            <div className="extraction-log-content">
              {activeExecution ? (
                <div className="extraction-progress-shell extraction-log-progress-shell">
                  <div className="extraction-progress-summary">
                    <div>
                      <span className="extraction-progress-label">Progresso parcial</span>
                      <strong>{progressMetrics.completionPercent}%</strong>
                      <p>{progressMetrics.partialUnitsLabel} entidades estimadas</p>
                    </div>
                    <div>
                      <span className="extraction-progress-label">Tempo decorrido</span>
                      <strong>{progressMetrics.elapsedLabel}</strong>
                      <p>{progressMetrics.requestsPerMinuteLabel}</p>
                    </div>
                    <div>
                      <span className="extraction-progress-label">Previsão restante</span>
                      <strong>{progressMetrics.etaLabel}</strong>
                      <p>{progressMetrics.benchmarkRequestsLabel}</p>
                    </div>
                  </div>

                  <div
                    className="extraction-progress-bar"
                    role="progressbar"
                    aria-valuemin="0"
                    aria-valuemax="100"
                    aria-valuenow={progressMetrics.completionPercent}
                    aria-label="Progresso estimado da extração"
                  >
                    <div
                      className="extraction-progress-fill"
                      style={{ width: `${Math.max(progressMetrics.completionPercent, isRunning ? 4 : 0)}%` }}
                    />
                  </div>

                  <div className="extraction-progress-meta">
                    <span>Entidade atual: <strong>{currentRun?.entityName ?? 'Aguardando'}</strong></span>
                    <span>Requisições atuais: <strong>{progressMetrics.currentRequestsLabel}</strong></span>
                    <span>Persistências atuais: <strong>{progressMetrics.currentSuccessLabel}</strong></span>
                    <span>Linhas atuais: <strong>{progressMetrics.currentLineProgressLabel}</strong></span>
                    <span>Linhas faltantes: <strong>{progressMetrics.currentLineRemainingLabel}</strong></span>
                    <span>Inserção atual: <strong>{progressMetrics.currentPersistenceBreakdownLabel}</strong></span>
                    <span>Erros atuais: <strong>{progressMetrics.currentErrorsLabel}</strong></span>
                  </div>
                </div>
              ) : null}
              <div className="extraction-log-list">
                <ExtractionExecutionSummaryCard summary={executionSummaryLog} />
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <strong>Nenhum log disponível</strong>
              <p>Os eventos de execução serão exibidos assim que a extração começar.</p>
            </div>
          )}
        </article>

        <article className="panel extraction-progress-panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Andamento por entidade</span>
            </div>
          </div>
          <div className="extraction-progress-content">
            <div className="extraction-run-list-shell">
              {entityProgressItems.length > 0 ? (
                <ul className="activity-list audit-list extraction-run-list">
                  {entityProgressItems.map((item) => (
                    <ExtractionRunItem
                      key={item.id}
                      item={item}
                    />
                  ))}
                </ul>
              ) : (
                <div className="empty-state extraction-progress-empty">
                  <strong>Nenhuma entidade em execução</strong>
                  <p>O andamento detalhado aparecerá aqui assim que a extração começar.</p>
                </div>
              )}
            </div>
          </div>
        </article>

        <article className="panel extraction-history-panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Histórico</span>
            </div>
          </div>
          {recentExecutions.length > 0 ? (
            <ul className="activity-list audit-list">
              {recentExecutions.map((item) => (
                <ExtractionHistoryItem
                  key={item.executionId}
                  item={{
                    id: item.executionId,
                    executionId: item.executionId,
                    executionType: item.executionType,
                    entitiesSuccess: item.entitiesSuccess ?? 0,
                    entitiesCancelled: item.entitiesCancelled ?? 0,
                    entitiesError: item.entitiesError ?? 0,
                    requestCount: item.requestCount ?? 0,
                    time: formatDateTime(item.startedAt),
                    tone:
                      (item.entitiesError ?? 0) > 0
                        ? 'danger'
                        : (item.entitiesCancelled ?? 0) > 0
                          ? 'warning'
                          : 'success',
                  }}
                  isDownloading={downloadingExecutionId === item.executionId}
                  onDownload={handleDownloadExecutionLog}
                />
              ))}
            </ul>
          ) : (
            <div className="empty-state">
              <strong>Nenhuma execução registrada</strong>
              <p>O histórico de sincronização aparecerá aqui após a primeira execução.</p>
            </div>
          )}
        </article>

        <article className="panel extraction-coverage-panel">
          <div className="panel-header compact">
            <div>
              <span className="eyebrow">Cobertura</span>
            </div>
          </div>
          {supportedEntities.length > 0 ? (
            <div className="detail-list extraction-entity-list">
              {supportedEntities.map((entityName) => (
                <li key={entityName}>{entityName}</li>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <strong>Nenhuma entidade configurada</strong>
              <p>Verifique a configuração da extração no backend.</p>
            </div>
          )}
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


function App() {
  const [activePage, setActivePage] = useState(() => getPageFromPath(window.location.pathname))
  const [currentUser, setCurrentUser] = useState(null)
  const [users, setUsers] = useState([])
  const [activity, setActivity] = useState([])
  const [connectionsOverview, setConnectionsOverview] = useState(null)
  const [extractionOverview, setExtractionOverview] = useState(null)
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
    const [usersData, auditData, overviewData, extractionData] = await Promise.all([
      apiRequest('/users'),
      apiRequest('/audit'),
      apiRequest('/connections/overview'),
      apiRequest('/extraction/overview'),
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
    setExtractionOverview(extractionData)
    clearPageFeedback()
  }, [])

  useEffect(() => {
    document.title = 'Albertina'
  }, [])

  useEffect(() => {
    const handlePopState = () => {
      if (window.location.pathname === LEGACY_ROUTES.audit) {
        window.history.replaceState({}, '', ROUTES.extraction)
        setActivePage('extraction')
        return
      }
      setActivePage(getPageFromPath(window.location.pathname))
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    if (window.location.pathname === LEGACY_ROUTES.olist) {
      window.history.replaceState({}, '', ROUTES.connections)
    }
    if (window.location.pathname === LEGACY_ROUTES.audit) {
      window.history.replaceState({}, '', ROUTES.extraction)
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
        } else if (window.location.pathname === LEGACY_ROUTES.audit) {
          navigate(ROUTES.extraction, true)
        }
        await hydrateAuthenticatedData()
      } catch {
        clearStoredToken()
        setCurrentUser(null)
        setUsers([])
        setActivity([])
        setConnectionsOverview(null)
        setExtractionOverview(null)
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
      setExtractionOverview(null)
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

  useEffect(() => {
    if (!isAuthenticated || activePage !== 'extraction') {
      return
    }

    if (!extractionOverview?.running && !extractionOverview?.activeExecutionId) {
      return
    }

    const intervalId = window.setInterval(async () => {
      try {
        const overview = await apiRequest('/extraction/overview')
        setExtractionOverview(overview)
      } catch {
        // Mantem a ultima visao renderizada enquanto a API nao responde.
      }
    }, 10000)

    return () => window.clearInterval(intervalId)
  }, [
    activePage,
    extractionOverview?.activeExecutionId,
    extractionOverview?.running,
    extractionOverview?.stopRequested,
    isAuthenticated,
  ])

  async function handleRefreshExtraction() {
    setIsSubmitting(true)
    try {
      const overview = await apiRequest('/extraction/overview')
      // #region debug-point D:manual-refresh
      reportExtractionDebug('D', 'frontend/src/App.jsx:handleRefreshExtraction', '[DEBUG] manual overview refresh resolved', {
        running: Boolean(overview?.running),
        activeExecutionId: overview?.activeExecutionId ?? null,
        hasActiveExecution: Boolean(overview?.activeExecution),
      })
      // #endregion
      setExtractionOverview(overview)
      showPageFeedback('Status da extração atualizado.', 'success')
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível atualizar o status da extração.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleStartExtraction(executionType) {
    setIsSubmitting(true)
    try {
      // #region debug-point E:start-click
      reportExtractionDebug('E', 'frontend/src/App.jsx:handleStartExtraction', '[DEBUG] start button clicked', {
        executionType,
        previousRunning: Boolean(extractionOverview?.running),
        previousActiveExecutionId: extractionOverview?.activeExecutionId ?? null,
      })
      // #endregion
      const response = await apiRequest('/extraction/run', {
        method: 'POST',
        body: JSON.stringify({ executionType }),
      })
      // #region debug-point E:start-response
      reportExtractionDebug('E', 'frontend/src/App.jsx:handleStartExtraction', '[DEBUG] run endpoint resolved', {
        executionType,
        responseStatus: response?.status ?? null,
        responseExecutionId: response?.executionId ?? null,
        responseDetail: response?.detail ?? null,
      })
      // #endregion
      const overview = await apiRequest('/extraction/overview')
      // #region debug-point E:overview-after-start
      reportExtractionDebug('E', 'frontend/src/App.jsx:handleStartExtraction', '[DEBUG] overview fetched after start', {
        executionType,
        running: Boolean(overview?.running),
        activeExecutionId: overview?.activeExecutionId ?? null,
        hasActiveExecution: Boolean(overview?.activeExecution),
        activeExecutionType: overview?.activeExecution?.executionType ?? null,
      })
      // #endregion
      setExtractionOverview(overview)
      showPageFeedback(
        response.detail ?? 'Extração iniciada com sucesso.',
        response.status === 'started' ? 'success' : 'neutral',
      )
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível iniciar a extração agora.',
        'danger',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleStopExtraction() {
    setIsSubmitting(true)
    try {
      const response = await apiRequest('/extraction/stop', { method: 'POST' })
      const overview = await apiRequest('/extraction/overview')
      setExtractionOverview(overview)
      showPageFeedback(
        response.detail ?? 'Parada da extração solicitada com sucesso.',
        response.status === 'stopping' ? 'success' : 'neutral',
      )
    } catch (error) {
      showPageFeedback(
        error instanceof ApiError ? error.message : 'Não foi possível solicitar a parada da extração agora.',
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

    if (activePage === 'extraction') {
      return (
        <ExtractionPage
          overview={extractionOverview}
          isSubmitting={isSubmitting}
          onStartIncremental={() => handleStartExtraction('incremental')}
          onStartReconciliation={() => handleStartExtraction('reconciliation')}
          onStopExtraction={handleStopExtraction}
          onRefreshExecution={handleRefreshExtraction}
        />
      )
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
