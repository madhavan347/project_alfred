/**
 * The operator's main path, entirely through the UI: create a task, dispatch a real agent into
 * tmux, answer it through the browser terminal, process its completion, commit and push its work,
 * then review, merge, deploy, and archive.
 */
import { expect, test } from '@playwright/test'
import { alfred, env, events, git, openAction, runs, signIn, submit, tab, task, terminalText } from './helpers'
import { join } from 'node:path'

test('a direct task goes from creation to archive through the UI', async ({ page }) => {
  await signIn(page)

  // Create the task with the form; the branch name is suggested from the title.
  await page.locator('.topbar').getByRole('button', { name: 'New task' }).click()
  const form = page.locator('dialog.modal.dialog[open]')
  await form.locator('#task-number').fill('11')
  await form.locator('#task-title').fill('Direct flow from the UI')
  await form.locator('#task-description').fill('Write a file, then wait for the operator. [fake:wait]')
  await expect(form.locator('#task-branch')).toHaveValue('feature/direct-flow-from-the-ui-11')
  await form.locator('#task-agent').selectOption('fake')
  await expect(form.locator('.command')).toContainText('alfred task create --task 11')
  await form.getByTestId('task-form-submit').click()

  const panel = page.locator('[data-task-panel="11"]')
  await expect(panel).toBeVisible()
  await expect(panel.locator('.facts')).toContainText('Pending')

  // Trigger: the action dialog shows the exact CLI equivalent.
  const trigger = await openAction(page, panel, 'trigger')
  await expect(trigger.locator('.command')).toContainText('alfred run trigger --tasks 11')
  await submit(trigger)

  // The agent reports progress through the real CLI; the drawer follows live.
  await expect(panel.locator('.facts')).toContainText('In progress')
  expect(runs(11).at(-1)?.run_status).toBe('running')

  // It waits for the operator; answer it in the browser terminal.
  await tab(panel, 'terminal')
  await expect(terminalText(panel)).toContainText('Type go and press Enter', { timeout: 45_000 })
  await panel.getByTestId('terminal').click()
  await page.keyboard.type('go')
  await page.keyboard.press('Enter')
  await expect(panel.locator('.facts')).toContainText('In review', { timeout: 45_000 })

  // The completion handoff waits for the coordinator: the call board shows it, and so does the
  // task itself, where it can be processed without leaving the drawer.
  await expect(page.locator('[data-call="completions"]')).toBeAttached()
  await tab(panel, 'overview')
  await expect(panel).toContainText('A completion report is waiting for the coordinator')
  await panel.getByRole('button', { name: 'Process now' }).click()
  await expect(page.locator('[data-call="review"]')).toBeAttached()
  await expect(panel).toContainText('Completed, needs review')

  // Commit the agent's uncommitted file and push the branch to the bare remote.
  await tab(panel, 'changes')
  await expect(panel.locator('[data-repository="app"]')).toContainText('fake-agent-task-11.txt')
  const commit = await openAction(page, panel, 'commit')
  await commit.getByLabel('Message').fill('Add the direct flow file')
  await expect(commit.locator('.command')).toContainText("alfred worktree commit --task 11 --type feature --message 'Add the direct flow file'")
  await submit(commit)
  await expect(panel.locator('[data-repository="app"]')).toContainText('[FEATURE] Add the direct flow file')
  const push = await openAction(page, panel, 'push')
  await submit(push)
  await expect(panel.locator('[data-repository="app"]')).toContainText('Up to date with origin/feature/direct-flow-from-the-ui-11')
  const remote = git(['show-ref', 'refs/heads/feature/direct-flow-from-the-ui-11'], join(env.workspace, 'app-remote.git'))
  expect(remote).toContain('feature/direct-flow-from-the-ui-11')

  // Merge is refused until a human approves after the latest work.
  await tab(panel, 'overview')
  await expect(panel).toContainText('No approval since the latest work')
  const review = await openAction(page, panel, 'review')
  await review.getByLabel('Review note').fill('Reviewed in the UI')
  await submit(review)
  await expect(panel).toContainText('Approved after the latest work')

  const merge = await openAction(page, panel, 'merge')
  await merge.getByLabel('Merge request').fill('local/11')
  await submit(merge)
  await expect(panel.locator('.facts')).toContainText('Testing and deployment')

  const deploy = await openAction(page, panel, 'deploy')
  await expect(deploy.locator('.command')).toContainText('alfred task deploy --task 11')
  await submit(deploy)
  await expect(panel.locator('.facts')).toContainText('Completed')

  const archive = await openAction(page, panel, 'archive')
  await submit(archive)
  await expect(panel.locator('.facts')).toContainText('Archived')

  // The persisted state agrees with what the UI showed.
  expect(task(11)).toMatchObject({ status: 'Completed', lifecycle_phase: 'archived' })
  const types = events(11).map((item) => item.event_type)
  for (const expected of ['RUN_STARTED', 'PROGRESS', 'RUN_COMPLETED', 'REVIEW_APPROVED', 'MERGED', 'PHASE_TESTING_DEPLOYMENT', 'STATUS_COMPLETED', 'PHASE_ARCHIVED']) {
    expect(types).toContain(expected)
  }
  expect(events(11).find((item) => item.event_type === 'PROGRESS')?.actor).toBe('agent:fake')

  // Close the drawer, follow the call board back to the task, and acknowledge its notification.
  await page.locator('dialog.modal.drawer').getByRole('button', { name: 'Close' }).click()
  await expect(panel).toBeHidden()
  await page.locator('[data-call="review"]').click()
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('Completed, needs review')
  await panel.getByRole('button', { name: 'Acknowledge' }).first().click()
  await expect(page.locator('[data-call="review"]')).toHaveCount(0)
  expect(alfred(['notifications']).output).toContain('No pending notifications')
})
