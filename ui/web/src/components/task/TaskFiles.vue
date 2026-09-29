<script setup lang="ts">
import { computed, ref } from 'vue'
import { BookPlus, RefreshCw } from 'lucide-vue-next'
import type { CompletionEntry, TaskDetail } from '@/api/types'
import { absolute, bytes } from '@/lib/format'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'
import MarkdownView from '@/components/base/MarkdownView.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import TagChip from '@/components/base/TagChip.vue'
import JsonBlock from '@/components/misc/JsonBlock.vue'
import TranscriptViewer from '@/components/misc/TranscriptViewer.vue'

/** The files Alfred keeps for this task: prompts, completion handoffs, transcripts, and knowledge. */
const props = defineProps<{ detail: TaskDetail }>()
const dialogs = useDialogs()
const live = useLive()
const promptPhase = ref<'plan' | 'execution'>('execution')
const promptView = ref<'rendered' | 'raw'>('rendered')

const prompts = computed(() => props.detail.prompts)
const prompt = computed(() => prompts.value.find((item) => item.phase === promptPhase.value) ?? prompts.value[0])
const completions = computed<CompletionEntry[]>(() => [
  ...props.detail.completions.pending,
  ...props.detail.completions.processed,
  ...props.detail.completions.invalid,
])
const required = computed(() => live.config?.knowledge.required_completion_entries ?? 0)
</script>

<template>
  <div class="files">
    <section class="panel">
      <header class="panel-header wrap">
        <h3>Prompts sent to the agent</h3>
        <span class="spacer" />
        <SegmentedControl
          v-if="prompts.length > 1"
          v-model="promptPhase"
          :options="prompts.map((item) => ({ value: item.phase, label: item.phase === 'plan' ? 'Planning' : 'Execution' }))"
          label="Prompt"
        />
        <SegmentedControl
          v-if="prompts.length"
          v-model="promptView"
          :options="[
            { value: 'rendered', label: 'Rendered' },
            { value: 'raw', label: 'Raw' },
          ]"
          label="View"
        />
      </header>
      <div class="panel-body">
        <p v-if="!prompt" class="muted">Alfred writes the prompt when the task is triggered.</p>
        <template v-else>
          <p class="faint small">{{ prompt.path }}, {{ bytes(prompt.size) }}, written {{ absolute(prompt.modified) }}</p>
          <MarkdownView v-if="promptView === 'rendered'" :source="prompt.content" />
          <pre v-else class="raw">{{ prompt.content }}</pre>
        </template>
      </div>
    </section>

    <section class="panel">
      <header class="panel-header">
        <h3>Completion reports</h3>
        <span class="faint small">Handoffs from the agent to the coordinator</span>
      </header>
      <div class="panel-body stack">
        <p v-if="!completions.length" class="muted">None yet. <code>alfred run complete</code> writes one.</p>
        <article v-for="entry in completions" :key="entry.path" class="completion">
          <p class="row">
            <TagChip :tone="entry.bucket === 'pending' ? 'brass' : entry.bucket === 'invalid' ? 'danger' : 'ok'">{{ entry.bucket }}</TagChip>
            <span class="mono small">{{ entry.name }}</span>
            <span class="faint small">{{ absolute(entry.modified) }}</span>
          </p>
          <p v-if="entry.error" class="error small">{{ entry.error }}</p>
          <JsonBlock v-if="entry.report" :value="entry.report" max-height="240px" />
          <JsonBlock v-else :raw="entry.raw" max-height="240px" />
        </article>
      </div>
    </section>

    <section class="panel">
      <header class="panel-header">
        <h3>Session transcripts</h3>
      </header>
      <div class="panel-body">
        <TranscriptViewer :transcripts="detail.transcripts" empty-label="Transcripts are saved when a plan is reported, a run finishes, before the UI stops a run, or on request." />
      </div>
    </section>

    <section class="panel">
      <header class="panel-header">
        <h3>Knowledge</h3>
        <span class="faint small">{{ detail.knowledge.length }} of {{ required }} required</span>
        <span class="spacer" />
        <AppButton size="sm" :icon="BookPlus" @click="dialogs.openAction('knowledge', detail.task.task_number)">Add entry</AppButton>
      </header>
      <div class="panel-body stack">
        <p v-if="!detail.knowledge.length" class="muted">No knowledge entries for this task.</p>
        <details v-for="entry in detail.knowledge" :key="entry.relative" class="entry">
          <summary>
            <TagChip>{{ entry.category }}</TagChip>
            <strong>{{ entry.title }}</strong>
            <span class="faint small">{{ entry.agent || 'no agent' }}, {{ absolute(entry.created) }}</span>
          </summary>
          <MarkdownView :source="entry.content" />
        </details>
      </div>
    </section>

    <section class="panel">
      <header class="panel-header">
        <h3>Markdown tracker</h3>
        <span class="spacer" />
        <AppButton size="sm" :icon="RefreshCw" @click="dialogs.openAction('sync_task', detail.task.task_number)">Reconcile</AppButton>
      </header>
      <div class="panel-body">
        <p v-if="!live.config?.tracker.enabled" class="muted">The Markdown tracker is disabled in the configuration.</p>
        <p v-else-if="!detail.drift.length" class="muted">Task and agent rows are present.</p>
        <ul v-else class="issues">
          <li v-for="issue in detail.drift" :key="issue">{{ issue }}</li>
        </ul>
      </div>
    </section>
  </div>
</template>

<style scoped>
.files {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5) var(--space-6);
}

.wrap {
  flex-wrap: wrap;
}

.raw {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: var(--panel-2);
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: pre-wrap;
  max-height: 520px;
  overflow-y: auto;
}

.completion {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.completion p {
  margin: 0;
}

.error,
.issues {
  color: var(--danger);
}

.issues {
  margin: 0;
  padding-left: 1.2em;
}

.entry summary {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  cursor: pointer;
  padding: 4px 0;
}

.entry[open] summary {
  margin-bottom: 8px;
}
</style>
