<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CirclePlay, History } from 'lucide-vue-next'
import type { RunStatus } from '@/api/types'
import { alfredCommand } from '@/lib/cli'
import { duration, shortId } from '@/lib/format'
import { RUN_META, runLamp } from '@/lib/status'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'
import CommandLine from '@/components/base/CommandLine.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LampDot from '@/components/base/LampDot.vue'
import RelativeTime from '@/components/base/RelativeTime.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import WorkspaceProblem from '@/components/layout/WorkspaceProblem.vue'

/** Every run attempt across tasks, like `alfred run list`, plus the run queue. */
const live = useLive()
const dialogs = useDialogs()
const route = useRoute()
const router = useRouter()
const status = ref<'' | RunStatus>('')
const agent = ref('')

const runs = computed(() =>
  [...live.runs]
    .filter((run) => !status.value || run.run_status === status.value)
    .filter((run) => !agent.value || run.agent_alias === agent.value)
    .reverse(),
)
const agents = computed(() => [...new Set(live.runs.map((run) => run.agent_alias))].sort())
const queue = computed(() => live.snapshot?.queue ?? [])
const command = computed(() => alfredCommand('run', 'list', ['--status', status.value]))

function openTask(number: number, tab = 'agents') {
  void router.push({ path: route.path, query: { ...route.query, task: String(number), tab } })
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>Runs</h1>
        <p>Each dispatch of an agent is a run. Active runs are queued, running, or blocked; the rest are history.</p>
      </div>
      <span class="spacer" />
      <AppButton tone="primary" :icon="CirclePlay" :disabled="!live.config" @click="dialogs.openTrigger()">Trigger agents</AppButton>
    </header>

    <WorkspaceProblem />

    <section class="panel queue">
      <header class="panel-header">
        <h3>Run queue</h3>
        <span class="faint small">Persisted when tmux was unavailable (queue.json)</span>
        <span class="spacer" />
        <AppButton v-if="queue.length" size="sm" @click="dialogs.openTrigger(queue)">Dispatch queued</AppButton>
      </header>
      <div class="panel-body">
        <p v-if="!queue.length" class="muted small">Empty.</p>
        <p v-else class="row">
          <button v-for="number in queue" :key="number" type="button" class="task" @click="openTask(number, 'terminal')">
            #{{ number }} {{ live.taskMap.get(number)?.title }}
          </button>
        </p>
      </div>
    </section>

    <div class="filters">
      <SegmentedControl
        v-model="status"
        :options="[
          { value: '', label: 'All' },
          ...(['queued', 'running', 'blocked', 'completed', 'failed', 'stopped'] as RunStatus[]).map((value) => ({
            value,
            label: `${RUN_META[value].label} (${live.runs.filter((run) => run.run_status === value).length})`,
          })),
        ]"
        label="Run status"
      />
      <label class="visually-hidden" for="runs-agent">Agent</label>
      <select id="runs-agent" v-model="agent" class="control">
        <option value="">Every agent</option>
        <option v-for="name in agents" :key="name" :value="name">{{ name }}</option>
      </select>
      <CommandLine class="command" :command="command" />
    </div>

    <EmptyState v-if="!runs.length" :icon="History" title="No runs match">Triggering a task creates its first run.</EmptyState>
    <div v-else class="panel table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th scope="col">Status</th>
            <th scope="col">Task</th>
            <th scope="col">Agent</th>
            <th scope="col">Phase</th>
            <th scope="col">Started</th>
            <th scope="col">Duration</th>
            <th scope="col">Session</th>
            <th scope="col">Summary</th>
            <th scope="col"><span class="visually-hidden">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in runs" :key="run.run_id" :data-run="run.run_id">
            <td class="nowrap">
              <span class="row"><LampDot :color="runLamp(run.run_status)" :lit="live.sessionMap.has(run.session_name) && ['running', 'blocked'].includes(run.run_status)" :size="8" /> {{ RUN_META[run.run_status].label }}</span>
              <span class="mono faint tiny" :title="run.run_id">{{ shortId(run.run_id) }}</span>
            </td>
            <td>
              <button type="button" class="task" @click="openTask(run.task_number)">#{{ run.task_number }}</button>
              <span class="small">{{ live.taskMap.get(run.task_number)?.title }}</span>
            </td>
            <td class="nowrap">{{ run.agent_alias }}<br /><span class="faint tiny">{{ run.runtime_target }}</span></td>
            <td>{{ run.phase }}</td>
            <td class="nowrap"><RelativeTime :value="run.started_at" /></td>
            <td class="nowrap">{{ duration(run.started_at, run.ended_at || null) }}</td>
            <td class="nowrap">
              <span class="mono tiny">{{ run.session_name || '—' }}</span><br />
              <span class="faint tiny">{{ run.session_status }}{{ live.sessionMap.has(run.session_name) ? ', tmux live' : '' }}</span>
            </td>
            <td class="summary">{{ run.summary || '—' }}</td>
            <td class="nowrap">
              <AppButton v-if="['running', 'blocked', 'queued'].includes(run.run_status)" size="sm" tone="danger" @click="dialogs.openAction('stop', run.task_number)">Stop</AppButton>
              <AppButton v-if="live.sessionMap.has(run.session_name)" size="sm" tone="quiet" @click="openTask(run.task_number, 'terminal')">Terminal</AppButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.queue {
  margin-bottom: var(--space-4);
}

.filters {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.command {
  flex: 1;
  min-width: min(260px, 100%);
}

.control {
  height: 34px;
  padding: 0 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
}

.table-wrap {
  position: relative;
  overflow-x: auto;
}

.task {
  border: 0;
  background: var(--panel-2);
  border-radius: var(--radius-s);
  padding: 0 5px;
  margin-right: 6px;
  font-weight: 750;
  cursor: pointer;
}

.summary {
  max-width: 36ch;
  overflow-wrap: anywhere;
}
</style>
