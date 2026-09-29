/**
 * Settings: health checks, editing the configuration with Alfred's own validation, creating and
 * switching workspaces, migrating legacy runtime state, and the recorded actor.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, test } from '@playwright/test'
import { alfred, api, env, events, signIn } from './helpers'

test.afterAll(async () => {
  // Leave the shared sandbox open for any test that runs afterwards.
  await api('POST', '/workspace/open', { path: env.config })
})

test('health checks confirm agents can run alfred and find the workspace', async ({ page }) => {
  await signIn(page)
  await page.goto(`${env.base}/settings#health`)
  for (const key of ['config', 'state', 'git', 'tmux', 'alfred-path', 'agent-executables', 'discovery']) {
    await expect(page.locator(`[data-check="${key}"]`)).toHaveClass(/\bok\b/)
  }
  await expect(page.locator('.check.error')).toHaveCount(0)
})

test('the configuration editor validates with Alfred and saves a new agent', async ({ page }) => {
  await signIn(page)
  await page.goto(`${env.base}/settings#configuration`)
  const editor = page.getByLabel('Configuration TOML')
  await expect(editor).toHaveValue(/\[agents\.fake\]/)

  // An unknown key (appended, so it lands in the last table, [knowledge]) is rejected.
  const original = await editor.inputValue()
  await editor.fill(`${original}\nbogus_key = 1\n`)
  await expect(page.locator('.config .failure').first()).toContainText('Unknown keys in knowledge: bogus_key')
  await expect(page.getByTestId('save-config')).toBeDisabled()
  await page.getByRole('button', { name: 'Revert' }).click()
  await expect(page.getByText('Valid', { exact: true })).toBeVisible()

  // Insert an agent from a preset, then save.
  await page.getByLabel('Start from').selectOption('recorder')
  await page.getByLabel('Alias').fill('watcher')
  await page.getByRole('button', { name: 'Insert into the configuration' }).last().click()
  await expect(editor).toHaveValue(/\[agents\.watcher\]\nruntime_target = "local-test"/)
  await expect(page.getByText('Valid', { exact: true })).toBeVisible()
  await page.getByTestId('save-config').click()
  await expect(page.locator('.toast').first()).toContainText('Configuration saved')

  const saved = readFileSync(env.config, 'utf8')
  expect(saved).toContain('[agents.watcher.commands]')
  expect(saved).toContain('execution = ["tail", "-f", "/dev/null"]')
  expect(readFileSync(`${env.config}.bak`, 'utf8')).not.toContain('watcher')
  // The CLI and the live snapshot both see the new agent.
  await api('POST', '/tasks', { task: 61, title: 'For the watcher', description: 'Config test', branch: 'feature/watch-61' })
  expect(alfred(['agent', 'assign', '--task', '61', '--to', 'watcher']).output).toContain('assigned to watcher')
  await page.locator('.topbar').getByRole('button', { name: 'New task' }).click()
  await expect(page.locator('#task-agent option[value="watcher"]')).toHaveCount(1)
})

test('a new workspace is created, legacy state is migrated into it, and the sandbox is reopened', async ({ page }) => {
  const legacy = join(process.env.AUI_ROOT!, 'legacy-runtime')
  mkdirSync(legacy, { recursive: true })
  writeFileSync(
    join(legacy, 'tasks.json'),
    JSON.stringify({
      tasks: [
        {
          task_number: 7,
          title: 'Legacy task',
          description: 'Imported from the legacy runtime',
          status: 'In Progress',
          repos: ['api'],
          branch_name: 'legacy/task-7',
          created_at_ist: '2025-01-02T10:00:00+05:30',
        },
      ],
    }),
  )
  writeFileSync(
    join(legacy, 'runs.json'),
    JSON.stringify({
      runs: [{ run_id: 'run-1', task_number: 7, agent_alias: 'builder', runtime_target: 'local', run_status: 'running', started_at_ist: '2025-01-02T10:05:00+05:30' }],
    }),
  )
  writeFileSync(join(legacy, 'queue.json'), JSON.stringify({ queued_tasks: [7] }))
  writeFileSync(
    join(legacy, 'agent_map.json'),
    JSON.stringify({ builder: { runtime_target: 'local', dispatch_templates: { direct: 'local-cli', plan: 'local-cli --plan', execution: 'local-cli --execute' } } }),
  )
  const second = join(process.env.AUI_ROOT!, 'second-project')

  await signIn(page)
  await page.goto(`${env.base}/settings#workspace`)
  await page.getByLabel('Project root').fill(second)
  await expect(page.locator('.command').filter({ hasText: 'alfred init' })).toContainText(`alfred init --root ${second}`)
  await page.getByRole('button', { name: 'Initialize' }).click()
  await expect(page.locator('.topbar .workspace')).toContainText('second-project')
  await expect(page.getByLabel('Configuration TOML')).toHaveValue(/session_prefix = "alfred-task"/)

  await page.goto(`${env.base}/settings#migrate`)
  await page.getByLabel('Legacy runtime folder').fill(legacy)
  await page.getByRole('button', { name: 'Migrate' }).click()
  await expect(page.locator('main')).toContainText('Legacy runtime migrated: tasks=1 runs=1 queued=1')
  await expect(page.locator('.fragment')).toContainText('plan = ["local-cli", "--plan"]')
  await page.getByRole('button', { name: 'Migrate' }).click()
  await expect(page.locator('main')).toContainText('Legacy runtime already migrated')
  // The legacy source is untouched.
  expect(JSON.parse(readFileSync(join(legacy, 'queue.json'), 'utf8'))).toEqual({ queued_tasks: [7] })

  await page.goto(`${env.base}/`)
  await expect(page.locator('[data-task="7"]')).toContainText('Legacy task')

  // Reopen the sandbox from the recent list.
  await page.goto(`${env.base}/settings#workspace`)
  await page.locator('.recent').getByRole('button', { name: env.config }).click()
  await expect(page.locator('.topbar .workspace')).toContainText('workspace')
  await expect(page.locator('.topbar .prefix')).toContainText(env.prefix)
})

test('actions are recorded under the actor chosen in preferences', async ({ page }) => {
  await signIn(page)
  await page.goto(`${env.base}/settings#preferences`)
  await page.getByLabel('Record my actions as').fill('manager:e2e')
  await api('POST', '/tasks', { task: 62, title: 'Actor check', description: 'Actor', branch: 'feature/actor-62', assign: 'fake' })
  await page.goto(`${env.base}/?task=62`)
  const panel = page.locator('[data-task-panel="62"]')
  await panel.locator('[data-action="block"]').click()
  const dialog = page.locator('dialog.modal.dialog[open]')
  await expect(dialog.getByLabel('Recorded as')).toHaveValue('manager:e2e')
  await expect(dialog.locator('.command')).toContainText('--actor manager:e2e')
  await dialog.getByLabel('Reason').fill('Checking the actor')
  await dialog.getByTestId('action-submit').click()
  await expect(panel.locator('.facts')).toContainText('Blocked')
  expect(events(62).at(-1)).toMatchObject({ event_type: 'STATUS_BLOCKED', actor: 'manager:e2e' })

  await page.goto(`${env.base}/settings#preferences`)
  await page.getByRole('button', { name: 'Reset preferences' }).click()
  await expect(page.getByLabel('Record my actions as')).toHaveValue('manager')
})
