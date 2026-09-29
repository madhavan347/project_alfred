/**
 * The background machinery through the Operations page: the coordinator as a background session,
 * the learner agent, Markdown tracker drift and reconciliation, and the raw files behind it all.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { alfred, api, createTask, env, signIn, tmux } from './helpers'

test('the background coordinator turns a completion into a notification on its own', async ({ page }) => {
  await signIn(page)
  await page.goto(`${env.base}/operations`)
  const coordinator = page.getByTestId('coordinator')
  await coordinator.getByRole('button', { name: 'Start in background' }).click()
  await expect(coordinator).toContainText('running')
  await expect(page.locator('.topbar [title^="Coordinator running"]')).toBeVisible()
  expect(tmux(['list-sessions', '-F', '#{session_name}'])).toContain(`${env.prefix}-coordinator`)

  // An agent completes a task from its own shell; the coordinator notices within its 5 s poll.
  await createTask({ task: 51, title: 'Handled by the coordinator', description: 'Completes at once', branch: 'feature/coord-51' })
  await api('POST', '/runs/trigger', { tasks: [51] })
  await expect.poll(() => alfred(['run', 'list', '--status', 'completed']).output, { timeout: 45_000 }).toContain('task=51')
  await expect(page.locator('[data-call="review"]')).toBeAttached({ timeout: 20_000 })
  await expect(coordinator).toContainText('0 pending')

  await coordinator.getByRole('button', { name: 'Stop' }).click()
  await expect(coordinator).toContainText('stopped')
})

test('the learner starts in its own session and stops', async ({ page }) => {
  await signIn(page)
  await page.goto(`${env.base}/operations`)
  const learner = page.getByTestId('learner')
  await learner.getByLabel('Learner agent').selectOption('fake')
  await learner.getByRole('button', { name: 'Start learner' }).click()
  await expect(learner).toContainText('running with fake')
  await expect(learner.getByTestId('screen-preview')).toContainText('Fake learner ready')
  await expect(learner).toContainText('Learner prompt')
  await learner.getByRole('button', { name: 'Stop' }).click()
  await expect(learner).toContainText('stopped')
  expect(alfred(['learner', 'status']).output).toContain('Learner: stopped')
})

test('tracker drift is detected and reconciled', async ({ page }) => {
  await createTask({ task: 52, title: 'Tracked task', description: 'Tracker rows', branch: 'feature/tracked-52' })
  const canonical = join(env.workspace, 'tracking', 'tasks.md')
  const withoutRow = readFileSync(canonical, 'utf8')
    .split('\n')
    .filter((line) => !/^\|\s*52\s*\|/.test(line))
    .join('\n')
  writeFileSync(canonical, withoutRow)

  await signIn(page)
  await page.goto(`${env.base}/operations?section=tracker`)
  await expect(page.locator('.issues')).toContainText('Task 52 is missing from the canonical tracker')
  await page.getByRole('button', { name: 'Apply to every task' }).click()
  await expect(page.getByText('in sync')).toBeVisible()
  expect(readFileSync(canonical, 'utf8')).toMatch(/^\|\s*52\s*\|/m)
  expect(alfred(['sync', 'validate']).output).toContain('Sync validation passed')
})

test('completion handoffs and raw state are readable', async ({ page }) => {
  await signIn(page)
  await page.goto(`${env.base}/operations?section=completions`)
  await expect(page.getByText('Processed into notifications')).toBeVisible()
  await expect(page.locator('details.entry').first()).toContainText('Task #')

  await page.goto(`${env.base}/operations?section=state`)
  await page.getByLabel('Document').selectOption('runs')
  await expect(page.locator('.json pre')).toContainText('"schema_version": 1')
  await expect(page.locator('.json pre')).toContainText('"runs"')
})
