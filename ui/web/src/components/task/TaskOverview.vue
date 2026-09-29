<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BellRing, CircleCheck, CircleSlash, MonitorPlay } from 'lucide-vue-next'
import { api } from '@/api/http'
import type { TaskDetail } from '@/api/types'
import { absolute, duration, humanize } from '@/lib/format'
import { NOTIFICATION_META, PHASE_META, PLANNING_LABELS, RUN_META, runLamp, statusLamp } from '@/lib/status'
import { useRequest } from '@/composables/useRequest'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'
import KeyValue from '@/components/base/KeyValue.vue'
import LampDot from '@/components/base/LampDot.vue'
import MarkdownView from '@/components/base/MarkdownView.vue'
import RelativeTime from '@/components/base/RelativeTime.vue'
import TagChip from '@/components/base/TagChip.vue'
import AgentChip from '@/components/misc/AgentChip.vue'
import ScreenPreview from '@/components/terminal/ScreenPreview.vue'

const props = defineProps<{ detail: TaskDetail }>()
const emit = defineEmits<{ tab: [string] }>()
const live = useLive()
const dialogs = useDialogs()
const route = useRoute()
const router = useRouter()
const { pending, run } = useRequest()

const task = computed(() => props.detail.task)
const derived = computed(() => task.value.derived)
const activeRun = computed(() => derived.value.active_run)
const session = computed(() => derived.value.session)
const required = computed(() => live.config?.knowledge.required_completion_entries ?? 0)
const pendingNotifications = computed(() => props.detail.notifications.filter((item) => !item.acknowledged))

const details = computed(() => [
  { label: 'Category', value: task.value.category },
  { label: 'Priority', value: task.value.priority },
  { label: 'Deadline', value: task.value.deadline },
  { label: 'Execution', value: task.value.execution_mode === 'plan-execution' ? 'Plan first, then execute' : 'Direct' },
  { label: 'Planning', value: PLANNING_LABELS[task.value.planning_state] },
  { label: 'Dispatch', value: task.value.dispatch_mode === 'queued' ? 'Queued for trigger all' : 'Triggered explicitly' },
  { label: 'Worktrees', value: task.value.worktree_mode === 'enabled' ? 'Isolated per repository' : 'Disabled (workspace root)' },
  { label: 'Branch', value: task.value.branch_name, mono: true },
  { label: 'Repositories', value: task.value.target_repositories.join(', ') || 'Default selection' },
  { label: 'Lifecycle', value: PHASE_META[task.value.lifecycle_phase].label },
  { label: 'In run queue', value: derived.value.queued ? 'Yes' : 'No' },
  { label: 'Created', value: absolute(task.value.created_at) },
  { label: 'Updated', value: absolute(task.value.updated_at) },
])

function openTask(number: number) {
  void router.push({ path: route.path, query: { ...route.query, task: String(number), tab: 'overview' } })
}

async function processCompletions() {
  await run(() => api.post('/coordinator/once'), { command: 'alfred coordinator once' })
}

async function acknowledge() {
  await run(() => api.post('/notifications/ack', { task: task.value.task_number }), {
    command: `alfred notifications ack --task ${task.value.task_number}`,
  })
}
</script>

<template>
  <div class="overview">
    <div class="main">
      <section class="panel">
        <header class="panel-header"><h3>Description</h3></header>
        <div class="panel-body"><MarkdownView :source="task.description" /></div>
      </section>

      <section v-if="task.notes" class="panel">
        <header class="panel-header"><h3>Latest note</h3></header>
        <div class="panel-body"><MarkdownView :source="task.notes" /></div>
      </section>

      <section class="panel">
        <header class="panel-header"><h3>Details</h3></header>
        <div class="panel-body"><KeyValue :items="details" /></div>
      </section>

      <section v-if="detail.dependencies.length || detail.dependents.length" class="panel">
        <header class="panel-header"><h3>Related tasks</h3></header>
        <div class="panel-body related">
          <div v-if="detail.dependencies.length">
            <h4>Depends on</h4>
            <ul>
              <li v-for="item in detail.dependencies" :key="item.task_number">
                <button type="button" class="link" :disabled="!item.exists" @click="openTask(item.task_number)">
                  <LampDot :color="statusLamp(item.status)" :size="8" />
                  #{{ item.task_number }} {{ item.exists ? item.title : '(not found)' }}
                </button>
                <span class="faint small">{{ item.status }}</span>
              </li>
            </ul>
          </div>
          <div v-if="detail.dependents.length">
            <h4>Needed by</h4>
            <ul>
              <li v-for="item in detail.dependents" :key="item.task_number">
                <button type="button" class="link" @click="openTask(item.task_number)">
                  <LampDot :color="statusLamp(item.status)" :size="8" />
                  #{{ item.task_number }} {{ item.title }}
                </button>
                <span class="faint small">{{ item.status }}</span>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </div>

    <aside class="side">
      <section class="panel now">
        <header class="panel-header">
          <h3>Right now</h3>
          <span class="spacer" />
          <AppButton v-if="session?.alive" size="sm" :icon="MonitorPlay" @click="emit('tab', 'terminal')">Open terminal</AppButton>
        </header>
        <div class="panel-body stack">
          <template v-if="activeRun">
            <p class="run">
              <LampDot :color="runLamp(activeRun.run_status)" :lit="!!session?.alive" :pulse="live.isBusy(session?.name)" />
              <strong>{{ RUN_META[activeRun.run_status].label }}</strong>
              <span class="muted">{{ activeRun.phase }} phase with {{ activeRun.agent_alias }}</span>
            </p>
            <KeyValue
              :items="[
                { label: 'Started', value: absolute(activeRun.started_at) },
                { label: 'Elapsed', value: duration(activeRun.started_at) },
                { label: 'Session', value: activeRun.session_name, mono: true },
                { label: 'Session state', value: session?.alive ? `live, running ${session.command || 'a process'}` : activeRun.session_status },
                { label: 'Last event', value: absolute(activeRun.last_event_at) },
              ]"
            />
            <p v-if="activeRun.run_status === 'queued'" class="muted small">
              {{ RUN_META.queued.description }}. Trigger again once tmux is available.
            </p>
          </template>
          <p v-else class="muted">No active run.<template v-if="derived.latest_run"> The last run {{ RUN_META[derived.latest_run.run_status].label.toLowerCase() }} <RelativeTime :value="derived.latest_run.ended_at || derived.latest_run.last_event_at" />.</template></p>
          <button v-if="session?.alive" type="button" class="screen-button" title="Open the terminal" @click="emit('tab', 'terminal')">
            <ScreenPreview :session="session.name" :max-font="9" />
          </button>
        </div>
      </section>

      <section class="panel">
        <header class="panel-header">
          <h3>Agents</h3>
          <span class="spacer" />
          <AppButton size="sm" tone="quiet" @click="emit('tab', 'agents')">Details</AppButton>
        </header>
        <div class="panel-body agents">
          <AgentChip v-for="agent in derived.agents" :key="agent.alias" :agent="agent" :session="session?.name" detailed />
          <p v-if="!derived.agents.length" class="muted small">
            No agent yet.
            <AppButton size="sm" @click="dialogs.openAction('assign', task.task_number)">Assign one</AppButton>
          </p>
        </div>
      </section>

      <section class="panel">
        <header class="panel-header"><h3>Review</h3></header>
        <div class="panel-body stack">
          <p class="check" :class="derived.approved_since_last_work ? 'ok' : 'no'">
            <CircleCheck v-if="derived.approved_since_last_work" :size="16" aria-hidden="true" />
            <CircleSlash v-else :size="16" aria-hidden="true" />
            {{
              derived.approved_since_last_work
                ? 'Approved after the latest work, so it can be merged.'
                : 'No approval since the latest work. Merge needs a fresh review approval.'
            }}
          </p>
          <p class="check" :class="derived.knowledge_count >= required ? 'ok' : 'no'">
            <CircleCheck v-if="derived.knowledge_count >= required" :size="16" aria-hidden="true" />
            <CircleSlash v-else :size="16" aria-hidden="true" />
            {{ derived.knowledge_count }} knowledge entr{{ derived.knowledge_count === 1 ? 'y' : 'ies' }}; successful completion needs {{ required }}.
          </p>
          <div v-if="derived.completion_pending" class="waiting">
            <p class="check no">
              <BellRing :size="16" aria-hidden="true" /> A completion report is waiting for the coordinator.
            </p>
            <AppButton size="sm" tone="brass" :loading="pending" @click="processCompletions">Process now</AppButton>
          </div>
        </div>
      </section>

      <section v-if="pendingNotifications.length" class="panel calls">
        <header class="panel-header">
          <h3>Notifications</h3>
          <span class="spacer" />
          <AppButton size="sm" tone="brass" :loading="pending" @click="acknowledge">Acknowledge</AppButton>
        </header>
        <ul class="panel-body notes">
          <li v-for="item in pendingNotifications" :key="item.notification_id">
            <strong>{{ NOTIFICATION_META[item.notification_type]?.label ?? humanize(item.notification_type) }}</strong>
            <span class="faint small"> <RelativeTime :value="item.created_at" /></span>
            <p v-if="item.details.summary || item.details.message" class="small">{{ item.details.summary || item.details.message }}</p>
            <ul v-if="item.details.validation_issues?.length" class="issues">
              <li v-for="issue in item.details.validation_issues" :key="issue">{{ issue }}</li>
            </ul>
          </li>
        </ul>
      </section>

      <section v-if="detail.drift.length" class="panel">
        <header class="panel-header">
          <h3>Tracker drift</h3>
          <span class="spacer" />
          <AppButton size="sm" @click="dialogs.openAction('sync_task', task.task_number)">Reconcile</AppButton>
        </header>
        <ul class="panel-body issues">
          <li v-for="issue in detail.drift" :key="issue">{{ issue }}</li>
        </ul>
      </section>

      <p class="tags">
        <TagChip v-if="derived.transcripts" tone="accent">{{ derived.transcripts }} transcript{{ derived.transcripts === 1 ? '' : 's' }}</TagChip>
        <TagChip>{{ derived.event_count }} event{{ derived.event_count === 1 ? '' : 's' }}</TagChip>
        <TagChip>{{ derived.run_count }} run{{ derived.run_count === 1 ? '' : 's' }}</TagChip>
      </p>
    </aside>
  </div>
</template>

<style scoped>
.overview {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 1fr);
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5) var(--space-6);
}

.main,
.side {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-width: 0;
}

.run {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0;
}

.screen-button {
  display: block;
  width: 100%;
  border: 0;
  padding: 0;
  background: none;
  cursor: pointer;
  text-align: left;
}

.agents {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.check {
  display: flex;
  gap: 8px;
  margin: 0;
  font-size: var(--text-sm);
}

.check.ok {
  color: var(--ok);
}

.check.no {
  color: var(--brass);
}

.calls {
  border-color: var(--brass-line);
}

.waiting {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.notes {
  list-style: none;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.notes p {
  margin: 2px 0 0;
}

.issues {
  margin: 4px 0 0;
  padding-left: 1.2em;
  color: var(--danger);
  font-size: var(--text-sm);
}

.related {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.related ul {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.related li {
  display: flex;
  gap: 8px;
  align-items: center;
}

.link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: none;
  color: var(--accent);
  cursor: pointer;
  padding: 0;
  font-weight: 600;
  text-align: left;
}

.link:disabled {
  color: var(--ink-3);
  cursor: default;
}

.tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: 0;
}

@media (max-width: 980px) {
  .overview {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
