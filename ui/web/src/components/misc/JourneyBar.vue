<script setup lang="ts">
import { computed } from 'vue'
import type { JourneyStep } from '@/api/types'

/** Where a task sits in Alfred's delivery lifecycle; compact on cards, labelled in the drawer. */
const props = defineProps<{ steps: JourneyStep[]; compact?: boolean }>()
const current = computed(() => props.steps.find((step) => step.state === 'current' || step.state === 'blocked'))
const done = computed(() => props.steps.filter((step) => step.state === 'done').length)
</script>

<template>
  <div v-if="compact" class="bar" :aria-label="`Lifecycle: ${done} of ${steps.length} steps done`">
    <span
      v-for="step in steps"
      :key="step.key"
      class="segment"
      :class="step.state"
      :title="`${step.label}: ${step.state}`"
    />
  </div>
  <ol v-else class="stepper" aria-label="Lifecycle">
    <li v-for="step in steps" :key="step.key" class="step" :class="step.state" :aria-current="step === current ? 'step' : undefined">
      <span class="dot" aria-hidden="true" />
      <span class="label">{{ step.label }}</span>
    </li>
  </ol>
</template>

<style scoped>
.bar {
  display: flex;
  gap: 2px;
}

.segment {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: var(--panel-3);
}

.segment.done {
  background: var(--lamp-done);
}

.segment.current {
  background: var(--accent);
}

.segment.blocked {
  background: var(--lamp-blocked);
}

.segment.skipped {
  background: repeating-linear-gradient(90deg, var(--panel-3) 0 3px, transparent 3px 5px);
}

.stepper {
  display: flex;
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.step {
  position: relative;
  flex: 1;
  min-width: 92px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding-right: 8px;
  color: var(--ink-3);
  font-size: var(--text-xs);
  font-weight: 600;
}

.step::before {
  content: '';
  position: absolute;
  top: 5px;
  left: 14px;
  right: 0;
  height: 2px;
  background: var(--line);
}

.step:last-child::before {
  display: none;
}

.dot {
  position: relative;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--line-strong);
  background: var(--panel);
}

.done {
  color: var(--ink-2);
}

.done .dot {
  background: var(--lamp-done);
  border-color: var(--lamp-done);
}

.done::before {
  background: var(--lamp-done);
}

.current {
  color: var(--ink);
}

.current .dot {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.blocked {
  color: var(--danger);
}

.blocked .dot {
  border-color: var(--lamp-blocked);
  background: var(--danger-soft);
}

.skipped {
  text-decoration: line-through;
}
</style>
