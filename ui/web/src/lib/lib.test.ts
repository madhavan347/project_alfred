import { describe, expect, it } from 'vitest'
import type { Task, TaskDerived } from '@/api/types'
import { ACTIONS, initialValues, nextStep, type ActionContext } from './actions'
import { ansiToHtml, escapeHtml, stripAnsi } from './ansi'
import { columnsFor, dropPlan, matchesFilters } from './board'
import { alfredCommand, shellJoin, shellQuote } from './cli'
import { parseDiff } from './diff'
import { humanSpan, humanize, relative } from './format'
import { splitCommand } from './shellwords'

const allowed = { enabled: true, reason: '' }
const denied = (reason: string) => ({ enabled: false, reason })

function makeTask(overrides: Partial<Task> = {}, actions: Partial<TaskDerived['actions']> = {}): Task {
  const names = [
    'trigger', 'continue', 'stop', 'reopen', 'event', 'complete', 'progress', 'start', 'block', 'unblock', 'hold',
    'review', 'merge', 'deploy', 'archive', 'consolidate', 'assign', 'reassign', 'update', 'worktree_create',
    'commit', 'push', 'remove_worktrees',
  ] as const
  const base = Object.fromEntries(names.map((name) => [name, denied(`${name} is not possible`)]))
  return {
    task_number: 7,
    title: 'Seven',
    description: 'Do it',
    category: 'General',
    priority: 'P2',
    status: 'Pending',
    deadline: '',
    notes: '',
    dependencies: [],
    assigned_agent_alias: 'fake',
    dispatch_mode: 'auto',
    execution_mode: 'direct',
    worktree_mode: 'enabled',
    branch_name: 'feature/seven',
    planning_state: 'not_required',
    lifecycle_phase: 'active',
    target_repositories: ['app'],
    created_at: '',
    updated_at: '',
    derived: {
      active_run: null,
      latest_run: null,
      run_count: 0,
      session: null,
      agents: [],
      approved_since_last_work: false,
      plan: { required: false, state: 'not_required', awaiting_approval: false, reported: false, last_report: null },
      last_event: null,
      event_count: 0,
      notifications: { pending: 0, types: [] },
      worktrees: [],
      dirty: false,
      knowledge_count: 0,
      queued: false,
      completion_pending: false,
      transcripts: 0,
      journey: [],
      actions: { ...base, ...actions } as TaskDerived['actions'],
    },
    ...overrides,
  }
}

describe('ansi', () => {
  it('escapes HTML and keeps colour as styled spans only', () => {
    const html = ansiToHtml('\x1b[1;31m<b>alert</b>\x1b[0m plain \x1b[38;5;208morange\x1b[38;2;1;2;3m rgb\x1b[0m')
    expect(html).toContain('<span style="color:var(--ansi-1);font-weight:700">&lt;b&gt;alert&lt;/b&gt;</span>')
    expect(html).toContain(' plain ')
    expect(html).toContain('color:rgb(255 135 0)')
    expect(html).toContain('color:rgb(1 2 3)')
    expect(html).not.toContain('<b>')
  })

  it('drops cursor movement and OSC sequences', () => {
    expect(stripAnsi('\x1b[2J\x1b[H\x1b]8;;http://x\x07link\x1b]8;;\x07\r\n')).toBe('link\n')
    expect(escapeHtml(`"'&`)).toBe('&quot;&#39;&amp;')
  })

  it('renders inverse video', () => {
    expect(ansiToHtml('\x1b[7mselected\x1b[27m')).toContain('background:var(--screen-ink)')
  })
})

describe('cli', () => {
  it('quotes only what a shell needs', () => {
    expect(shellQuote('feature/health-1')).toBe('feature/health-1')
    expect(shellQuote('{prompt}')).toBe('{prompt}')
    expect(shellQuote('{a,b}')).toBe("'{a,b}'")
    expect(shellQuote("it's here")).toBe(`'it'"'"'s here'`)
    expect(shellQuote('')).toBe("''")
    expect(shellJoin(['claude', '--model', 'opus', '{prompt}'])).toBe('claude --model opus {prompt}')
  })

  it('omits empty flags and renders bare boolean flags', () => {
    expect(alfredCommand('run', 'stop', ['--task', 3], ['--reason', ''], true && '--force')).toBe('alfred run stop --task 3 --force')
    expect(alfredCommand('task', 'update', ['--task', 1], ['--notes', '', true])).toBe("alfred task update --task 1 --notes ''")
  })
})

describe('shell words', () => {
  it('splits like a POSIX shell for quotes and escapes', () => {
    expect(splitCommand(`claude --allowedTools "Bash(alfred *)" '{prompt}' a\\ b`)).toEqual([
      'claude', '--allowedTools', 'Bash(alfred *)', '{prompt}', 'a b',
    ])
    expect(splitCommand('  ')).toEqual([])
    expect(splitCommand(`""`)).toEqual([''])
    expect(() => splitCommand(`"open`)).toThrow('Unclosed quote')
  })
})

describe('diff', () => {
  it('numbers lines and counts changes per file', () => {
    const files = parseDiff(
      [
        'diff --git a/app.py b/app.py',
        'index 1..2 100644',
        '--- a/app.py',
        '+++ b/app.py',
        '@@ -1,2 +1,3 @@',
        ' keep',
        '-old',
        '+new',
        '+added',
        'diff --git a/img.png b/img.png',
        'Binary files a/img.png and b/img.png differ',
      ].join('\n'),
    )
    expect(files).toHaveLength(2)
    expect(files[0]).toMatchObject({ path: 'app.py', additions: 2, deletions: 1 })
    expect(files[0].lines.map((line) => [line.kind, line.oldNumber, line.newNumber])).toEqual([
      ['hunk', null, null],
      ['context', 1, 1],
      ['remove', 2, null],
      ['add', null, 2],
      ['add', null, 3],
    ])
    expect(files[1].binary).toBe(true)
  })
})

describe('board', () => {
  it('maps drops to the action a column stands for', () => {
    const pending = makeTask({}, { trigger: allowed, block: allowed })
    expect(dropPlan(pending, 'status', 'Running')).toEqual({ allowed: true, action: 'trigger', overrides: {}, label: 'Trigger the agent' })
    expect(dropPlan(pending, 'status', 'Blocked')).toMatchObject({ allowed: true, action: 'block' })
    expect(dropPlan(pending, 'status', 'Pending')).toEqual({ allowed: false, reason: 'Already here' })
    expect(dropPlan(pending, 'status', 'MR in Review')).toEqual({ allowed: false, reason: 'review is not possible' })
    const reviewing = makeTask({ status: 'MR in Review' }, {
      review: { enabled: true, reason: '', approve: true, request_changes: true },
    })
    expect(dropPlan(reviewing, 'status', 'In Progress')).toMatchObject({ action: 'review', overrides: { decision: 'changes_requested' } })
    const running = makeTask({ status: 'Running' }, { stop: allowed, complete: allowed })
    running.derived.active_run = { run_status: 'running' } as TaskDerived['active_run']
    expect(dropPlan(running, 'status', 'Pending')).toMatchObject({ action: 'stop' })
    expect(dropPlan(running, 'status', 'MR in Review')).toMatchObject({ action: 'complete', overrides: { result: 'success' } })
    expect(dropPlan(pending, 'agent', 'other')).toEqual({ allowed: false, reason: 'reassign is not possible' })
    expect(dropPlan(pending, 'agent', '')).toMatchObject({ allowed: false })
    expect(dropPlan(pending, 'phase', 'archived')).toEqual({ allowed: false, reason: 'archive is not possible' })
  })

  it('builds columns, hiding optional empty ones unless dragging', () => {
    const tasks = [makeTask(), makeTask({ task_number: 8, status: 'Completed', lifecycle_phase: 'archived', priority: 'P0' })]
    const columns = columnsFor(tasks, 'status', [], { showFinished: false, dragging: false })
    expect(columns.map((column) => column.key)).toEqual(['Pending', 'Queued', 'Running', 'In Progress', 'Blocked', 'MR in Review'])
    const dragging = columnsFor(tasks, 'status', [], { showFinished: true, dragging: true })
    expect(dragging.map((column) => column.key)).toContain('On Hold')
    expect(dragging.find((column) => column.key === 'Completed')?.tasks.map((task) => task.task_number)).toEqual([8])
    const byAgent = columnsFor(tasks, 'agent', [], { showFinished: true, dragging: false })
    expect(byAgent.map((column) => column.key)).toEqual(['', 'fake'])
  })

  it('filters by words, agent, priority, and repository', () => {
    const task = makeTask({ notes: 'Tests pass now' })
    const none = { search: '', agent: '', priority: '', repository: '' }
    expect(matchesFilters(task, { ...none, search: 'seven tests' })).toBe(true)
    expect(matchesFilters(task, { ...none, search: '#7' })).toBe(true)
    expect(matchesFilters(task, { ...none, search: 'missing' })).toBe(false)
    expect(matchesFilters(task, { ...none, agent: '-' })).toBe(false)
    expect(matchesFilters(task, { ...none, priority: 'P1' })).toBe(false)
    expect(matchesFilters(task, { ...none, repository: 'app' })).toBe(true)
  })
})

describe('actions', () => {
  const context = (task: Task): ActionContext => ({ task, config: undefined, actor: 'manager' })

  it('chooses the next step a person should take', () => {
    expect(nextStep(makeTask({ assigned_agent_alias: '' })).action).toBe('assign')
    expect(nextStep(makeTask({}, { trigger: allowed })).label).toBe('Trigger the agent')
    const plan = makeTask({ execution_mode: 'plan-execution', planning_state: 'started' }, { continue: allowed })
    plan.derived.plan = { ...plan.derived.plan, awaiting_approval: true, reported: true }
    expect(nextStep(plan)).toEqual({ action: 'continue', label: 'Review and approve the plan' })
    const review = makeTask({ status: 'MR in Review' })
    expect(nextStep(review).action).toBe('review')
    review.derived.approved_since_last_work = true
    expect(nextStep(review).action).toBe('merge')
    expect(nextStep(makeTask({ status: 'Completed', lifecycle_phase: 'archived' })).label).toBe('Finished')
  })

  it('renders the exact CLI equivalent for an action', () => {
    const task = makeTask()
    const stop = ACTIONS.stop
    const values = initialValues(stop, context(task), { cleanup: true, force: true, reason: 'Superseded approach' })
    expect(stop.command(values, context(task))).toBe("alfred run stop --task 7 --reason 'Superseded approach' --cleanup yes --force")
    expect(stop.request(values, context(task)).body).toMatchObject({ cleanup: true, force: true })
    const event = ACTIONS.event
    const reported = initialValues(event, context(task), { type: 'blocked', note: 'Waiting', acting: 'agent' })
    expect(event.command(reported, context(task))).toBe("alfred run event --task 7 --type blocked --note Waiting --actor agent:fake")
    const managed = { ...reported, acting: 'manager' }
    expect(event.command(managed, context(task))).toBe(
      'alfred run event --task 7 --type blocked --note Waiting --actor manager --override-manager',
    )
    expect(ACTIONS.hold.command({}, context(task))).toBeNull()
  })
})

describe('format', () => {
  it('writes human spans and labels', () => {
    expect(humanSpan(59)).toBe('59s')
    expect(humanSpan(3700)).toBe('1h 1m')
    expect(humanSpan(200000)).toBe('2d 7h')
    expect(humanize('AGENT_PLAN_COMPLETED')).toBe('Agent plan completed')
    const now = Date.parse('2026-01-01T12:00:00Z')
    expect(relative('2026-01-01T11:55:00Z', now)).toBe('5 min ago')
    expect(relative('2026-01-01T11:59:58Z', now)).toBe('just now')
    expect(relative('', now)).toBe('—')
  })
})
