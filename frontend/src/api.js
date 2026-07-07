const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'
const TOKEN_KEY = 'albertina.auth.token'


class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}


export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY)
}


export function setStoredToken(token) {
  window.localStorage.setItem(TOKEN_KEY, token)
}


export function clearStoredToken() {
  window.localStorage.removeItem(TOKEN_KEY)
}


export async function apiRequest(path, options = {}) {
  const token = getStoredToken()
  const headers = new Headers(options.headers ?? {})

  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  const data = await response
    .json()
    .catch(() => ({ detail: 'A API retornou uma resposta inválida.' }))

  if (!response.ok) {
    const message =
      typeof data?.detail === 'string'
        ? data.detail
        : typeof data?.detail?.message === 'string'
          ? data.detail.message
        : 'Não foi possível concluir a operação.'
    throw new ApiError(message, response.status)
  }

  return data
}


export { API_BASE_URL, ApiError }
