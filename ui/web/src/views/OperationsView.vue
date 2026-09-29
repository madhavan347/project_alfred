<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BrainCircuit, Cog, Database, FileStack, Play, RefreshCw, Square, SquareTerminal, Table } from 'lucide-vue-next'
import { api } from '@/api/http'
import type { CompletionEntry, CompletionListing, PromptFile, TrackerListing } from '@/api/types'
import { absolute } from '@/lib/format'
import { alfredCommand } from '@/lib/cli'
import { errorMessage, useRequest } from '@/composables/useRequest'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'
import CommandLine from '@/components/base/CommandLine.vue'
import LampDot from '@/components/base/LampDot.vue'
import MarkdownView from '@/components/base/MarkdownView.vue'
import SelectInput from '@/components/base/SelectInput.vue'
import TabBar from '@/components/base/TabBar.vue'
import TagChip from '@/components/base/TagChip.vue'
import JsonBlock from '@/components/misc/JsonBlock.vue'
import ScreenPreview from '@/components/terminal/ScreenPreview.vue'
import WorkspaceProblem from '@/components/layout/WorkspaceProblem.vue'

/** The background machinery: coordinator, learner, completion handoffs, tracker, and raw state. */
const live = useLive()
const route = useRoute()
const router = useRouter()
const { pending, run } = useRequest()

const tab = computed({
  get: () => String(route.query.section ?? 'daemons'),
  set: (value: string) => void router.replace({ query: { ...route.query, section: value } }),
})
const tabs = [
  { key: 'daemons', label: 'Coordinator and learner', icon: Cog },
  { key: 'completions', label: 'Completion handoffs', icon: FileStack },
  { key: 'tracker', label: 'Markdown tracker', icon: Table },
  { key: 'state', label: 'State files', icon: Database },
]

const coordinator = computed(() => live.snapshot?.coordinator)
const learner = computed(() => live.snapshot?.learner)
const learnerAgent = ref('')
watch(
  () => live.agents,
  (agents) => {
    if (!learnerAgent.value) learnerAgent.value = learner.value?.agent || agents[0]?.alias || ''
  },
  { immediate: true },
)

function openSession(name: string) {
  void router.push({ path: route.path, query: { ...route.query, session: name } })
}

async function post(path: string, command: string, body: unknown = {}) {
  await run(() => api.post(path, body), { command, toastErrors: true })
}

// Learner prompt ---------------------------------------------------------------
const learnerPrompt = ref<PromptFile | null>(null)
async function loadLearnerPrompt() {
  try {
    const prompt = await api.get<PromptFile & { exists: boolean }>('/prompts/learner.md')
    learnerPrompt.value = prompt.exists ? prompt : null
  } catch {
    learnerPrompt.value = null
  }
}
watch(() => learner.value?.running, loadLearnerPrompt, { immediate: true })

// Completions -------------------------------------------------------------------
const completions = ref<CompletionListing | null>(null)
const completionFailure = ref('')
async function loadCompletions() {
  try {
    completions.value = await api.get<CompletionListing>('/completions')
    completionFailure.value = ''
  } catch (error) {
    completionFailure.value = errorMessage(error)
  }
}
watch(
  () => [tab.value, live.snapshot?.completions?.pending, live.snapshot?.completions?.processed, live.snapshot?.completions?.invalid],
  () => {
    if (tab.value === 'completions') void loadCompletions()
  },
  { immediate: true },
)
const buckets: { key: 'pending' | 'processed' | 'invalid'; label: string; tone: 'brass' | 'ok' | 'danger' }[] = [
  { key: 'pending', label: 'Waiting for the coordinator', tone: 'brass' },
  { key: 'processed', label: 'Processed into notifications', tone: 'ok' },
  { key: 'invalid', label: 'Quarantined as malformed', tone: 'danger' },
]

// Tracker -----------------------------------------------------------------------
const tracker = ref<TrackerListing | null>(null)
const trackerFailure = ref('')
const daily = ref('')
const dailyContent = ref('')
async function loadTracker() {
  try {
    tracker.value = await api.get<TrackerListing>('/tracker')
    trackerFailure.value = ''
    if (!daily.value) daily.value = tracker.value.daily_notes.files[0]?.name ?? ''
  } catch (error) {
    trackerFailure.value = errorMessage(error)
  }
}
watch(
  () => [tab.value, live.snapshot?.generated_at],
  () => {
    if (tab.value === 'tracker') void loadTracker()
  },
  { immediate: true },
)
watch(daily, async (name) => {
  dailyContent.value = ''
  if (!name) return
  try {
    dailyContent.value = (await api.get<{ content: string }>(`/tracker/daily/${encodeURIComponent(name)}`)).content
  } catch (error) {
    dailyContent.value = errorMessage(error)
  }
})

// State files ---------------------------------------------------------------------
const documentName = ref('tasks')
const documentText = ref('')
const documentPath = ref('')
async function loadDocument() {
  try {
    const result = await api.get<{ content: string; path: string }>(`/state/${documentName.value}`)
    documentText.value = result.content
    documentPath.value = result.path
  } catch (error) {
    documentText.value = errorMessage(error)
  }
}
watch(
  () => [tab.value, documentName.value, live.snapshot?.generated_at],
  () => {
    if (tab.value === 'state') void loadDocument()
  },
  { immediate: true },
)

function completionList(key: 'pending' | 'processed' | 'invalid'): CompletionEntry[] {
  return completions.value?.[key] ?? []
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>Operations</h1>
        <p>The parts of Alfred that run in the background, and the files they read and write.</p>
      </div>
    </header>

    <WorkspaceProblem />
    <TabBar v-model="tab" :tabs="tabs" label="Operations sections" class="tabs" />

    <div v-if="tab === 'daemons'" class="grid">
      <section class="panel" data-testid="coordinator">
        <header class="panel-header">
          <LampDot color="var(--lamp-running)" :lit="!!coordinator?.running" :pulse="live.isBusy(coordinator?.session_name)" />
          <h3>Coordinator</h3>
          <TagChip :tone="coordinator?.running ? 'ok' : 'default'">{{ coordinator?.running ? 'running' : 'stopped' }}</TagChip>
        </header>
        <div class="panel-body stack">
          <p class="muted small">
            Turns completion reports into notifications, checks the knowledge requirement, and reports agent sessions
            that died while their run was active. In the background it polls every five seconds.
          </p>
          <p class="row small">
            <TagChip tone="brass">{{ live.snapshot?.completions?.pending ?? 0 }} pending</TagChip>
            <TagChip tone="ok">{{ live.snapshot?.completions?.processed ?? 0 }} processed</TagChip>
            <TagChip tone="danger">{{ live.snapshot?.completions?.invalid ?? 0 }} invalid</TagChip>
          </p>
          <div class="row">
            <AppButton tone="primary" :icon="RefreshCw" :loading="pending" @click="post('/coordinator/once', 'alfred coordinator once')">Process once now</AppButton>
            <AppButton v-if="!coordinator?.running" :icon="Play" :loading="pending" :disabled="!live.snapshot?.tmux.available" @click="post('/coordinator/start', 'alfred coordinator start')">
              Start in background
            </AppButton>
            <AppButton v-else tone="danger" :icon="Square" :loading="pending" @click="post('/coordinator/stop', 'alfred coordinator stop')">Stop</AppButton>
          </div>
          <template v-if="coordinator?.running">
            <ScreenPreview :session="coordinator.session_name" :max-font="10" :min-rows="6" />
            <AppButton size="sm" :icon="SquareTerminal" @click="openSession(coordinator.session_name)">Open terminal</AppButton>
          </template>
          <CommandLine command="alfred coordinator status" />
        </div>
      </section>

      <section class="panel" data-testid="learner">
        <header class="panel-header">
          <LampDot color="var(--lamp-review)" :lit="!!learner?.running" :pulse="live.isBusy(learner?.session_name)" />
          <h3>Learner</h3>
          <TagChip :tone="learner?.running ? 'ok' : 'default'">{{ learner?.running ? `running with ${learner.agent}` : 'stopped' }}</TagChip>
        </header>
        <div class="panel-body stack">
          <p class="muted small">
            An agent in its own session ({{ learner?.session_name }}) that reads processed completion reports and adds
            new knowledge entries. It never edits or deletes existing ones.
          </p>
          <div class="row">
            <label class="visually-hidden" for="learner-agent">Learner agent</label>
            <SelectInput
              id="learner-agent"
              v-model="learnerAgent"
              class="agent-select"
              :options="live.agents.map((agent) => ({ value: agent.alias, label: agent.alias, hint: agent.cli }))"
            />
            <AppButton v-if="!learner?.running" :icon="BrainCircuit" :loading="pending" :disabled="!learnerAgent || !live.snapshot?.tmux.available" @click="post('/learner/start', alfredCommand('learner', 'start', ['--agent', learnerAgent]), { agent: learnerAgent })">
              Start learner
            </AppButton>
            <AppButton v-else tone="danger" :icon="Square" :loading="pending" @click="post('/learner/stop', 'alfred learner stop')">Stop</AppButton>
          </div>
          <template v-if="learner?.running">
            <ScreenPreview :session="learner.session_name" :max-font="10" :min-rows="6" />
            <AppButton size="sm" :icon="SquareTerminal" @click="openSession(learner.session_name)">Open terminal</AppButton>
          </template>
          <details v-if="learnerPrompt" class="prompt">
            <summary>Learner prompt, written {{ absolute(learnerPrompt.modified) }}</summary>
            <MarkdownView :source="learnerPrompt.content" />
          </details>
          <CommandLine command="alfred learner status" />
        </div>
      </section>
    </div>

    <div v-else-if="tab === 'completions'" class="stack">
      <p v-if="completionFailure" class="failure">{{ completionFailure }}</p>
      <p class="muted small">{{ completions?.directory }}</p>
      <section v-for="bucket in buckets" :key="bucket.key" class="panel">
        <header class="panel-header">
          <h3>{{ bucket.label }}</h3>
          <TagChip :tone="bucket.tone">{{ completionList(bucket.key).length }}</TagChip>
          <span class="spacer" />
          <AppButton v-if="bucket.key === 'pending' && completionList('pending').length" size="sm" tone="primary" :loading="pending" @click="post('/coordinator/once', 'alfred coordinator once')">
            Process now
          </AppButton>
        </header>
        <div class="panel-body stack">
          <p v-if="!completionList(bucket.key).length" class="muted small">None.</p>
          <details v-for="entry in completionList(bucket.key)" :key="entry.path" class="entry">
            <summary>
              <strong>{{ entry.task_number !== null ? `Task #${entry.task_number}` : entry.name }}</strong>
              <span class="mono small">{{ entry.name }}</span>
              <span class="faint small">{{ absolute(entry.modified) }}</span>
              <span v-if="entry.report" class="small">{{ entry.report.status }}: {{ entry.report.summary }}</span>
            </summary>
            <p v-if="entry.error" class="failure small">{{ entry.error }}</p>
            <JsonBlock v-if="entry.report" :value="entry.report" />
            <JsonBlock v-else :raw="entry.raw" />
          </details>
        </div>
      </section>
    </div>

    <div v-else-if="tab === 'tracker'" class="stack">
      <p v-if="trackerFailure" class="failure">{{ trackerFailure }}</p>
      <template v-if="tracker">
        <section class="panel">
          <header class="panel-header">
            <h3>Validation</h3>
            <TagChip :tone="!tracker.enabled ? 'default' : tracker.issues.length ? 'danger' : 'ok'">
              {{ !tracker.enabled ? 'disabled' : tracker.issues.length ? `${tracker.issues.length} issue${tracker.issues.length === 1 ? '' : 's'}` : 'in sync' }}
            </TagChip>
            <span class="spacer" />
            <AppButton size="sm" :icon="RefreshCw" @click="loadTracker">Validate again</AppButton>
            <AppButton v-if="tracker.enabled" size="sm" tone="primary" :loading="pending" @click="post('/sync/apply', 'alfred sync apply', {})">Apply to every task</AppButton>
          </header>
          <div class="panel-body stack">
            <p v-if="!tracker.enabled" class="muted">Enable <code>[trackers.markdown]</code> in the configuration to keep task, agent, and daily Markdown files in step with every change.</p>
            <p v-else-if="!tracker.issues.length" class="muted">Every configured path exists and every task and agent has its row.</p>
            <ul v-else class="issues">
              <li v-for="issue in tracker.issues" :key="issue">{{ issue }}</li>
            </ul>
            <CommandLine command="alfred sync validate" />
          </div>
        </section>
        <div v-if="tracker.enabled" class="grid">
          <section class="panel">
            <header class="panel-header"><h3>Tasks</h3><span class="mono faint tiny truncate" :title="tracker.canonical.path">{{ tracker.canonical.path.split('/').pop() }}</span></header>
            <div class="panel-body scroll-x">
              <MarkdownView v-if="tracker.canonical.exists" :source="tracker.canonical.content" />
              <p v-else class="muted">Not created yet.</p>
            </div>
          </section>
          <section class="panel">
            <header class="panel-header"><h3>Agents</h3><span class="mono faint tiny truncate" :title="tracker.agents.path">{{ tracker.agents.path.split('/').pop() }}</span></header>
            <div class="panel-body scroll-x">
              <MarkdownView v-if="tracker.agents.exists" :source="tracker.agents.content" />
              <p v-else class="muted">Not created yet.</p>
            </div>
          </section>
        </div>
        <section v-if="tracker.enabled" class="panel">
          <header class="panel-header">
            <h3>Daily notes</h3>
            <span class="spacer" />
            <label class="visually-hidden" for="daily-note">Day</label>
            <select id="daily-note" v-model="daily" class="control">
              <option v-for="file in tracker.daily_notes.files" :key="file.name" :value="file.name">{{ file.name.replace('.md', '') }}</option>
            </select>
          </header>
          <div class="panel-body">
            <p v-if="!tracker.daily_notes.files.length" class="muted">No daily notes yet.</p>
            <MarkdownView v-else :source="dailyContent" />
          </div>
        </section>
      </template>
    </div>

    <div v-else class="stack">
      <section class="panel">
        <header class="panel-header">
          <h3>Raw state</h3>
          <span class="spacer" />
          <label class="visually-hidden" for="state-document">Document</label>
          <select id="state-document" v-model="documentName" class="control">
            <option v-for="name in ['tasks', 'runs', 'queue', 'notifications', 'events']" :key="name" :value="name">{{ name }}.json</option>
          </select>
        </header>
        <div class="panel-body stack">
          <p class="muted small">
            Read-only. Alfred writes these atomically and validates the schema version on every read; change them only
            through commands so events and the tracker stay consistent.
          </p>
          <p class="mono faint tiny">{{ documentPath }}</p>
          <JsonBlock :raw="documentText" max-height="60vh" />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tabs {
  margin-bottom: var(--space-4);
  padding: 0;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(420px, 100%), 1fr));
  gap: var(--space-4);
  align-items: start;
}

.agent-select {
  min-width: min(220px, 100%);
}

.prompt summary,
.entry summary {
  cursor: pointer;
  display: flex;
  gap: 10px;
  align-items: baseline;
  flex-wrap: wrap;
}

.entry[open] summary {
  margin-bottom: 8px;
}

.issues {
  margin: 0;
  padding-left: 1.2em;
  color: var(--danger);
}

.control {
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
}

.scroll-x {
  overflow-x: auto;
}

.failure {
  color: var(--danger);
}
</style>
