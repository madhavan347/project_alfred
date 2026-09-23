/** Board columns and the Alfred action a drag-and-drop between columns stands for. */

import type { AgentDescription, LifecyclePhase, Task, TaskStatus } from '@/api/types'
import type { Values } from '@/lib/actions'
import { PHASE_META, PHASES, STATUS_META, TASK_STATUSES } from '@/lib/status'

export type Grouping = 'status' | 'phase' | 'agent'

export interface ColumnDef {
  key: string
  title: string
  color: string
  description: string
  tasks: Task[]
}

export type DropPlan =
  | { allowed: true; action: string; overrides: Values; label: string }
  | { allowed: false; reason: string }

const OPTIONAL_STATUSES = new Set<TaskStatus>(['On Hold', 'Consolidated'])
const FINISHED_STATUSES = new Set<TaskStatus>(['Completed', 'Consolidated'])

const PRIORITY_ORDER: Record<string, number> = { P0: 0, P1: 1, P2: 2, P3: 3, P4: 4, P5: 5 }

export function sortTasks(tasks: Task[]): Task[] {
  return [...tasks].sort(
    (left, right) =>
      (PRIORITY_ORDER[left.priority] ?? 9) - (PRIORITY_ORDER[right.priority] ?? 9) ||
      left.task_number - right.task_number,
  )
}

export function isFinished(task: Task): boolean {
  return FINISHED_STATUSES.has(task.status) || task.lifecycle_phase === 'archived' || task.lifecycle_phase === 'consolidated'
}

export function columnsFor(
  tasks: Task[],
  grouping: Grouping,
  agents: AgentDescription[],
  options: { showFinished: boolean; dragging: boolean },
): ColumnDef[] {
  const visible = options.showFinished ? tasks : tasks.filter((task) => !isFinished(task))
  if (grouping === 'phase') {
    return PHASES.filter((phase) => options.showFinished || (phase !== 'archived' && phase !== 'consolidated'))
      .map((phase) => ({
        key: phase,
        title: PHASE_META[phase].label,
        color: PHASE_META[phase].lamp,
        description: PHASE_META[phase].description,
        tasks: sortTasks(visible.filter((task) => task.lifecycle_phase === phase)),
      }))
      .filter((column) => column.tasks.length || options.dragging || column.key !== 'consolidated')
  }
  if (grouping === 'agent') {
    const aliases = new Set(agents.map((agent) => agent.alias))
    for (const task of visible) if (task.assigned_agent_alias) aliases.add(task.assigned_agent_alias)
    const columns: ColumnDef[] = [
      {
        key: '',
        title: 'Unassigned',
        color: 'var(--lamp-off)',
        description: 'Tasks without an agent',
        tasks: sortTasks(visible.filter((task) => !task.assigned_agent_alias)),
      },
    ]
    for (const alias of [...aliases].sort()) {
      const agent = agents.find((item) => item.alias === alias)
      columns.push({
        key: alias,
        title: alias,
        color: 'var(--lamp-progress)',
        description: agent ? [agent.cli, agent.model, agent.runtime_target].filter(Boolean).join(', ') : 'Not in the configuration',
        tasks: sortTasks(visible.filter((task) => task.assigned_agent_alias === alias)),
      })
    }
    return columns
  }
  return TASK_STATUSES.filter((status) => options.showFinished || !FINISHED_STATUSES.has(status))
    .map((status) => ({
      key: status,
      title: STATUS_META[status].label,
      color: STATUS_META[status].lamp,
      description: STATUS_META[status].description,
      tasks: sortTasks(visible.filter((task) => task.status === status)),
    }))
    .filter((column) => column.tasks.length || options.dragging || !OPTIONAL_STATUSES.has(column.key as TaskStatus))
}

/** Map a drop onto a column to the Alfred action it represents. */
export function dropPlan(task: Task, grouping: Grouping, column: string): DropPlan {
  const actions = task.derived.actions
  const deny = (reason: string): DropPlan => ({ allowed: false, reason: reason || 'Not possible from here' })
  const allow = (action: string, label: string, overrides: Values = {}): DropPlan => ({
    allowed: true,
    action,
    overrides,
    label,
  })

  if (grouping === 'agent') {
    if (column === task.assigned_agent_alias) return deny('Already assigned here')
    if (!column) return deny('Alfred cannot unassign an agent; assign another one instead')
    if (task.assigned_agent_alias) {
      return actions.reassign.enabled ? allow('reassign', `Reassign to ${column}`, { agent: column }) : deny(actions.reassign.reason)
    }
    return actions.assign.enabled ? allow('assign', `Assign to ${column}`, { agent: column }) : deny(actions.assign.reason)
  }

  if (grouping === 'phase') {
    const target = column as LifecyclePhase
    if (target === task.lifecycle_phase) return deny('Already here')
    if (target === 'testing_deployment') return actions.merge.enabled ? allow('merge', 'Record the merge') : deny(actions.merge.reason)
    if (target === 'archived') return actions.archive.enabled ? allow('archive', 'Archive') : deny(actions.archive.reason)
    if (target === 'consolidated') {
      return actions.consolidate.enabled ? allow('consolidate', 'Consolidate') : deny(actions.consolidate.reason)
    }
    return deny('Tasks return to active only through review changes')
  }

  const target = column as TaskStatus
  if (target === task.status) return deny('Already here')
  switch (target) {
    case 'Running':
      if (actions.trigger.enabled) return allow('trigger', 'Trigger the agent')
      if (actions.reopen.enabled) return allow('reopen', 'Reopen with a new attempt')
      return deny(actions.trigger.reason)
    case 'In Progress':
      if (task.status === 'MR in Review' && actions.review.request_changes) {
        return allow('review', 'Request changes', { decision: 'changes_requested' })
      }
      return actions.progress.enabled ? allow('progress', 'Record progress') : deny(actions.progress.reason)
    case 'Blocked':
      return actions.block.enabled ? allow('block', 'Block with a reason') : deny(actions.block.reason)
    case 'On Hold':
      return actions.hold.enabled ? allow('hold', 'Put on hold') : deny(actions.hold.reason)
    case 'Pending':
      if (actions.stop.enabled) return allow('stop', 'Stop the run')
      if (actions.unblock.enabled) return allow('unblock', task.status === 'On Hold' ? 'Resume' : 'Unblock')
      return deny('Stop the run or unblock the task to return it to Pending')
    case 'MR in Review':
      if (task.derived.active_run && actions.complete.enabled) {
        return allow('complete', 'Report completion', { result: 'success' })
      }
      return actions.review.enabled ? allow('review', 'Approve the review', { decision: 'approved' }) : deny(actions.review.reason)
    case 'Completed':
      if (actions.deploy.enabled) return allow('deploy', 'Record the deployment')
      return deny(actions.merge.enabled ? 'Record the merge first (drag in the lifecycle view or use Merge)' : actions.deploy.reason)
    case 'Consolidated':
      return actions.consolidate.enabled ? allow('consolidate', 'Consolidate') : deny(actions.consolidate.reason)
    case 'Queued':
      return task.status === 'Pending' && actions.assign.enabled
        ? allow('assign', 'Queue for trigger all', { dispatch: 'queued', agent: task.assigned_agent_alias })
        : deny('Only pending tasks can be queued')
    default:
      return deny('Not a column')
  }
}

export function matchesFilters(
  task: Task,
  filters: { search: string; agent: string; priority: string; repository: string },
): boolean {
  const search = filters.search.trim().toLowerCase()
  if (search) {
    const haystack = [
      `#${task.task_number}`,
      String(task.task_number),
      task.title,
      task.description,
      task.category,
      task.branch_name,
      task.notes,
      task.assigned_agent_alias,
    ]
      .join(' ')
      .toLowerCase()
    if (!search.split(/\s+/).every((word) => haystack.includes(word))) return false
  }
  if (filters.agent === '-' && task.assigned_agent_alias) return false
  if (filters.agent && filters.agent !== '-' && task.assigned_agent_alias !== filters.agent) return false
  if (filters.priority && task.priority !== filters.priority) return false
  if (filters.repository && !task.target_repositories.includes(filters.repository)) return false
  return true
}
