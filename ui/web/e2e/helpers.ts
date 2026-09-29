/** Shared helpers: the environment global setup created, the real CLI, and state readers. */
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, type Locator, type Page } from '@playwright/test'

export const env = {
  get base() {
    return process.env.AUI_BASE!
  },
  get token() {
    return process.env.AUI_TOKEN!
  },
  get workspace() {
    return process.env.AUI_WORKSPACE!
  },
  get config() {
    return process.env.AUI_CONFIG!
  },
  get tmux() {
    return process.env.AUI_TMUX!
  },
  get prefix() {
    return process.env.AUI_PREFIX!
  },
  get ui() {
    return process.env.AUI_UI!
  },
}

function childEnvironment(extra: Record<string, string> = {}) {
  const environment: Record<string, string> = { ...(process.env as Record<string, string>), TMUX_TMPDIR: env.tmux, ...extra }
  delete environment.TMUX
  return environment
}

/** Run the real alfred CLI against the test workspace, as an agent or operator would. */
export function alfred(args: string[], extra: Record<string, string> = {}): { status: number; output: string } {
  try {
    const output = execFileSync(join(env.ui, '.venv', 'bin', 'alfred'), ['--config', env.config, ...args], {
      env: childEnvironment(extra),
      encoding: 'utf8',
    })
    return { status: 0, output }
  } catch (error) {
    const failure = error as { status: number; stdout?: string; stderr?: string }
    return { status: failure.status ?? 1, output: `${failure.stdout ?? ''}${failure.stderr ?? ''}` }
  }
}

/** Run tmux on the test's private socket. */
export function tmux(args: string[]): string {
  return execFileSync('tmux', args, { env: childEnvironment(), encoding: 'utf8' })
}

export function git(args: string[], cwd: string): string {
  return execFileSync('git', args, { cwd, encoding: 'utf8' })
}

type Task = { task_number: number; status: string; lifecycle_phase: string; planning_state: string; assigned_agent_alias: string }

export function tasks(): Task[] {
  return JSON.parse(readFileSync(join(env.workspace, '.alfred', 'state', 'tasks.json'), 'utf8')).tasks
}

export function task(number: number): Task {
  const found = tasks().find((item) => item.task_number === number)
  if (!found) throw new Error(`Task ${number} not found`)
  return found
}

export function events(number: number): { event_type: string; actor: string; details: string }[] {
  const all = JSON.parse(readFileSync(join(env.workspace, '.alfred', 'state', 'events.json'), 'utf8')).events
  return all.filter((item: { task_number: number }) => item.task_number === number)
}

export function runs(number: number): { run_status: string; phase: string; session_name: string }[] {
  const all = JSON.parse(readFileSync(join(env.workspace, '.alfred', 'state', 'runs.json'), 'utf8')).runs
  return all.filter((item: { task_number: number }) => item.task_number === number)
}

/** Call the UI server's API directly (used only to set up preconditions quickly). */
export async function api<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${env.base}/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Alfred-Token': env.token },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(`${method} ${path}: ${JSON.stringify(data)}`)
  return data as T
}

export async function createTask(fields: Record<string, unknown>) {
  await api('POST', '/tasks', { assign: 'fake', repos: ['app'], ...fields })
}

export async function signIn(page: Page) {
  await page.goto(`${env.base}/?token=${env.token}`)
  await expect(page.locator('.shell')).toBeVisible()
  await expect(page.locator('.topbar')).toContainText('Live')
}

export async function openTask(page: Page, number: number, tab = 'overview'): Promise<Locator> {
  await page.goto(`${env.base}/?task=${number}&tab=${tab}`)
  const panel = page.locator(`[data-task-panel="${number}"]`)
  await expect(panel).toBeVisible()
  return panel
}

/** Open an action from the task's quick buttons or its All actions menu, then return the dialog. */
export async function openAction(page: Page, panel: Locator, id: string): Promise<Locator> {
  const quick = panel.locator(`[data-action="${id}"]`)
  if (await quick.count()) await quick.first().click()
  else {
    await panel.locator('[data-action="more"]').click()
    await panel.locator(`[data-menu-action="${id}"]`).click()
  }
  // Action dialogs use the "dialog" variant; the task drawer underneath uses "drawer".
  const dialog = page.locator('dialog.modal.dialog[open]')
  await expect(dialog).toBeVisible()
  return dialog
}

export async function submit(dialog: Locator) {
  await dialog.getByTestId('action-submit').click()
  await expect(dialog).toBeHidden()
}

export async function tab(panel: Locator, key: string) {
  await panel.locator(`[role=tab][data-tab="${key}"]`).click()
}

export function terminalText(scope: Locator): Locator {
  return scope.getByTestId('terminal').locator('.xterm-rows')
}
