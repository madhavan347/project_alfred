<script setup lang="ts">
import { computed } from 'vue'
import type { TaskEvent } from '@/api/types'
import { absolute, clockTime, humanize } from '@/lib/format'
import { eventGroup } from '@/lib/status'
import RelativeTime from '@/components/base/RelativeTime.vue'

/** One task event: when, who, what kind, and the recorded details. */
const props = defineProps<{ event: TaskEvent; showTask?: boolean; fresh?: boolean }>()
const emit = defineEmits<{ openTask: [number] }>()
const group = computed(() => eventGroup(props.event.event_type))
const agent = computed(() => props.event.actor.startsWith('agent:'))
</script>

<template>
  <li class="event" :class="[group, { fresh }]" :data-event-type="event.event_type">
    <time class="when" :datetime="event.timestamp" :title="absolute(event.timestamp)">{{ clockTime(event.timestamp) }}</time>
    <div class="body">
      <div class="head">
        <button v-if="showTask" type="button" class="task" @click="emit('openTask', event.task_number)">#{{ event.task_number }}</button>
        <span class="type">{{ humanize(event.event_type) }}</span>
        <span class="actor mono" :class="{ agent }">{{ event.actor }}</span>
        <RelativeTime class="ago" :value="event.timestamp" />
      </div>
      <p v-if="event.details" class="details">{{ event.details }}</p>
    </div>
  </li>
</template>

<style scoped>
.event {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 12px;
  padding: 8px 0 8px 10px;
  border-left: 3px solid var(--line);
}

.event.run {
  border-left-color: var(--lamp-running);
}

.event.agent {
  border-left-color: var(--lamp-progress);
}

.event.review {
  border-left-color: var(--lamp-review);
}

.event.status {
  border-left-color: var(--lamp-queued);
}

.event.lifecycle {
  border-left-color: var(--lamp-done);
}

.event.fresh {
  animation: glow 2.4s var(--ease);
}

.when {
  font-size: var(--text-xs);
  color: var(--ink-3);
  padding-top: 2px;
  font-feature-settings: 'tnum' 1;
}

.head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.task {
  border: 0;
  background: var(--panel-2);
  border-radius: var(--radius-s);
  padding: 0 5px;
  font-weight: 750;
  font-size: var(--text-sm);
  cursor: pointer;
}

.type {
  font-weight: 650;
  font-size: var(--text-sm);
}

.actor {
  font-size: 11px;
  color: var(--ink-2);
  background: var(--panel-2);
  border-radius: var(--radius-s);
  padding: 0 5px;
}

.actor.agent {
  background: color-mix(in srgb, var(--lamp-progress) 14%, var(--panel));
  color: var(--ink);
}

.ago {
  font-size: var(--text-xs);
  color: var(--ink-3);
}

.details {
  margin: 3px 0 0;
  font-size: var(--text-sm);
  color: var(--ink-2);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@keyframes glow {
  from {
    background: var(--accent-soft);
  }
}
</style>
