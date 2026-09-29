<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight } from 'lucide-vue-next'
import { api } from '@/api/http'
import type { ReportRow, Reports } from '@/api/types'
import { humanSpan } from '@/lib/format'
import { PHASE_META, RUN_META, STATUS_META, TASK_STATUSES, statusLamp } from '@/lib/status'
import { errorMessage } from '@/composables/useRequest'
import { useLive } from '@/stores/live'
import CommandLine from '@/components/base/CommandLine.vue'
import LampDot from '@/components/base/LampDot.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import TagChip from '@/components/base/TagChip.vue'
import BarList from '@/components/charts/BarList.vue'
import ColumnChart from '@/components/charts/ColumnChart.vue'
import WorkspaceProblem from '@/components/layout/WorkspaceProblem.vue'

/** Alfred's four reports, plus throughput, cycle time, and workload views of the same state. */
const live = useLive()
const route = useRoute()
const router = useRouter()
const reports = ref<Reports | null>(null)
const failure = ref('')
const view = ref<'charts' | 'tables'>('charts')

async function load() {
  try {
    reports.value = await api.get<Reports>('/reports')
    failure.value = ''
  } catch (error) {
    failure.value = errorMessage(error)
  }
}

watch(() => live.snapshot?.generated_at, load, { immediate: true })

const velocity = computed(() => reports.value?.velocity ?? { completed: 0, total: 0 })
const share = computed(() => (velocity.value.total ? Math.round((velocity.value.completed / velocity.value.total) * 100) : 0))
const statusRows = computed(() =>
  TASK_STATUSES.map((status) => ({
    key: status,
    label: STATUS_META[status].label,
    value: reports.value?.by_status[status] ?? 0,
    lamp: STATUS_META[status].lamp,
  })).filter((row) => row.value > 0),
)
const phaseRows = computed(() =>
  Object.entries(reports.value?.by_phase ?? {}).map(([phase, value]) => ({
    key: phase,
    label: PHASE_META[phase as keyof typeof PHASE_META]?.label ?? phase,
    value,
    lamp: PHASE_META[phase as keyof typeof PHASE_META]?.lamp,
  })),
)
const agentRows = computed(() =>
  Object.entries(reports.value?.by_agent ?? {})
    .sort((left, right) => right[1] - left[1])
    .map(([agent, value]) => ({ key: agent, label: agent, value })),
)
const priorityRows = computed(() =>
  Object.entries(reports.value?.by_priority ?? {})
    .sort()
    .map(([priority, value]) => ({ key: priority, label: priority, value })),
)
const runRows = computed(() =>
  Object.entries(reports.value?.runs.by_status ?? {}).map(([status, value]) => ({
    key: status,
    label: RUN_META[status as keyof typeof RUN_META]?.label ?? status,
    value,
    lamp: RUN_META[status as keyof typeof RUN_META]?.lamp,
  })),
)
const durationRows = computed(() =>
  Object.entries(reports.value?.runs.average_hours_by_agent ?? {}).map(([agent, hours]) => ({
    key: agent,
    label: agent,
    value: hours,
  })),
)
const cycleRows = computed(() =>
  [...(reports.value?.cycle_times ?? [])]
    .sort((left, right) => right.hours - left.hours)
    .slice(0, 12)
    .map((row) => ({ key: String(row.task_number), label: `#${row.task_number} ${row.title}`, value: row.hours })),
)
const throughput = computed(() => (reports.value?.throughput ?? []).map((item) => ({ label: item.day, value: item.count })))

function openTask(number: number) {
  void router.push({ path: route.path, query: { ...route.query, task: String(number) } })
}

function rows(list: ReportRow[] | undefined) {
  return list ?? []
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>Reports</h1>
        <p>Read-only projections of the current task state, refreshed as it changes.</p>
      </div>
      <span class="spacer" />
      <SegmentedControl
        v-model="view"
        :options="[
          { value: 'charts', label: 'Charts' },
          { value: 'tables', label: 'Tables' },
        ]"
        label="Show as"
      />
    </header>

    <WorkspaceProblem />
    <p v-if="failure" class="failure">{{ failure }}</p>

    <div v-if="reports" class="grid">
      <section class="panel velocity">
        <header class="panel-header"><h3>Velocity</h3></header>
        <div class="panel-body">
          <p class="hero" data-testid="velocity">{{ velocity.completed }}<span>/{{ velocity.total }}</span></p>
          <p class="muted small">tasks completed or consolidated ({{ share }}%)</p>
          <div class="meter" role="meter" :aria-valuenow="velocity.completed" aria-valuemin="0" :aria-valuemax="velocity.total" aria-label="Completed tasks">
            <span :style="{ width: `${share}%` }" />
          </div>
          <CommandLine command="alfred report velocity" />
        </div>
      </section>

      <section class="panel">
        <header class="panel-header"><h3>Tasks by status</h3></header>
        <div class="panel-body">
          <BarList v-if="view === 'charts'" :rows="statusRows" caption="Number of tasks in each status" unit="tasks" />
          <table v-else class="table">
            <tbody>
              <tr v-for="row in statusRows" :key="row.key"><td>{{ row.label }}</td><td>{{ row.value }}</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel wide">
        <header class="panel-header">
          <h3>Finished per day</h3>
          <span class="faint small">Tasks reaching Completed, archived, or consolidated</span>
        </header>
        <div class="panel-body">
          <ColumnChart v-if="view === 'charts'" :points="throughput" caption="Tasks finished per day" unit="tasks" />
          <table v-else class="table">
            <tbody>
              <tr v-for="point in throughput" :key="point.label"><td>{{ point.label }}</td><td>{{ point.value }}</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <header class="panel-header"><h3>Workload by agent</h3></header>
        <div class="panel-body">
          <BarList v-if="view === 'charts'" :rows="agentRows" caption="Tasks assigned to each agent" unit="tasks" />
          <table v-else class="table">
            <tbody>
              <tr v-for="row in agentRows" :key="row.key"><td>{{ row.label }}</td><td>{{ row.value }}</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <header class="panel-header"><h3>Lifecycle and priority</h3></header>
        <div class="panel-body stack">
          <BarList :rows="phaseRows" caption="Tasks in each lifecycle phase" unit="tasks" />
          <BarList :rows="priorityRows" caption="Tasks at each priority" unit="tasks" />
        </div>
      </section>

      <section class="panel">
        <header class="panel-header"><h3>Runs</h3></header>
        <div class="panel-body stack">
          <BarList :rows="runRows" caption="Runs in each status" unit="runs" />
          <h4>Average finished run, by agent</h4>
          <BarList :rows="durationRows" caption="Average run length per agent" :format="(value) => humanSpan(value * 3600)" />
        </div>
      </section>

      <section class="panel">
        <header class="panel-header"><h3>Longest time to finish</h3></header>
        <div class="panel-body">
          <BarList :rows="cycleRows" caption="Hours from creation to finish" :format="(value) => humanSpan(value * 3600)" />
        </div>
      </section>

      <section class="panel wide">
        <header class="panel-header">
          <h3>Active today</h3>
          <span class="faint small">Every task that is not completed or consolidated</span>
        </header>
        <div class="panel-body stack table-scroll">
          <table class="table">
            <thead>
              <tr><th scope="col">Task</th><th scope="col">Status</th><th scope="col">Priority</th><th scope="col">Agent</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in rows(reports.today)" :key="row.task_number" class="clickable" @click="openTask(row.task_number)">
                <td><strong>#{{ row.task_number }}</strong> {{ row.title }}</td>
                <td class="nowrap"><span class="row"><LampDot :color="statusLamp(row.status)" :size="8" /> {{ row.status }}</span></td>
                <td>{{ row.priority }}</td>
                <td>{{ row.agent || '—' }}</td>
              </tr>
              <tr v-if="!reports.today.length"><td colspan="4" class="muted">Nothing active.</td></tr>
            </tbody>
          </table>
          <CommandLine command="alfred report today" />
        </div>
      </section>

      <section class="panel">
        <header class="panel-header">
          <h3>At risk</h3>
          <span class="faint small">Blocked, on hold, P0, or P1</span>
        </header>
        <div class="panel-body stack">
          <ul class="list">
            <li v-for="row in rows(reports.risk)" :key="row.task_number">
              <button type="button" class="link" @click="openTask(row.task_number)">#{{ row.task_number }} {{ row.title }}</button>
              <TagChip :tone="row.status === 'Blocked' ? 'danger' : row.priority === 'P0' ? 'danger' : 'brass'">{{ row.status }}, {{ row.priority }}</TagChip>
            </li>
            <li v-if="!reports.risk.length" class="muted">Nothing at risk.</li>
          </ul>
          <CommandLine command="alfred report risk" />
        </div>
      </section>

      <section class="panel">
        <header class="panel-header">
          <h3>Dependencies</h3>
          <span class="faint small">Descriptive only; they do not block dispatch</span>
        </header>
        <div class="panel-body stack">
          <ul class="list">
            <li v-for="row in rows(reports.dependency)" :key="row.task_number" class="dependency">
              <span class="chain">
                <template v-for="dependency in row.dependencies ?? []" :key="dependency">
                  <button type="button" class="link" @click="openTask(dependency)">
                    <LampDot :color="statusLamp(live.taskMap.get(dependency)?.status ?? '')" :size="7" /> #{{ dependency }}
                  </button>
                </template>
                <ArrowRight :size="14" aria-hidden="true" />
                <button type="button" class="link strong" @click="openTask(row.task_number)">#{{ row.task_number }} {{ row.title }}</button>
              </span>
            </li>
            <li v-if="!reports.dependency.length" class="muted">No task declares dependencies.</li>
          </ul>
          <CommandLine command="alfred report dependency" />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(380px, 100%), 1fr));
  grid-auto-flow: dense;
  gap: var(--space-4);
}

.wide {
  grid-column: span 2;
}

.hero {
  margin: 0;
  font-size: 3.5rem;
  font-weight: 700;
  font-stretch: 112%;
  line-height: 1;
}

.hero span {
  font-size: 1.6rem;
  color: var(--ink-2);
  font-weight: 600;
}

.meter {
  height: 10px;
  margin: var(--space-2) 0 var(--space-4);
  border-radius: 5px;
  background: var(--accent-soft);
  overflow: hidden;
}

.meter span {
  display: block;
  height: 100%;
  background: var(--accent);
  border-radius: 0 5px 5px 0;
}

.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.list li {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: none;
  padding: 0;
  color: var(--accent);
  font-weight: 600;
  cursor: pointer;
  text-align: left;
}

.link.strong {
  color: var(--ink);
}

.chain {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.clickable {
  cursor: pointer;
}

.failure {
  color: var(--danger);
}

@media (max-width: 900px) {
  .wide {
    grid-column: auto;
  }
}
</style>
