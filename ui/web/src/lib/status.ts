/** Presentation metadata for Alfred's statuses, phases, and notification types. */

import type { LifecyclePhase, PlanningState, RunStatus, TaskStatus } from '@/api/types'

export interface StatusMeta {
  label: string
  lamp: string
  description: string
}

export const TASK_STATUSES: TaskStatus[] = [
  'Pending',
  'Queued',
  'Running',
  'In Progress',
  'Blocked',
  'On Hold',
  'MR in Review',
  'Completed',
  'Consolidated',
]

export const STATUS_META: Record<TaskStatus, StatusMeta> = {
  Pending: { label: 'Pending', lamp: 'var(--lamp-pending)', description: 'Not started; trigger it explicitly' },
  Queued: { label: 'Queued', lamp: 'var(--lamp-queued)', description: 'Waiting for a dispatch (run trigger --all picks these)' },
  Running: { label: 'Running', lamp: 'var(--lamp-running)', description: 'An agent session was dispatched' },
  'In Progress': { label: 'In progress', lamp: 'var(--lamp-progress)', description: 'Work is being reported' },
  Blocked: { label: 'Blocked', lamp: 'var(--lamp-blocked)', description: 'Waiting on something outside the agent' },
  'On Hold': { label: 'On hold', lamp: 'var(--lamp-hold)', description: 'Paused on purpose' },
  'MR in Review': { label: 'In review', lamp: 'var(--lamp-review)', description: 'Waiting for human review' },
  Completed: { label: 'Completed', lamp: 'var(--lamp-done)', description: 'Deployed or archived' },
  Consolidated: { label: 'Consolidated', lamp: 'var(--lamp-consolidated)', description: 'Absorbed into another task' },
}

export const PHASES: LifecyclePhase[] = ['active', 'testing_deployment', 'archived', 'consolidated']

export const PHASE_META: Record<LifecyclePhase, StatusMeta> = {
  active: { label: 'Active', lamp: 'var(--lamp-progress)', description: 'Being worked on or reviewed' },
  testing_deployment: {
    label: 'Testing and deployment',
    lamp: 'var(--lamp-review)',
    description: 'Merged; waiting for deployment',
  },
  archived: { label: 'Archived', lamp: 'var(--lamp-done)', description: 'Finished and archived' },
  consolidated: { label: 'Consolidated', lamp: 'var(--lamp-consolidated)', description: 'Absorbed into another task' },
}

export const PLANNING_LABELS: Record<PlanningState, string> = {
  not_required: 'No plan needed',
  pending: 'Plan not started',
  started: 'Planning',
  approved: 'Plan approved',
  completed: 'Plan approved',
}

export const RUN_META: Record<RunStatus, StatusMeta> = {
  queued: { label: 'Queued', lamp: 'var(--lamp-queued)', description: 'Persisted but no session started (tmux unavailable)' },
  running: { label: 'Running', lamp: 'var(--lamp-running)', description: 'The agent session is active' },
  completed: { label: 'Completed', lamp: 'var(--lamp-done)', description: 'Reported success' },
  failed: { label: 'Failed', lamp: 'var(--lamp-blocked)', description: 'Reported failure' },
  blocked: { label: 'Blocked', lamp: 'var(--lamp-hold)', description: 'Reported a blocker; still active' },
  stopped: { label: 'Stopped', lamp: 'var(--lamp-consolidated)', description: 'Stopped or superseded' },
}

export const NOTIFICATION_META: Record<string, { label: string; call: string }> = {
  task_completed: { label: 'Completed, needs review', call: 'Review needed' },
  task_failed: { label: 'Run failed', call: 'Run failed' },
  task_blocked: { label: 'Blocked', call: 'Blocked' },
  session_died: { label: 'Session ended unexpectedly', call: 'Session ended' },
}

export const PRIORITIES = ['P0', 'P1', 'P2', 'P3', 'P4', 'P5']

export const EVENT_TYPES = [
  'plan_completed',
  'plan_approved',
  'progress',
  'coding',
  'execution_started',
  'blocked',
  'unblocked',
  'review_requested',
  'fixing',
] as const

export const KNOWLEDGE_CATEGORIES = ['patterns', 'decisions', 'entities', 'issues', 'conventions'] as const

export function statusLamp(status: string): string {
  return STATUS_META[status as TaskStatus]?.lamp ?? 'var(--lamp-off)'
}

export function statusLabel(status: string): string {
  return STATUS_META[status as TaskStatus]?.label ?? status
}

export function runLamp(status: string): string {
  return RUN_META[status as RunStatus]?.lamp ?? 'var(--lamp-off)'
}

export function isTerminal(status: string, phase: string): boolean {
  return status === 'Completed' || status === 'Consolidated' || phase === 'archived' || phase === 'consolidated'
}

/** Classify an event type into a coarse group used for colour and filtering. */
export function eventGroup(type: string): 'run' | 'agent' | 'review' | 'status' | 'lifecycle' | 'other' {
  if (type.startsWith('RUN_')) return 'run'
  if (type.startsWith('AGENT_') || type === 'PROGRESS' || type === 'OPERATOR_MESSAGE') return 'agent'
  if (type.startsWith('REVIEW_') || type === 'MERGED') return 'review'
  if (type.startsWith('STATUS_')) return 'status'
  if (type.startsWith('PHASE_') || type === 'PLAN_APPROVED') return 'lifecycle'
  return 'other'
}
