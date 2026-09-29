<script setup lang="ts">
import { ref } from 'vue'
import type { Task } from '@/api/types'
import TaskCard from './TaskCard.vue'
import LampDot from '@/components/base/LampDot.vue'

/** One board column. While a card is dragged it shows whether dropping here is possible. */
const props = defineProps<{
  columnKey: string
  title: string
  color: string
  description?: string
  tasks: Task[]
  dropHint?: { allowed: boolean; label: string } | null
  selectedTask?: number | null
}>()
const emit = defineEmits<{ open: [number]; drop: [task: number, column: string]; hover: [column: string] }>()
const over = ref(false)

function onDragOver(event: DragEvent) {
  if (!event.dataTransfer?.types.includes('application/x-alfred-task')) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = props.dropHint?.allowed ? 'move' : 'none'
  over.value = true
  emit('hover', props.columnKey)
}

function onDrop(event: DragEvent) {
  over.value = false
  const value = event.dataTransfer?.getData('application/x-alfred-task')
  if (!value) return
  event.preventDefault()
  emit('drop', Number(value), props.columnKey)
}
</script>

<template>
  <section
    class="column"
    :class="{ over, allowed: dropHint?.allowed, denied: dropHint && !dropHint.allowed, empty: !tasks.length }"
    :aria-label="`${title}, ${tasks.length} task${tasks.length === 1 ? '' : 's'}`"
    :data-column="columnKey"
    @dragover="onDragOver"
    @dragleave="over = false"
    @drop="onDrop"
  >
    <header class="head" :title="description">
      <LampDot :color="color" :size="9" />
      <h2 class="name">{{ title }}</h2>
      <span class="count">{{ tasks.length }}</span>
    </header>
    <p v-if="dropHint" class="hint" :class="{ allowed: dropHint.allowed }">{{ dropHint.label }}</p>
    <TransitionGroup tag="div" name="card" class="cards">
      <TaskCard
        v-for="task in tasks"
        :key="task.task_number"
        :task="task"
        :selected="selectedTask === task.task_number"
        @open="emit('open', $event)"
      />
    </TransitionGroup>
    <p v-if="!tasks.length && !dropHint" class="empty">No tasks</p>
  </section>
</template>

<style scoped>
.column {
  display: flex;
  flex-direction: column;
  flex: 0 0 300px;
  width: 300px;
  min-height: 100%;
  padding: 10px 8px 12px;
  border-radius: var(--radius-l);
  background: color-mix(in srgb, var(--panel-2) 55%, transparent);
  border: 1px solid transparent;
  transition:
    background 120ms var(--ease),
    border-color 120ms var(--ease);
}

.column.empty {
  flex-basis: 176px;
  width: 176px;
}

.column.allowed {
  border-color: color-mix(in srgb, var(--accent) 40%, transparent);
  background: color-mix(in srgb, var(--accent-soft) 55%, transparent);
}

.column.denied {
  opacity: 0.6;
}

.column.over.allowed {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 4px 8px;
}

.name {
  font-size: var(--text-sm);
  font-weight: 700;
  font-stretch: 82%;
  color: var(--ink);
}

.count {
  margin-left: auto;
  font-size: var(--text-xs);
  font-weight: 700;
  color: var(--ink-2);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0 7px;
}

.hint {
  margin: 0 4px 8px;
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.hint.allowed {
  color: var(--accent);
  font-weight: 650;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty {
  margin: 4px;
  font-size: var(--text-xs);
  color: var(--ink-3);
}

.card-move,
.card-enter-active,
.card-leave-active {
  transition:
    transform 260ms var(--ease),
    opacity 200ms var(--ease);
}

.card-enter-from,
.card-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.card-leave-active {
  position: absolute;
  width: 284px;
}
</style>
