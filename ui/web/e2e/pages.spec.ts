/** Knowledge, reports, runs, and notifications agree with the CLI's view of the same state. */
import { expect, test } from '@playwright/test'
import { alfred, api, createTask, env, signIn } from './helpers'

test('a knowledge entry added in the UI is written where the CLI lists it', async ({ page }) => {
  await createTask({ task: 71, title: 'Knowledge source', description: 'Knowledge', branch: 'feature/knowledge-71' })
  await signIn(page)
  await page.goto(`${env.base}/knowledge`)
  await page.getByRole('button', { name: 'Add entry' }).click()
  const dialog = page.locator('dialog.modal.dialog[open]')
  await dialog.getByLabel('Task number').fill('71')
  await dialog.getByRole('radio', { name: 'decisions' }).click()
  await dialog.getByLabel('Title').fill('Keep prompts as arguments')
  await dialog.getByLabel('Learning').fill('Interactive agent CLIs can drop pasted prompts while starting.')
  await dialog.getByLabel('Related files').fill('src/alfred/application/dispatch.py')
  await expect(dialog.locator('.command')).toContainText('alfred knowledge add --task 71 --category decisions')
  await dialog.getByTestId('action-submit').click()
  await expect(page.locator('.entry.active')).toContainText('Keep prompts as arguments')
  await expect(page.locator('.reader')).toContainText('Interactive agent CLIs can drop pasted prompts while starting.')
  expect(alfred(['knowledge', 'list', '--category', 'decisions']).output).toContain('task-71-keep-prompts-as-arguments.md')
})

test('reports match the CLI', async ({ page }) => {
  await signIn(page)
  await page.goto(`${env.base}/reports`)
  const velocity = alfred(['report', 'velocity']).output.trim()
  const [completed, total] = /Completed (\d+)\/(\d+)/.exec(velocity)!.slice(1)
  await expect(page.getByTestId('velocity')).toHaveText(`${completed}/${total}`)
  const risk = alfred(['report', 'risk']).output
  for (const match of risk.matchAll(/Task (\d+):/g)) {
    await expect(page.locator('main')).toContainText(`#${match[1]}`)
  }
})

test('runs can be filtered by status like alfred run list', async ({ page }) => {
  await createTask({ task: 72, title: 'Run list entry', description: 'Completes at once', branch: 'feature/runs-72' })
  await api('POST', '/runs/trigger', { tasks: [72] })
  await expect.poll(() => alfred(['run', 'list', '--status', 'completed']).output, { timeout: 45_000 }).toContain('task=72')
  await signIn(page)
  await page.goto(`${env.base}/runs`)
  await page.getByRole('radio', { name: /Completed/ }).click()
  await expect(page.locator('.command')).toContainText('alfred run list --status completed')
  await expect(page.locator('tbody')).toContainText('Run list entry')
  await expect(page.locator('tbody tr').filter({ hasText: 'Running' })).toHaveCount(0)
})

test('notifications are acknowledged per task and cleared', async ({ page }) => {
  await createTask({ task: 73, title: 'Needs review', description: 'Completes at once', branch: 'feature/notify-73' })
  await api('POST', '/runs/trigger', { tasks: [73] })
  await expect.poll(() => alfred(['run', 'list', '--status', 'completed']).output, { timeout: 45_000 }).toContain('task=73')
  await api('POST', '/coordinator/once')
  await signIn(page)
  await page.goto(`${env.base}/notifications`)
  const group = page.locator('.group').filter({ hasText: '#73 Needs review' })
  await expect(group).toContainText('Completed, needs review')
  await expect(group).toContainText('Agent fake')
  await group.getByRole('button', { name: 'Acknowledge' }).click()
  await expect(group).toHaveCount(0)
  expect(alfred(['notifications']).output).not.toContain('Task 73')
  await page.getByRole('button', { name: 'Clear acknowledged' }).click()
  await expect(page.locator('.toast').last()).toContainText('Cleared')
})
