/** Small JSON client for the Alfred UI server. */

import { ref } from 'vue'
import type { ActionResult } from './types'

/** True once the server has rejected a request for a missing or wrong access token. */
export const signInRequired = ref(false)

export class ApiError extends Error {
  readonly status: number
  readonly kind: string

  constructor(message: string, status: number, kind = '') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.kind = kind
  }
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT'

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? { Accept: 'application/json' } : {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('The Alfred UI server is not reachable. Is alfred-ui still running?', 0)
  }
  const text = await response.text()
  let data: unknown = undefined
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { error: text }
    }
  }
  if (response.status === 401) {
    signInRequired.value = true
  }
  if (!response.ok) {
    const payload = (data ?? {}) as { error?: string; kind?: string }
    throw new ApiError(payload.error || response.statusText || 'Request failed', response.status, payload.kind)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T = ActionResult>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  patch: <T = ActionResult>(path: string, body: unknown) => request<T>('PATCH', path, body),
  put: <T = ActionResult>(path: string, body: unknown) => request<T>('PUT', path, body),
}

/** Build a query string, skipping empty values. */
export function query(values: Record<string, string | number | boolean | null | undefined>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

/** Absolute WebSocket URL for an API path on the current origin. */
export function socketUrl(path: string): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${window.location.host}/api${path}`
}
