/**
 * The board is live: changes made from a shell or by agents appear without reloading, cards can be
 * dragged to the action a column stands for, and every event reaches the feed.
 */
import { expect, test } from '@playwright/test'
import { alfred, api, createTask, env, events, runs, signIn, task, tmux } from './helpers'

test('changes made with the CLI appear on the board and in the feed without reloading', async ({ page }) => {
  await signIn(page)
  const created = alfred([
    'task', 'create', '--task', '41', '--title', 'Created from a shell', '--description', 'Made with the CLI',
    '--branch', 'feature/shell-41', '--repos', 'app', '--assign', 'fake', '--priority', 'P0',
  ])
  expect(created.status).toBe(0)
  const card = page.locator('[data-column="Pending"] [data-task="41"]')
  await expect(card).toBeVisible({ timeout: 10_000 })
  await expect(card).toContainText('P0')

  alfred(['task', 'progress', '--task', '41', '--note', 'Progress written from a shell', '--actor', 'agent:fake'])
  const moved = page.locator('[data-column="In Progress"] [data-task="41"]')
  await expect(moved).toContainText('Progress written from a shell', { timeout: 10_000 })

  await page.goto(`${env.base}/feed`)
  const feed = page.getByTestId('feed')
  await expect(feed.locator('[data-event-type="PROGRESS"]').first()).toContainText('Progress written from a shell')
  alfred(['task', 'block', '--task', '41', '--reason', 'Blocked from a shell'])
  await expect(feed.locator('[data-event-type="STATUS_BLOCKED"]').first()).toContainText('Blocked from a shell', { timeout: 10_000 })
})

test('dragging a card opens the action its column stands for', async ({ page }) => {
  await createTask({ task: 42, title: 'Drag me', description: 'Board interaction', branch: 'feature/drag-42' })
  await signIn(page)
  const card = page.locator('[data-task="42"]')
  await expect(card).toBeVisible()

  await card.dragTo(page.locator('[data-column="Blocked"]'))
  const dialog = page.locator('dialog.modal.dialog[open]')
  await expect(dialog).toContainText('Block task: #42')
  await dialog.getByLabel('Reason').fill('Waiting for the design review')
  await dialog.getByTestId('action-submit').click()
  await expect(page.locator('[data-column="Blocked"] [data-task="42"]')).toBeVisible()
  expect(task(42).status).toBe('Blocked')

  // A move Alfred does not allow explains itself instead of doing anything.
  await page.locator('[data-column="Blocked"] [data-task="42"]').dragTo(page.locator('[data-column="Queued"]'))
  await expect(page.locator('.toast').last()).toContainText('Task 42 stays where it is')
  await expect(page.locator('.toast').last()).toContainText('Only pending tasks can be queued')
  expect(task(42).status).toBe('Blocked')

  await page.locator('[data-column="Blocked"] [data-task="42"]').dragTo(page.locator('[data-column="Pending"]'))
  await expect(dialog).toContainText('Unblock task: #42')
  await dialog.getByTestId('action-submit').click()
  await expect(page.locator('[data-column="Pending"] [data-task="42"]')).toBeVisible()
})

test('the command palette jumps to a task', async ({ page }) => {
  await createTask({ task: 43, title: 'Find me with the keyboard', description: 'Palette', branch: 'feature/palette-43' })
  await signIn(page)
  await page.keyboard.press('ControlOrMeta+k')
  const palette = page.locator('dialog.modal.dialog[open]')
  await palette.getByRole('searchbox').fill('keyboard')
  await palette.getByRole('option', { name: /#43 Find me with the keyboard/ }).click()
  await expect(page.locator('[data-task-panel="43"]')).toBeVisible()
})

test('an agent session can be watched, messaged, and closed after it finishes', async ({ page }) => {
  await createTask({ task: 44, title: 'Talk to the agent', description: 'Waits for go. [fake:wait]', branch: 'feature/talk-44' })
  await api('POST', '/runs/trigger', { tasks: [44] })
  const session = `${env.prefix}-44-fake`
  await signIn(page)
  await page.goto(`${env.base}/sessions`)
  const tile = page.locator(`[data-session="${session}"]`)
  await expect(tile.getByTestId('screen-preview')).toContainText('Type go and press Enter', { timeout: 45_000 })

  // Message the agent from the full terminal dialog; it echoes the message.
  await tile.getByRole('button', { name: 'Open terminal' }).click()
  const dialog = page.locator('dialog.modal.dialog[open]')
  await dialog.getByLabel('Message to the agent').fill('go')
  await dialog.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(dialog.getByTestId('terminal').locator('.xterm-rows')).toContainText('Reported success.', { timeout: 45_000 })
  expect(events(44).map((item) => item.event_type)).toContain('OPERATOR_MESSAGE')
  await dialog.getByRole('button', { name: 'Close' }).click()

  // The run is complete but Alfred leaves the session alive; the UI can close it.
  await expect(tile).toContainText('left running')
  await tile.getByRole('button', { name: 'Close session' }).click()
  await page.locator('dialog.modal.dialog[open]').getByRole('button', { name: 'Close session' }).click()
  await expect(tile).toHaveCount(0)
  expect(() => tmux(['has-session', '-t', `=${session}`])).toThrow()
  expect(events(44).map((item) => item.event_type)).toContain('SESSION_CLOSED')
  expect(runs(44).at(-1)?.run_status).toBe('completed')
})
