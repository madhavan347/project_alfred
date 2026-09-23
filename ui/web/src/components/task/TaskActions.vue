<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Ban,
  CheckCheck,
  ChevronDown,
  CirclePlay,
  GitCommitHorizontal,
  Hand,
  Pencil,
  Play,
  RotateCcw,
  Square,
  Upload,
} from 'lucide-vue-next'
import type { ActionName, Task } from '@/api/types'
import { nextStep } from '@/lib/actions'
import { useDialogs } from '@/stores/dialogs'
import AppButton from '@/components/base/AppButton.vue'

/** The task's primary next step, the common actions, and every other action in a menu. */
const props = defineProps<{ task: Task }>()
const dialogs = useDialogs()
const menuOpen = ref(false)
const root = ref<HTMLElement>()

const next = computed(() => nextStep(props.task))
const available = (name: ActionName) => props.task.derived.actions[name]

const quick = computed(() => {
  const buttons: { id: string; label: string; icon: unknown; tone?: 'primary' | 'danger' | 'brass'; overrides?: Record<string, unknown> }[] = []
  const add = (id: string, gate: ActionName, label: string, icon: unknown, tone?: 'primary' | 'danger' | 'brass', overrides?: Record<string, unknown>) => {
    if (available(gate).enabled) buttons.push({ id, label, icon, tone, overrides })
  }
  const primary = next.value.action
  if (primary) {
    const labels: Record<string, string> = {
      assign: 'Assign agent',
      continue: 'Approve plan',
      unblock: props.task.status === 'On Hold' ? 'Resume' : 'Unblock',
      trigger: props.task.derived.active_run?.run_status === 'queued' ? 'Dispatch again' : props.task.execution_mode === 'plan-execution' && props.task.planning_state === 'pending' ? 'Start planning' : 'Trigger agent',
      reopen: 'Reopen',
      review: 'Review',
      merge: 'Record merge',
      deploy: 'Record deployment',
      archive: 'Archive',
    }
    const gate = primary as ActionName
    if (available(gate)?.enabled) {
      buttons.push({ id: primary, label: labels[primary] ?? primary, icon: primary === 'continue' ? CheckCheck : Play, tone: primary === 'continue' || primary === 'review' ? 'brass' : 'primary' })
    }
  }
  // Offer the actions that fit where the task is; everything else stays in All actions.
  const status = props.task.status
  const seen = new Set(buttons.map((item) => item.id))
  const extra: [string, ActionName, string, unknown, ('danger' | undefined)?, boolean?][] = [
    ['trigger', 'trigger', 'Trigger', CirclePlay, undefined, status === 'Pending' || status === 'Queued'],
    ['stop', 'stop', 'Stop run', Square, 'danger'],
    ['review', 'review', 'Review', CheckCheck, undefined, status === 'MR in Review'],
    ['reopen', 'reopen', 'Reopen', RotateCcw, undefined, status === 'In Progress' || status === 'Pending'],
    ['commit', 'commit', 'Commit', GitCommitHorizontal],
    ['push', 'push', 'Push', Upload],
    ['block', 'block', 'Block', Ban, undefined, status !== 'MR in Review'],
    ['hold', 'hold', 'Hold', Hand, undefined, status === 'Pending' || status === 'Queued' || status === 'In Progress'],
  ]
  for (const [id, gate, label, icon, tone, fits = true] of extra) {
    if (fits && !seen.has(id)) add(id, gate, label, icon, tone)
  }
  return buttons.slice(0, 5)
})

const groups = computed(() => [
  {
    title: 'Run',
    items: [
      ['trigger', 'trigger', 'Trigger agent'],
      ['continue', 'continue', 'Approve plan and continue'],
      ['stop', 'stop', 'Stop run'],
      ['reopen', 'reopen', 'Reopen with a new attempt'],
      ['event', 'event', 'Record agent event'],
      ['complete', 'complete', 'Report completion'],
    ],
  },
  {
    title: 'Status',
    items: [
      ['start', 'start', 'Start work'],
      ['progress', 'progress', 'Record progress'],
      ['block', 'block', 'Block'],
      ['unblock', 'unblock', props.task.status === 'On Hold' ? 'Resume' : 'Unblock'],
      ['hold', 'hold', 'Put on hold'],
    ],
  },
  {
    title: 'Review and delivery',
    items: [
      ['review', 'review', 'Record review'],
      ['merge', 'merge', 'Record merge'],
      ['deploy', 'deploy', 'Record deployment'],
      ['archive', 'archive', 'Archive'],
      ['consolidate', 'consolidate', 'Consolidate'],
    ],
  },
  {
    title: 'Agent and code',
    items: [
      ['assign', 'assign', 'Assign agent'],
      ['reassign', 'reassign', 'Reassign agent'],
      ['worktree_create', 'worktree_create', 'Create worktrees'],
      ['commit', 'commit', 'Commit changes'],
      ['push', 'push', 'Push branch'],
      ['remove_worktrees', 'remove_worktrees', 'Remove worktrees'],
    ],
  },
  {
    title: 'Records',
    items: [
      ['knowledge', '', 'Add knowledge entry'],
      ['sync_task', '', 'Reconcile tracker rows'],
    ],
  },
])

function open(id: string, overrides: Record<string, unknown> = {}) {
  menuOpen.value = false
  dialogs.openAction(id, props.task.task_number, overrides)
}

function onDocumentClick(event: MouseEvent) {
  if (menuOpen.value && root.value && !root.value.contains(event.target as Node)) menuOpen.value = false
}
onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))
</script>

<template>
  <div ref="root" class="actions">
    <p v-if="next.label" class="next">
      Next: <strong>{{ next.label }}</strong>
    </p>
    <div class="buttons">
      <AppButton
        v-for="button in quick"
        :key="button.id"
        size="sm"
        :tone="button.tone ?? 'default'"
        :icon="button.icon as never"
        :data-action="button.id"
        @click="open(button.id, button.overrides)"
      >
        {{ button.label }}
      </AppButton>
      <AppButton size="sm" :icon="Pencil" data-action="edit" @click="dialogs.openTaskForm('edit', task.task_number)">Edit</AppButton>
      <div class="menu-anchor">
        <AppButton size="sm" :icon="ChevronDown" :aria-expanded="menuOpen" aria-haspopup="menu" data-action="more" @click.stop="menuOpen = !menuOpen">
          All actions
        </AppButton>
        <div v-if="menuOpen" class="menu" role="menu">
          <section v-for="group in groups" :key="group.title" class="group">
            <h4>{{ group.title }}</h4>
            <button
              v-for="[id, gate, label] in group.items"
              :key="id"
              type="button"
              role="menuitem"
              class="item"
              :class="{ disabled: gate && !available(gate as ActionName).enabled }"
              :title="gate && !available(gate as ActionName).enabled ? available(gate as ActionName).reason : ''"
              :data-menu-action="id"
              @click="open(id)"
            >
              <span>{{ label }}</span>
              <span v-if="gate && !available(gate as ActionName).enabled" class="why">{{ available(gate as ActionName).reason }}</span>
            </button>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.next {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--ink-2);
}

.next strong {
  color: var(--ink);
}

.buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-left: auto;
}

.menu-anchor {
  position: relative;
}

.menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  z-index: 20;
  width: 560px;
  max-width: calc(100vw - 48px);
  max-height: 70vh;
  overflow-y: auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-l);
  background: var(--panel);
  box-shadow: var(--shadow-float);
}

.group h4 {
  margin: 0 0 4px;
  font-size: var(--text-xs);
}

.item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 5px 8px;
  border-radius: var(--radius);
  text-align: left;
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}

.item:hover {
  background: var(--panel-2);
}

.item.disabled {
  color: var(--ink-3);
}

.why {
  font-weight: 400;
  font-size: var(--text-xs);
  color: var(--ink-3);
}
</style>
