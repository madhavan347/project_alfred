/**
 * Plan first: the agent asks to be trusted, writes a plan in its session, and reports it; the
 * operator reads the plan and its transcript in the UI, approves it, and the same session executes.
 */
import { expect, test } from '@playwright/test'
import { createTask, events, openAction, openTask, runs, signIn, submit, tab, task } from './helpers'

test('a plan-first task is planned, reviewed in the Plan tab, approved, and executed', async ({ page }) => {
  await createTask({
    task: 21,
    title: 'Plan the cache layer',
    description: 'Plan before changing anything. [fake:trust]',
    branch: 'feature/cache-21',
    mode: 'plan-execution',
  })
  await signIn(page)
  const panel = await openTask(page, 21, 'plan')
  await expect(panel).toContainText('Nothing reported yet')

  const start = await openAction(page, panel, 'trigger')
  await expect(start.getByText('Starts the planning phase in a new session without creating worktrees.')).toBeVisible()
  await submit(start)

  // The agent stops at a trust question. Answer it with the quick keys (tmux send-keys).
  await expect(panel.getByTestId('screen-preview')).toContainText('Do you trust the files in this folder?')
  await panel.getByRole('button', { name: 'y', exact: true }).click()
  await panel.getByRole('button', { name: 'Enter', exact: true }).click()

  // The plan arrives through the real CLI and is shown, with a saved transcript.
  await expect(panel).toContainText('The plan is ready for your review')
  await expect(panel.locator('.report').first()).toContainText('Add the change in a new file next to the existing code.')
  await expect(page.locator('[data-call="plan"]')).toBeAttached()
  await expect(panel.locator('.viewer pre')).toContainText('## Plan', { timeout: 30_000 })
  expect(task(21).planning_state).toBe('started')
  expect(runs(21)).toHaveLength(1)

  // No worktree exists while planning.
  await tab(panel, 'changes')
  await expect(panel).toContainText('Plan-first tasks get their worktrees when the plan is approved.')

  // Approve: the execution prompt goes to the same session, which does the work.
  await tab(panel, 'plan')
  await panel.getByTestId('approve-plan').click()
  const approve = page.locator('dialog.modal.dialog[open]')
  await approve.getByLabel('Note to the agent').fill('Approved. Keep it small.')
  await expect(approve.locator('.command')).toContainText("alfred run continue --task 21 --note 'Approved. Keep it small.'")
  await submit(approve)

  await expect(panel.locator('.facts')).toContainText('In review', { timeout: 45_000 })
  const record = runs(21)
  expect(record).toHaveLength(1)
  expect(record[0]).toMatchObject({ phase: 'execution', run_status: 'completed' })
  expect(task(21)).toMatchObject({ planning_state: 'completed', status: 'MR in Review' })
  const types = events(21).map((item) => item.event_type)
  expect(types).toEqual(expect.arrayContaining(['RUN_STARTED', 'AGENT_PLAN_COMPLETED', 'PLAN_APPROVED', 'RUN_COMPLETED']))
  expect(events(21).find((item) => item.event_type === 'PLAN_APPROVED')?.details).toBe('Approved. Keep it small.')

  // The worktree now exists with the agent's file, and the plan tab records the approval.
  await tab(panel, 'changes')
  await expect(panel.locator('[data-repository="app"]')).toContainText('fake-agent-task-21.txt')
  await tab(panel, 'plan')
  await expect(panel).toContainText('Approved. Keep it small.')
})
