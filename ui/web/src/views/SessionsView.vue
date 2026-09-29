<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Cpu, MonitorPlay, Save, SquareTerminal, X } from 'lucide-vue-next'
import { api } from '@/api/http'
import type { SessionInfo } from '@/api/types'
import { useRequest } from '@/composables/useRequest'
import { RUN_META, runLamp, statusLamp } from '@/lib/status'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import { usePrefs } from '@/stores/prefs'
import AppButton from '@/components/base/AppButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import LampDot from '@/components/base/LampDot.vue'
import RelativeTime from '@/components/base/RelativeTime.vue'
import TagChip from '@/components/base/TagChip.vue'
import ScreenPreview from '@/components/terminal/ScreenPreview.vue'
import WorkspaceProblem from '@/components/layout/WorkspaceProblem.vue'

/** Every Alfred tmux session at once, with live screens. */
const live = useLive()
const prefs = usePrefs()
const dialogs = useDialogs()
const route = useRoute()
const router = useRouter()
const { run } = useRequest()

const order: Record<string, number> = { task: 0, coordinator: 1, learner: 2, other: 3 }
const sessions = computed(() =>
  [...live.sessions].sort((left, right) => order[left.kind] - order[right.kind] || left.name.localeCompare(right.name)),
)

function leftover(session: SessionInfo): boolean {
  return session.kind === 'task' && !!session.run_status && !['running', 'blocked', 'queued'].includes(session.run_status)
}

function openTerminal(name: string) {
  void router.push({ path: route.path, query: { ...route.query, session: name } })
}

function openTask(number: number | null) {
  if (number !== null) void router.push({ path: route.path, query: { ...route.query, task: String(number), tab: 'terminal' } })
}

async function capture(name: string) {
  await run(() => api.post(`/sessions/${encodeURIComponent(name)}/capture`, { reason: 'manual' }), { toastErrors: true })
}

async function close(session: SessionInfo) {
  const ok = await dialogs.confirm({
    title: `Close ${session.name}?`,
    message:
      session.kind === 'task'
        ? 'The UI saves its transcript first, then stops the tmux session. The run record is not changed.'
        : `This stops the ${session.kind} session.`,
    confirm: 'Close session',
    tone: 'danger',
  })
  if (!ok) return
  await run(() => api.post(`/sessions/${encodeURIComponent(session.name)}/kill`, { actor: prefs.values.actor }), {
    command: `tmux kill-session -t ${session.name}`,
    toastErrors: true,
  })
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>Agent sessions</h1>
        <p>
          Every tmux session this workspace owns ({{ live.config?.runtime.session_prefix ?? 'prefix' }}-*). Screens update
          every couple of seconds without attaching, so watching never resizes or disturbs an agent.
        </p>
      </div>
    </header>

    <WorkspaceProblem />

    <p v-if="live.snapshot && !live.snapshot.tmux.available" class="warning">
      tmux is not on the server’s PATH. Dispatches follow the <code>tmux_unavailable_policy</code> setting and no sessions can start.
    </p>

    <EmptyState v-else-if="live.config && !sessions.length" :icon="MonitorPlay" title="No agent sessions are running">
      Trigger a task and its agent’s session appears here with a live screen.
    </EmptyState>

    <div class="grid">
      <article v-for="session in sessions" :key="session.name" class="panel session" :class="{ leftover: leftover(session) }" :data-session="session.name">
        <header class="panel-header head">
          <LampDot
            :color="session.kind === 'task' ? runLamp(session.run_status || 'running') : 'var(--lamp-review)'"
            :pulse="live.isBusy(session.name)"
            :label="live.isBusy(session.name) ? 'Producing output now' : 'Idle'"
          />
          <span class="name mono">{{ session.name }}</span>
          <TagChip>{{ session.kind }}</TagChip>
          <TagChip v-if="leftover(session)" tone="brass" title="The run finished; Alfred leaves the session running for reuse">left running</TagChip>
          <span class="spacer" />
          <AppButton size="sm" tone="quiet" :icon="Save" title="Save transcript" aria-label="Save transcript" @click="capture(session.name)" />
          <AppButton size="sm" tone="quiet" :icon="X" title="Close session" aria-label="Close session" @click="close(session)" />
        </header>
        <div class="panel-body stack">
          <p v-if="session.task_number !== null" class="task">
            <button type="button" class="link" @click="openTask(session.task_number)">
              <LampDot :color="statusLamp(live.taskMap.get(session.task_number)?.status ?? '')" :size="8" />
              #{{ session.task_number }} {{ live.taskMap.get(session.task_number)?.title ?? '(task not found)' }}
            </button>
          </p>
          <p class="facts small">
            <span v-if="session.agent_alias"><Cpu :size="13" aria-hidden="true" /> {{ session.agent_alias }}<template v-if="live.agentMap.get(session.agent_alias)?.model">, {{ live.agentMap.get(session.agent_alias)?.model }}</template></span>
            <span v-if="session.run_status">run {{ RUN_META[session.run_status as keyof typeof RUN_META]?.label.toLowerCase() ?? session.run_status }}</span>
            <span v-if="session.pane">{{ session.pane.current_command }} (pid {{ session.pane.pid }}), {{ session.pane.width }}×{{ session.pane.height }}</span>
            <span>{{ session.attached }} attached</span>
            <span>active <RelativeTime :value="session.activity" /></span>
          </p>
          <button type="button" class="screen" :aria-label="`Open ${session.name} in a terminal`" @click="openTerminal(session.name)">
            <ScreenPreview :session="session.name" :max-font="10" :min-rows="12" />
          </button>
          <div class="row">
            <AppButton size="sm" tone="primary" :icon="SquareTerminal" @click="openTerminal(session.name)">Open terminal</AppButton>
            <AppButton v-if="session.task_number !== null" size="sm" @click="openTask(session.task_number)">Open task</AppButton>
          </div>
        </div>
      </article>
    </div>
    <p v-if="live.snapshot?.tmux.foreign_sessions" class="faint small foreign">
      {{ live.snapshot.tmux.foreign_sessions }} other tmux session{{ live.snapshot.tmux.foreign_sessions === 1 ? '' : 's' }} on this server belong to something else and are not shown.
    </p>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(420px, 100%), 1fr));
  gap: var(--space-4);
}

.session.leftover {
  border-style: dashed;
}

.head {
  gap: 8px;
}

.name {
  font-size: 12.5px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task {
  margin: 0;
}

.link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: none;
  padding: 0;
  color: var(--ink);
  font-weight: 650;
  cursor: pointer;
  text-align: left;
}

.link:hover {
  color: var(--accent);
}

.facts {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 14px;
  margin: 0;
  color: var(--ink-2);
}

.facts span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.screen {
  display: block;
  width: 100%;
  border: 0;
  padding: 0;
  background: none;
  cursor: zoom-in;
  text-align: left;
}

.warning {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius);
  background: var(--brass-soft);
  color: var(--brass);
}

.foreign {
  margin-top: var(--space-4);
}
</style>
