<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CirclePlay, Kanban, Plus, Search } from 'lucide-vue-next'
import { columnsFor, dropPlan, matchesFilters, type Grouping } from '@/lib/board'
import { PRIORITIES } from '@/lib/status'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import { usePrefs } from '@/stores/prefs'
import { useToasts } from '@/stores/toasts'
import AppButton from '@/components/base/AppButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LampDot from '@/components/base/LampDot.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import ToggleSwitch from '@/components/base/ToggleSwitch.vue'
import KanbanColumn from '@/components/board/KanbanColumn.vue'
import WorkspaceProblem from '@/components/layout/WorkspaceProblem.vue'

const live = useLive()
const prefs = usePrefs()
const dialogs = useDialogs()
const toasts = useToasts()
const route = useRoute()
const router = useRouter()
const dragging = ref<number | null>(null)
const hovered = ref<string | null>(null)

const filtered = computed(() =>
  live.tasks.filter((task) =>
    matchesFilters(task, {
      search: prefs.values.search,
      agent: prefs.values.agentFilter,
      priority: prefs.values.priorityFilter,
      repository: prefs.values.repositoryFilter,
    }),
  ),
)
const columns = computed(() =>
  columnsFor(filtered.value, prefs.values.grouping, live.agents, {
    showFinished: prefs.values.showFinished,
    dragging: dragging.value !== null,
  }),
)
const draggedTask = computed(() => (dragging.value !== null ? live.taskMap.get(dragging.value) : undefined))
const selected = computed(() => (route.query.task ? Number(route.query.task) : null))

const summary = computed(() => {
  const tasks = live.tasks
  return {
    working: tasks.filter((task) => task.derived.session?.alive && task.derived.active_run).length,
    review: tasks.filter((task) => task.status === 'MR in Review').length,
    blocked: tasks.filter((task) => task.status === 'Blocked').length,
    queued: tasks.filter((task) => task.status === 'Queued').length,
  }
})

function hint(column: string) {
  const task = draggedTask.value
  if (!task) return null
  const plan = dropPlan(task, prefs.values.grouping, column)
  return plan.allowed ? { allowed: true, label: plan.label } : { allowed: false, label: plan.reason }
}

function onDragStart(event: DragEvent) {
  const card = (event.target as HTMLElement | null)?.closest<HTMLElement>('[data-task]')
  dragging.value = card ? Number(card.dataset.task) : null
  hovered.value = null
}

// A column that refuses a card never receives the drop, so explain why when the drag ends there.
function onDragEnd() {
  const task = draggedTask.value
  const column = hovered.value
  dragging.value = null
  hovered.value = null
  if (!task || column === null) return
  const plan = dropPlan(task, prefs.values.grouping, column)
  if (!plan.allowed && plan.reason !== 'Already here' && plan.reason !== 'Already assigned here') {
    toasts.push({ tone: 'info', title: `Task ${task.task_number} stays where it is`, detail: plan.reason })
  }
}

function onDrop(taskNumber: number, column: string) {
  dragging.value = null
  hovered.value = null
  const task = live.taskMap.get(taskNumber)
  if (!task) return
  const plan = dropPlan(task, prefs.values.grouping, column)
  if (plan.allowed) dialogs.openAction(plan.action, taskNumber, plan.overrides)
  else toasts.push({ tone: 'info', title: `Task ${taskNumber} stays where it is`, detail: plan.reason })
}

function openTask(number: number) {
  void router.push({ path: route.path, query: { ...route.query, task: String(number) } })
}
</script>

<template>
  <div class="board-page">
    <header class="head">
      <div class="title">
        <h1>Board</h1>
        <p class="summary" aria-live="polite">
          <span><LampDot color="var(--lamp-running)" :lit="summary.working > 0" :size="8" /> {{ summary.working }} agent{{ summary.working === 1 ? '' : 's' }} working</span>
          <span><LampDot color="var(--lamp-review)" :size="8" /> {{ summary.review }} in review</span>
          <span><LampDot color="var(--lamp-blocked)" :lit="summary.blocked > 0" :size="8" /> {{ summary.blocked }} blocked</span>
          <span><LampDot color="var(--lamp-queued)" :size="8" /> {{ summary.queued }} queued</span>
        </p>
      </div>
      <div class="filters">
        <label class="search">
          <Search :size="15" aria-hidden="true" />
          <span class="visually-hidden">Search tasks</span>
          <input v-model="prefs.values.search" type="search" placeholder="Search number, title, branch, note" />
        </label>
        <label class="visually-hidden" for="filter-agent">Agent</label>
        <select id="filter-agent" v-model="prefs.values.agentFilter" class="filter">
          <option value="">Every agent</option>
          <option value="-">Unassigned</option>
          <option v-for="agent in live.agents" :key="agent.alias" :value="agent.alias">{{ agent.alias }}</option>
        </select>
        <label class="visually-hidden" for="filter-priority">Priority</label>
        <select id="filter-priority" v-model="prefs.values.priorityFilter" class="filter">
          <option value="">Any priority</option>
          <option v-for="priority in PRIORITIES" :key="priority" :value="priority">{{ priority }}</option>
        </select>
        <label class="visually-hidden" for="filter-repository">Repository</label>
        <select id="filter-repository" v-model="prefs.values.repositoryFilter" class="filter">
          <option value="">Every repository</option>
          <option v-for="repository in live.config?.repositories ?? []" :key="repository.name" :value="repository.name">{{ repository.name }}</option>
        </select>
        <SegmentedControl
          :model-value="prefs.values.grouping"
          :options="[
            { value: 'status', label: 'By status' },
            { value: 'phase', label: 'By lifecycle' },
            { value: 'agent', label: 'By agent' },
          ]"
          label="Group by"
          @update:model-value="prefs.values.grouping = $event as Grouping"
        />
        <ToggleSwitch v-model="prefs.values.showFinished" label="Show finished" />
        <span class="spacer" />
        <AppButton :icon="CirclePlay" :disabled="!live.config" @click="dialogs.openTrigger()">Trigger agents</AppButton>
      </div>
    </header>

    <WorkspaceProblem />

    <EmptyState v-if="live.config && !live.tasks.length" class="empty" :icon="Kanban" title="No tasks yet">
      Create a task, assign an agent, and trigger it. Its card moves across the board as the agent reports.
      <template v-if="!live.config.agents.length || !live.config.repositories.length">
        First, add {{ !live.config.agents.length ? 'an agent' : '' }}{{ !live.config.agents.length && !live.config.repositories.length ? ' and ' : '' }}{{ !live.config.repositories.length ? 'a repository' : '' }} in Settings.
      </template>
      <template #actions>
        <AppButton tone="primary" :icon="Plus" @click="dialogs.openTaskForm('create')">New task</AppButton>
        <RouterLink v-if="!live.config.agents.length || !live.config.repositories.length" to="/settings#configuration"><AppButton>Open settings</AppButton></RouterLink>
      </template>
    </EmptyState>

    <div
      v-else-if="live.config"
      class="columns"
      data-testid="board"
      @dragstart="onDragStart"
      @dragend="onDragEnd"
    >
      <KanbanColumn
        v-for="column in columns"
        :key="column.key"
        :column-key="column.key"
        :title="column.title"
        :color="column.color"
        :description="column.description"
        :tasks="column.tasks"
        :drop-hint="hint(column.key)"
        :selected-task="selected"
        @open="openTask"
        @drop="onDrop"
        @hover="hovered = $event"
      />
    </div>
    <p v-if="live.tasks.length && !filtered.length" class="muted none">No tasks match the filters.</p>
  </div>
</template>

<style scoped>
.board-page {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - var(--topbar-height));
  padding: var(--space-5) var(--space-5) var(--space-4);
}

.head {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.title {
  display: flex;
  align-items: baseline;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.summary {
  display: flex;
  gap: var(--space-4);
  margin: 0;
  color: var(--ink-2);
  font-size: var(--text-sm);
  flex-wrap: wrap;
}

.summary span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.search {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--ink-2);
}

.search input {
  border: 0;
  background: transparent;
  outline: none;
  width: 240px;
  color: var(--ink);
}

.filter {
  height: 34px;
  padding: 0 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  font-size: var(--text-sm);
}

.columns {
  flex: 1;
  display: flex;
  gap: var(--space-3);
  overflow-x: auto;
  padding-bottom: var(--space-3);
  align-items: stretch;
  scrollbar-width: thin;
}

.empty {
  max-width: 640px;
}

.none {
  margin-top: var(--space-4);
}
</style>
