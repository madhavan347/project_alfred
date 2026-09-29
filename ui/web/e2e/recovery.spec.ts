/**
 * Recovery paths: a failed attempt reopened, a session that dies, a dispatch queued while tmux was
 * missing, and a stop that must not silently discard uncommitted work.
 */
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { alfred, api, createTask, env, events, openAction, openTask, runs, signIn, submit, tab, task, tmux } from './helpers'

test('a failed attempt is reported, then reopened and completed in the same session', async ({ page }) => {
  await createTask({ task: 31, title: 'Flaky fix', description: 'Fails first. [fake:fail-once]', branch: 'fix/flaky-31' })
  await signIn(page)
  const panel = await openTask(page, 31)
  await submit(await openAction(page, panel, 'trigger'))

  await expect.poll(() => runs(31).at(-1)?.run_status, { timeout: 45_000 }).toBe('failed')
  await expect(panel.locator('.facts')).toContainText('In progress')
  await panel.getByRole('button', { name: 'Process now' }).click()
  await expect(panel).toContainText('Run failed')
  await expect(page.locator('[data-call="failed"]')).toBeAttached()

  // Reopen starts a new attempt; the existing session receives the execution prompt.
  const reopen = await openAction(page, panel, 'reopen')
  await expect(reopen.locator('.command')).toContainText('alfred run reopen --task 31')
  await submit(reopen)
  await expect(panel.locator('.facts')).toContainText('In review', { timeout: 45_000 })
  const attempts = runs(31)
  expect(attempts.map((run) => run.run_status)).toEqual(['failed', 'completed'])
  expect(new Set(attempts.map((run) => run.session_name)).size).toBe(1)
})

test('a dead session raises one alert and the run can be stopped', async ({ page }) => {
  await createTask({ task: 32, title: 'Crashing agent', description: 'Waits for go. [fake:wait]', branch: 'feature/crash-32' })
  await signIn(page)
  const panel = await openTask(page, 32)
  await submit(await openAction(page, panel, 'trigger'))
  const session = `${env.prefix}-32-fake`
  await expect.poll(() => runs(32).at(-1)?.session_name).toBe(session)
  await expect(panel.locator('.facts')).toContainText('In progress', { timeout: 30_000 })

  // The session disappears behind Alfred's back.
  tmux(['kill-session', '-t', `=${session}`])
  const first = await api<{ dead_sessions: number }>('POST', '/coordinator/once')
  expect(first.dead_sessions).toBe(1)
  const second = await api<{ dead_sessions: number }>('POST', '/coordinator/once')
  expect(second.dead_sessions).toBe(0)
  await expect(page.locator('[data-call="session"]')).toBeAttached()

  await tab(panel, 'terminal')
  await expect(panel).toContainText('No live session')

  const stop = await openAction(page, panel, 'stop')
  await stop.getByLabel('Reason').fill('Session crashed')
  await submit(stop)
  await expect(panel.locator('.facts')).toContainText('Pending')
  expect(runs(32).at(-1)?.run_status).toBe('stopped')
  expect(events(32).map((item) => item.event_type)).toContain('RUN_STOPPED')
})

test('a dispatch queued without tmux is dispatched again from the UI', async ({ page }) => {
  await createTask({ task: 33, title: 'Queued without tmux', description: 'Waits for go. [fake:wait]', branch: 'feature/queue-33' })
  // An operator triggers from a shell where tmux is not on PATH.
  const queued = alfred(['run', 'trigger', '--tasks', '33'], { PATH: '/usr/bin:/bin' })
  expect(queued.output).toContain('Task 33: queued')
  expect(task(33).status).toBe('Queued')

  await signIn(page)
  const card = page.locator('[data-column="Queued"] [data-task="33"]')
  await expect(card).toBeVisible()
  await card.click()
  const panel = page.locator('[data-task-panel="33"]')
  await tab(panel, 'terminal')
  await expect(panel).toContainText('Queued: no session was started')
  await panel.locator('.terminal-tab').getByRole('button', { name: 'Dispatch again' }).click()
  await submit(page.locator('dialog.modal.dialog[open]'))
  await expect(panel.getByTestId('terminal').locator('.xterm-rows')).toContainText('Type go and press Enter', { timeout: 45_000 })
  expect(runs(33).map((run) => run.run_status)).toEqual(['stopped', 'running'])
  expect(runs(33)[0]).toMatchObject({ phase: 'execution' })
})

test('stopping with cleanup refuses to discard uncommitted work unless forced', async ({ page }) => {
  await createTask({ task: 34, title: 'Dirty stop', description: 'Leaves a file. [fake:wait]', branch: 'feature/dirty-34' })
  await signIn(page)
  const panel = await openTask(page, 34)
  await submit(await openAction(page, panel, 'trigger'))
  const worktree = join(env.workspace, '.alfred', 'worktrees', 'task-34', 'app')
  await expect.poll(() => existsSync(join(worktree, 'fake-agent-task-34.txt')), { timeout: 45_000 }).toBe(true)

  const stop = await openAction(page, panel, 'stop')
  await stop.getByText('Also remove the task’s worktrees').click()
  await stop.getByTestId('action-submit').click()
  await expect(stop.locator('.error')).toContainText('uncommitted changes: app')
  expect(existsSync(worktree)).toBe(true)
  expect(runs(34).at(-1)?.run_status).toBe('running')

  await stop.getByText('Discard uncommitted changes (force)').click()
  await expect(stop.locator('.warning')).toContainText('Uncommitted changes in the worktrees will be lost.')
  await expect(stop.locator('.command')).toContainText('alfred run stop --task 34 --cleanup yes --force')
  await submit(stop)
  await expect(panel.locator('.facts')).toContainText('Pending')
  expect(existsSync(worktree)).toBe(false)
  expect(runs(34).at(-1)?.run_status).toBe('stopped')
})
