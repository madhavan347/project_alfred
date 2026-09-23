<script setup lang="ts">
import { computed } from 'vue'
import { Bell, FileWarning, GitBranch, ScrollText } from 'lucide-vue-next'
import type { Task } from '@/api/types'
import { useLive } from '@/stores/live'
import { statusLamp } from '@/lib/status'
import { nextStep } from '@/lib/actions'
import LampDot from '@/components/base/LampDot.vue'
import TagChip from '@/components/base/TagChip.vue'
import RelativeTime from '@/components/base/RelativeTime.vue'
import JourneyBar from '@/components/misc/JourneyBar.vue'
import AgentChip from '@/components/misc/AgentChip.vue'

const props = defineProps<{ task: Task; selected?: boolean }>()
const emit = defineEmits<{ open: [number] }>()
const live = useLive()

const session = computed(() => props.task.derived.session)
const lampTitle = computed(() => {
  const run = props.task.derived.active_run
  if (session.value?.alive) {
    return `${props.task.status}; session ${session.value.name} is live running ${session.value.command || 'a process'}`
  }
  if (run) return `${props.task.status}; ${run.run_status} run without a live session`
  return props.task.status
})
const next = computed(() => nextStep(props.task))
const planLabel = computed(() => {
  const plan = props.task.derived.plan
  if (plan.awaiting_approval) return plan.reported ? 'Plan ready' : 'Planning'
  return props.task.planning_state === 'pending' ? 'Plan first' : 'Plan approved'
})
const agents = computed(() => props.task.derived.agents.slice(0, 3))
const priorityTone = computed(() =>
  props.task.priority === 'P0' ? 'danger' : props.task.priority === 'P1' ? 'brass' : 'default',
)

function dragStart(event: DragEvent) {
  event.dataTransfer?.setData('application/x-alfred-task', String(props.task.task_number))
  event.dataTransfer?.setData('text/plain', `#${props.task.task_number} ${props.task.title}`)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}
</script>

<template>
  <article
    class="card"
    :class="{ selected, busy: live.isBusy(session?.name) }"
    :style="{ '--status': statusLamp(task.status) }"
    draggable="true"
    tabindex="0"
    :data-task="task.task_number"
    :aria-label="`Task ${task.task_number}: ${task.title}, ${task.status}`"
    @dragstart="dragStart"
    @click="emit('open', task.task_number)"
    @keydown.enter.prevent="emit('open', task.task_number)"
  >
    <header class="top">
      <LampDot :color="statusLamp(task.status)" :lit="!!session?.alive" :pulse="live.isBusy(session?.name)" :label="lampTitle" />
      <span class="number">#{{ task.task_number }}</span>
      <TagChip :tone="priorityTone">{{ task.priority }}</TagChip>
      <span class="category truncate">{{ task.category }}</span>
      <span class="spacer" />
      <span v-if="task.derived.notifications.pending" class="signal brass" :title="`${task.derived.notifications.pending} notification(s) waiting`">
        <Bell :size="13" aria-hidden="true" />{{ task.derived.notifications.pending }}
      </span>
      <span v-if="task.derived.completion_pending" class="signal brass" title="Completion report waiting for the coordinator">
        <FileWarning :size="13" aria-hidden="true" />
      </span>
    </header>

    <h3 class="title">{{ task.title }}</h3>
    <p v-if="task.notes" class="note">{{ task.notes }}</p>

    <div class="progress">
      <JourneyBar :steps="task.derived.journey" compact />
      <p class="next" :class="{ call: next.action === 'continue' || next.action === 'review' }">
        {{ next.label || '—' }}
      </p>
    </div>

    <footer class="meta">
      <AgentChip v-for="agent in agents" :key="agent.alias" :agent="agent" :session="session?.name" />
      <TagChip v-if="task.execution_mode === 'plan-execution'" :tone="task.derived.plan.awaiting_approval && task.derived.plan.reported ? 'brass' : 'default'">
        <ScrollText :size="11" aria-hidden="true" />
        {{ planLabel }}
      </TagChip>
      <TagChip v-if="task.branch_name" mono :title="task.branch_name">
        <GitBranch :size="11" aria-hidden="true" />{{ task.branch_name }}
      </TagChip>
      <TagChip v-if="task.derived.dirty" tone="brass" :title="task.derived.worktrees.map((item) => `${item.repository}: ${item.changes} changed`).join(', ')">
        {{ task.derived.worktrees.reduce((sum, item) => sum + item.changes, 0) }} uncommitted
      </TagChip>
      <span class="spacer" />
      <RelativeTime class="updated" :value="task.updated_at" />
    </footer>
  </article>
</template>

<style scoped>
.card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 10px 12px 10px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--panel);
  cursor: pointer;
  text-align: left;
}

.card::before {
  content: '';
  position: absolute;
  left: -1px;
  top: -1px;
  bottom: -1px;
  width: 4px;
  border-radius: var(--radius) 0 0 var(--radius);
  background: var(--status);
}

.card:hover {
  border-color: var(--line-strong);
}

.card.selected {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.card:active {
  cursor: grabbing;
}

.top {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.number {
  font-weight: 750;
  font-size: var(--text-sm);
}

.category {
  font-size: var(--text-xs);
  color: var(--ink-3);
  min-width: 0;
}

.signal {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--text-xs);
  font-weight: 700;
}

.signal.brass {
  color: var(--brass);
}

.title {
  font-size: var(--text-base);
  font-weight: 650;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.note {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--ink-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}

.progress {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.next {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.next.call {
  color: var(--brass);
  font-weight: 650;
}

.meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  min-width: 0;
}

.updated {
  font-size: var(--text-xs);
  color: var(--ink-3);
}
</style>
