<script setup lang="ts">
import { computed, ref } from 'vue'
import { Eye, Keyboard, Minus, Plus, Save, SquareTerminal } from 'lucide-vue-next'
import { api } from '@/api/http'
import type { TaskDetail } from '@/api/types'
import { useRequest } from '@/composables/useRequest'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import { usePrefs } from '@/stores/prefs'
import AppButton from '@/components/base/AppButton.vue'
import CopyButton from '@/components/base/CopyButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import TerminalView from '@/components/terminal/TerminalView.vue'
import SendBar from '@/components/terminal/SendBar.vue'
import TranscriptViewer from '@/components/misc/TranscriptViewer.vue'

/** The agent's live tmux session: type into it, watch it, or message it. */
const props = defineProps<{ detail: TaskDetail }>()
const live = useLive()
const prefs = usePrefs()
const dialogs = useDialogs()
const { pending, run } = useRequest()
const mode = ref<'interactive' | 'readonly'>('interactive')

const task = computed(() => props.detail.task)
const session = computed(() => task.value.derived.session)
const alive = computed(() => !!session.value?.alive && live.sessionMap.has(session.value.name))
const attach = computed(() => (session.value?.name ? `tmux attach-session -t ${session.value.name}` : ''))
const queued = computed(() => task.value.derived.active_run?.run_status === 'queued')

function font(delta: number) {
  prefs.values.terminalFontSize = Math.max(9, Math.min(20, prefs.values.terminalFontSize + delta))
}

async function capture() {
  if (!session.value?.name) return
  await run(() => api.post(`/sessions/${encodeURIComponent(session.value!.name)}/capture`, { reason: 'manual' }), {})
}
</script>

<template>
  <div class="terminal-tab">
    <template v-if="alive && session">
      <div class="toolbar">
        <SegmentedControl
          v-model="mode"
          :options="[
            { value: 'interactive', label: 'Interactive' },
            { value: 'readonly', label: 'Watch only' },
          ]"
          label="Terminal mode"
        />
        <span class="hint small">
          <Keyboard v-if="mode === 'interactive'" :size="14" aria-hidden="true" />
          <Eye v-else :size="14" aria-hidden="true" />
          {{ mode === 'interactive' ? 'Keystrokes go to the agent. Escape stays in the terminal.' : 'Attached read-only; typing is ignored.' }}
        </span>
        <span class="spacer" />
        <AppButton size="sm" tone="quiet" :icon="Minus" title="Smaller text" aria-label="Smaller text" @click="font(-1)" />
        <span class="small">{{ prefs.values.terminalFontSize }}px</span>
        <AppButton size="sm" tone="quiet" :icon="Plus" title="Larger text" aria-label="Larger text" @click="font(1)" />
        <AppButton size="sm" :icon="Save" :loading="pending" @click="capture">Save transcript</AppButton>
      </div>
      <div class="screen">
        <TerminalView :key="`${session.name}-${mode}`" :session="session.name" :mode="mode" autofocus />
      </div>
      <SendBar :session="session.name" />
      <p class="attach small">
        From your own terminal: <code>{{ attach }}</code>
        <CopyButton :text="attach" label="Copy" />
        <span class="faint">(detach with Ctrl-b d; a browser session attaches the same way)</span>
      </p>
    </template>

    <template v-else>
      <EmptyState :icon="SquareTerminal" :title="queued ? 'Queued: no session was started' : 'No live session'">
        <template v-if="queued">
          tmux was unavailable when this run was dispatched, so Alfred persisted it as queued. Once tmux is available,
          dispatch it again; the queued attempt is superseded.
        </template>
        <template v-else-if="session?.name">
          Session <code>{{ session.name }}</code> is not running. Agents keep their session after completing, so it
          was stopped or it ended on its own.
        </template>
        <template v-else>The agent session starts when the task is triggered.</template>
        <template #actions>
          <AppButton v-if="task.derived.actions.trigger.enabled" tone="primary" @click="dialogs.openAction('trigger', task.task_number)">
            {{ queued ? 'Dispatch again' : 'Trigger agent' }}
          </AppButton>
          <AppButton v-else-if="task.derived.actions.reopen.enabled" tone="primary" @click="dialogs.openAction('reopen', task.task_number)">
            Reopen with a new attempt
          </AppButton>
        </template>
      </EmptyState>
      <section v-if="detail.transcripts.length" class="panel">
        <header class="panel-header"><h3>Saved transcripts</h3></header>
        <div class="panel-body"><TranscriptViewer :transcripts="detail.transcripts" /></div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.terminal-tab {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5) var(--space-5);
  height: 100%;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-2);
}

.screen {
  height: min(62vh, 640px);
  min-height: 320px;
}

.attach {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0;
  color: var(--ink-2);
}
</style>
