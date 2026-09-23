<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import { statusLamp } from '@/lib/status'
import ModalDialog from '@/components/base/ModalDialog.vue'
import LampDot from '@/components/base/LampDot.vue'

/** Jump to any task or run a common action from the keyboard (⌘K or Ctrl-K). */
const dialogs = useDialogs()
const live = useLive()
const router = useRouter()
const route = useRoute()
const search = ref('')
const index = ref(0)
const input = ref<HTMLInputElement>()

interface Item {
  key: string
  label: string
  hint: string
  color?: string
  run: () => void
}

const commands = computed<Item[]>(() => [
  { key: 'new', label: 'New task', hint: 'Create a task', run: () => dialogs.openTaskForm('create') },
  { key: 'trigger', label: 'Trigger agents', hint: 'Dispatch tasks', run: () => dialogs.openTrigger() },
  { key: 'board', label: 'Board', hint: 'Go to the Kanban board', run: () => router.push('/') },
  { key: 'sessions', label: 'Agent sessions', hint: 'Watch every live agent', run: () => router.push('/sessions') },
  { key: 'feed', label: 'Live feed', hint: 'Every event as it happens', run: () => router.push('/feed') },
  { key: 'notifications', label: 'Notifications', hint: 'Reviews and alerts', run: () => router.push('/notifications') },
  { key: 'operations', label: 'Operations', hint: 'Coordinator, learner, tracker, state', run: () => router.push('/operations') },
  { key: 'settings', label: 'Settings', hint: 'Workspace, configuration, health checks', run: () => router.push('/settings') },
])

const items = computed<Item[]>(() => {
  const query = search.value.trim().toLowerCase()
  const tasks = live.tasks
    .filter((task) => !query || `#${task.task_number} ${task.title} ${task.branch_name}`.toLowerCase().includes(query.replace(/^#/, '')) || String(task.task_number) === query.replace(/^#/, ''))
    .slice(0, 12)
    .map((task) => ({
      key: `task-${task.task_number}`,
      label: `#${task.task_number} ${task.title}`,
      hint: `${task.status}${task.assigned_agent_alias ? `, ${task.assigned_agent_alias}` : ''}`,
      color: statusLamp(task.status),
      run: () => router.push({ path: route.path, query: { ...route.query, task: String(task.task_number) } }),
    }))
  const matching = commands.value.filter((item) => !query || item.label.toLowerCase().includes(query))
  return [...tasks, ...matching]
})

watch(
  () => dialogs.palette,
  async (open) => {
    if (!open) return
    search.value = ''
    index.value = 0
    await nextTick()
    input.value?.focus()
  },
)

watch(search, () => (index.value = 0))

function choose(item: Item | undefined) {
  if (!item) return
  dialogs.palette = false
  item.run()
}

function keydown(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    index.value = Math.min(items.value.length - 1, index.value + 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    index.value = Math.max(0, index.value - 1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    choose(items.value[index.value])
  }
}
</script>

<template>
  <ModalDialog :open="dialogs.palette" title="Jump to" width="560px" @close="dialogs.palette = false">
    <input
      ref="input"
      v-model="search"
      class="search"
      type="search"
      placeholder="Task number, title, branch, or a page"
      aria-label="Search tasks and actions"
      @keydown="keydown"
    />
    <ul class="results" role="listbox" aria-label="Results">
      <li
        v-for="(item, position) in items"
        :key="item.key"
        role="option"
        :aria-selected="position === index"
        class="result"
        :class="{ active: position === index }"
        @mouseenter="index = position"
        @click="choose(item)"
      >
        <LampDot v-if="item.color" :color="item.color" :size="8" />
        <span class="label">{{ item.label }}</span>
        <span class="hint">{{ item.hint }}</span>
      </li>
      <li v-if="!items.length" class="none">Nothing matches.</li>
    </ul>
  </ModalDialog>
</template>

<style scoped>
.search {
  width: 100%;
  height: 40px;
  padding: 0 12px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  font-size: var(--text-md);
}

.results {
  list-style: none;
  margin: var(--space-3) 0 0;
  padding: 0;
  max-height: 50vh;
  overflow-y: auto;
}

.result {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius);
  cursor: pointer;
}

.result.active {
  background: var(--accent-soft);
}

.label {
  flex: 1;
  min-width: 0;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hint {
  color: var(--ink-2);
  font-size: var(--text-sm);
  white-space: nowrap;
}

.none {
  padding: 8px 10px;
  color: var(--ink-2);
}
</style>
