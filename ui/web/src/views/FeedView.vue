<script setup lang="ts">
import { computed, ref, watch, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Pause, Play, Radio } from 'lucide-vue-next'
import { api, query } from '@/api/http'
import type { TaskEvent } from '@/api/types'
import { clockTime } from '@/lib/format'
import { eventGroup } from '@/lib/status'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import EventRow from '@/components/misc/EventRow.vue'
import WorkspaceProblem from '@/components/layout/WorkspaceProblem.vue'

/** Every event as it happens, from the UI, the CLI, and agents alike. */
const live = useLive()
const route = useRoute()
const router = useRouter()
const paused = ref(false)
const frozen = ref<TaskEvent[]>([])
const older = ref<TaskEvent[]>([])
const loadingOlder = ref(false)
const group = ref('all')
const taskFilter = ref('')
const search = ref('')
const seen = ref<number | null>(null)

watch(paused, (value) => {
  if (value) frozen.value = [...live.events]
})

const source = computed(() => (paused.value ? frozen.value : live.events))
const events = computed(() => {
  const combined = [...older.value, ...source.value]
  const needle = search.value.trim().toLowerCase()
  return combined
    .filter((event) => group.value === 'all' || eventGroup(event.event_type) === group.value)
    .filter((event) => !taskFilter.value || String(event.task_number) === taskFilter.value)
    .filter(
      (event) =>
        !needle || `${event.actor} ${event.event_type} ${event.details}`.toLowerCase().includes(needle),
    )
    .reverse()
})
const oldestIndex = computed(() => (older.value[0] ?? source.value[0])?.index ?? 0)
const total = computed(() => live.snapshot?.event_count ?? 0)
const sessionChanges = computed(() => [...live.sessionLog].reverse().slice(0, 30))

// Events already present when the page opens are not highlighted; later arrivals are.
watchEffect(() => {
  if (seen.value === null && live.snapshot) seen.value = live.events.at(-1)?.index ?? -1
})

async function loadOlder() {
  loadingOlder.value = true
  try {
    const result = await api.get<{ events: TaskEvent[] }>(`/events${query({ before: oldestIndex.value, limit: 300 })}`)
    older.value = [...result.events, ...older.value]
  } finally {
    loadingOlder.value = false
  }
}

function openTask(number: number) {
  void router.push({ path: route.path, query: { ...route.query, task: String(number), tab: 'activity' } })
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>Live feed</h1>
        <p>
          Every task event as it is written, whether it came from this page, the command line, or an agent in its
          session. {{ total }} events recorded.
        </p>
      </div>
      <span class="spacer" />
      <AppButton :icon="paused ? Play : Pause" @click="paused = !paused">{{ paused ? 'Resume live updates' : 'Pause' }}</AppButton>
    </header>

    <WorkspaceProblem />

    <div class="layout">
      <section class="panel">
        <header class="panel-header filters">
          <Radio :size="16" aria-hidden="true" :class="{ on: !paused && live.connection === 'live' }" class="radio" />
          <SegmentedControl
            v-model="group"
            :options="[
              { value: 'all', label: 'All' },
              { value: 'run', label: 'Runs' },
              { value: 'agent', label: 'Agents' },
              { value: 'status', label: 'Status' },
              { value: 'review', label: 'Review' },
              { value: 'lifecycle', label: 'Lifecycle' },
              { value: 'other', label: 'Other' },
            ]"
            label="Event type"
          />
          <label class="visually-hidden" for="feed-task">Task</label>
          <select id="feed-task" v-model="taskFilter" class="control">
            <option value="">Every task</option>
            <option v-for="task in live.tasks" :key="task.task_number" :value="String(task.task_number)">#{{ task.task_number }} {{ task.title }}</option>
          </select>
          <input v-model="search" class="control grow" type="search" placeholder="Filter by actor or text" aria-label="Filter events" />
        </header>
        <ol class="panel-body events" aria-live="polite" data-testid="feed">
          <EventRow
            v-for="event in events"
            :key="event.index"
            :event="event"
            show-task
            :fresh="seen !== null && event.index > seen"
            @open-task="openTask"
          />
          <li v-if="!events.length" class="muted">No events yet.</li>
        </ol>
        <footer class="panel-body more">
          <AppButton v-if="oldestIndex > 0" size="sm" :loading="loadingOlder" @click="loadOlder">Load older events</AppButton>
        </footer>
      </section>

      <aside class="panel">
        <header class="panel-header"><h3>Sessions starting and ending</h3></header>
        <ul class="panel-body sessions">
          <li v-if="!sessionChanges.length" class="muted small note">Sessions that start or end while this page is open are listed here.</li>
          <li v-for="change in sessionChanges" :key="change.id" :class="change.change">
            <span class="time">{{ clockTime(change.time) }}</span>
            <span class="mono small">{{ change.name }}</span>
            <strong>{{ change.change }}</strong>
          </li>
        </ul>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: var(--space-4);
  align-items: start;
}

.filters {
  flex-wrap: wrap;
}

.radio {
  color: var(--ink-3);
}

.radio.on {
  color: var(--lamp-running);
}

.control {
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  font-size: var(--text-sm);
  max-width: 260px;
}

.grow {
  flex: 1;
  min-width: min(160px, 100%);
  max-width: none;
}

.events {
  list-style: none;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.more {
  padding-top: 0;
}

.sessions {
  list-style: none;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sessions li {
  display: grid;
  grid-template-columns: 70px 1fr auto;
  gap: 8px;
  align-items: baseline;
  font-size: var(--text-sm);
}

.sessions li.note {
  display: block;
}

.sessions .started strong {
  color: var(--ok);
}

.sessions .ended strong {
  color: var(--danger);
}

.time {
  color: var(--ink-3);
  font-size: var(--text-xs);
}

@media (max-width: 1100px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
