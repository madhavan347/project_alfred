/** Time, size, and text formatting helpers. */

import { ref } from 'vue'

/** A clock that ticks every few seconds so relative times stay current. */
export const now = ref(Date.now())
let started = false

export function startClock(): void {
  if (started) return
  started = true
  window.setInterval(() => {
    now.value = Date.now()
  }, 2000)
}

/** Milliseconds to add to the browser clock to match the server clock. */
export const serverSkew = ref(0)

export function parseTime(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'number') return value < 1e12 ? value * 1000 : value
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? null : parsed
}

/** Human relative time such as "just now", "4 min ago", or "3 days ago". */
export function relative(value: string | number | null | undefined, reference = now.value): string {
  const time = parseTime(value)
  if (time === null) return '—'
  const seconds = Math.round((reference + serverSkew.value - time) / 1000)
  const future = seconds < 0
  const span = Math.abs(seconds)
  let text: string
  if (span < 10) return future ? 'in a moment' : 'just now'
  if (span < 60) text = `${span} s`
  else if (span < 3600) text = `${Math.round(span / 60)} min`
  else if (span < 86400) text = `${Math.round(span / 3600)} h`
  else if (span < 86400 * 30) {
    const days = Math.round(span / 86400)
    text = `${days} day${days === 1 ? '' : 's'}`
  } else return absolute(time)
  return future ? `in ${text}` : `${text} ago`
}

/** Absolute local date and time. */
export function absolute(value: string | number | null | undefined): string {
  const time = parseTime(value)
  if (time === null) return '—'
  return new Date(time).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/** Short local time of day, for timelines. */
export function clockTime(value: string | number | null | undefined): string {
  const time = parseTime(value)
  if (time === null) return '—'
  return new Date(time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

/** Duration between two times, or from a start until now. */
export function duration(
  start: string | number | null | undefined,
  end?: string | number | null,
  reference = now.value,
): string {
  const from = parseTime(start)
  if (from === null) return '—'
  const to = parseTime(end ?? null) ?? reference + serverSkew.value
  return humanSpan(Math.max(0, (to - from) / 1000))
}

export function humanSpan(totalSeconds: number): string {
  const seconds = Math.round(totalSeconds)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours}h ${minutes % 60}m`
  return `${Math.floor(hours / 24)}d ${hours % 24}h`
}

export function bytes(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count} ${count === 1 ? one : many}`
}

/** "AGENT_PLAN_COMPLETED" → "Agent plan completed". */
export function humanize(value: string): string {
  const text = value.replace(/[_-]+/g, ' ').trim().toLowerCase()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function shortId(value: string): string {
  return value.slice(0, 8)
}
