<script setup lang="ts">
import { computed, ref } from 'vue'
import { CheckCheck, Save, ScrollText } from 'lucide-vue-next'
import { api } from '@/api/http'
import type { TaskDetail } from '@/api/types'
import { absolute } from '@/lib/format'
import { PLANNING_LABELS } from '@/lib/status'
import { useRequest } from '@/composables/useRequest'
import { useDialogs } from '@/stores/dialogs'
import AppButton from '@/components/base/AppButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import MarkdownView from '@/components/base/MarkdownView.vue'
import RelativeTime from '@/components/base/RelativeTime.vue'
import ScreenPreview from '@/components/terminal/ScreenPreview.vue'
import SendBar from '@/components/terminal/SendBar.vue'
import TranscriptViewer from '@/components/misc/TranscriptViewer.vue'

/** Everything about a plan-execution task's plan: what was asked, what the agent proposed, and approval. */
const props = defineProps<{ detail: TaskDetail }>()
const emit = defineEmits<{ tab: [string] }>()
const dialogs = useDialogs()
const { pending, run } = useRequest()
const showPrompt = ref(false)

const task = computed(() => props.detail.task)
const plan = computed(() => task.value.derived.plan)
const session = computed(() => task.value.derived.session)
const reports = computed(() =>
  props.detail.events.filter((event) => event.event_type === 'AGENT_PLAN_COMPLETED').slice().reverse(),
)
const approvals = computed(() => props.detail.events.filter((event) => event.event_type === 'PLAN_APPROVED').slice().reverse())
const dispatches = computed(() =>
  props.detail.events.filter(
    (event) => (event.event_type === 'RUN_STARTED' || event.event_type === 'RUN_QUEUED') && event.details.startsWith('Plan phase'),
  ),
)
const prompt = computed(() => props.detail.prompts.find((item) => item.phase === 'plan'))
const planTranscripts = computed(() => props.detail.transcripts.filter((item) => item.reason === 'plan'))
const allTranscripts = computed(() => props.detail.transcripts)
const planning = computed(() => task.value.derived.active_run?.phase === 'plan' && !!session.value?.alive)

const steps = computed(() => {
  const state = task.value.planning_state
  const order = ['pending', 'started', 'approved', 'completed']
  const reached = order.indexOf(state)
  return [
    { key: 'pending', label: 'Waiting to start', done: reached > 0 || dispatches.value.length > 0 },
    { key: 'started', label: plan.value.reported ? 'Plan reported' : 'Agent planning', done: reached > 1 || plan.value.reported },
    { key: 'approved', label: 'Approved', done: reached >= 2 || approvals.value.length > 0 },
    { key: 'completed', label: 'Executing', done: reached >= 3 },
  ]
})

async function capture() {
  if (!session.value?.name) return
  await run(() => api.post(`/sessions/${encodeURIComponent(session.value!.name)}/capture`, { reason: 'plan' }), {})
}
</script>

<template>
  <div class="plan">
    <EmptyState v-if="!plan.required && !reports.length" :icon="ScrollText" title="This task runs directly, without a plan">
      Direct tasks create worktrees and start executing immediately. Edit the task and choose "Plan first" to review a
      plan before any code changes.
      <template #actions>
        <AppButton size="sm" @click="dialogs.openTaskForm('edit', task.task_number)">Edit task</AppButton>
      </template>
    </EmptyState>

    <template v-else>
      <ol class="states" aria-label="Planning progress">
        <li v-for="step in steps" :key="step.key" :class="{ done: step.done }">{{ step.label }}</li>
      </ol>

      <section v-if="plan.awaiting_approval" class="approval" :class="{ ready: plan.reported }">
        <div class="text">
          <h3>{{ plan.reported ? 'The plan is ready for your review' : 'The agent is still planning' }}</h3>
          <p>
            Approving creates the worktrees and sends the execution prompt to the same session, with your note as the
            task’s latest note. To ask for changes instead, message the agent below; it keeps planning in its session.
          </p>
        </div>
        <AppButton tone="brass" :icon="CheckCheck" data-testid="approve-plan" :disabled="!task.derived.actions.continue.enabled" :title="task.derived.actions.continue.reason" @click="dialogs.openAction('continue', task.task_number)">
          Approve plan
        </AppButton>
      </section>

      <section class="panel">
        <header class="panel-header">
          <h3>Plan reported by the agent</h3>
          <span class="spacer" />
          <span class="faint small">{{ PLANNING_LABELS[task.planning_state] }}</span>
        </header>
        <div class="panel-body">
          <p v-if="!reports.length" class="muted">
            Nothing reported yet. The agent reports with
            <code>alfred run event --type plan_completed</code>; until then, watch its screen below.
          </p>
          <article v-for="(report, index) in reports" :key="report.index" class="report" :class="{ older: index > 0 }">
            <p class="byline">
              <strong>{{ index === 0 ? 'Latest plan' : 'Earlier plan' }}</strong>
              <span class="mono small">{{ report.actor }}</span>
              <RelativeTime class="faint small" :value="report.timestamp" />
            </p>
            <MarkdownView :source="report.details" />
          </article>
        </div>
      </section>

      <section v-if="session?.alive && (planning || plan.awaiting_approval)" class="panel">
        <header class="panel-header">
          <h3>Planning session</h3>
          <span class="spacer" />
          <AppButton size="sm" :icon="Save" :loading="pending" @click="capture">Save transcript</AppButton>
          <AppButton size="sm" @click="emit('tab', 'terminal')">Open terminal</AppButton>
        </header>
        <div class="panel-body stack">
          <ScreenPreview :session="session.name" :max-font="11" :interval="1200" />
          <SendBar :session="session.name" />
        </div>
      </section>

      <section class="panel">
        <header class="panel-header">
          <h3>Full planning transcript</h3>
          <span class="spacer" />
          <span class="faint small">Saved when the plan is reported, and on request</span>
        </header>
        <div class="panel-body">
          <TranscriptViewer
            :transcripts="planTranscripts.length ? planTranscripts : allTranscripts"
            empty-label="No transcript saved yet. One is saved automatically when the agent reports its plan."
          />
        </div>
      </section>

      <section v-if="approvals.length" class="panel">
        <header class="panel-header"><h3>Approvals</h3></header>
        <ul class="panel-body approvals">
          <li v-for="approval in approvals" :key="approval.index">
            <strong>{{ approval.actor }}</strong> approved {{ absolute(approval.timestamp) }}
            <p class="muted small">{{ approval.details }}</p>
          </li>
        </ul>
      </section>

      <section class="panel">
        <header class="panel-header">
          <h3>What the agent was asked</h3>
          <span class="spacer" />
          <AppButton v-if="prompt" size="sm" tone="quiet" @click="showPrompt = !showPrompt">{{ showPrompt ? 'Hide' : 'Show' }} planning prompt</AppButton>
        </header>
        <div class="panel-body">
          <p v-if="!prompt" class="muted">The planning prompt is written when the task is first triggered.</p>
          <template v-else>
            <p class="faint small">{{ prompt.path }}, written {{ absolute(prompt.modified) }}</p>
            <MarkdownView v-if="showPrompt" :source="prompt.content" />
          </template>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.plan {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5) var(--space-6);
}

.states {
  display: flex;
  gap: 6px;
  list-style: none;
  margin: 0;
  padding: 0;
  flex-wrap: wrap;
}

.states li {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--line-strong);
  font-size: var(--text-xs);
  font-weight: 650;
  color: var(--ink-2);
}

.states li.done {
  background: var(--ok-soft);
  border-color: color-mix(in srgb, var(--ok) 40%, var(--line));
  color: var(--ok);
}

.approval {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  border-radius: var(--radius-l);
  border: 1px solid var(--line-strong);
  background: var(--panel);
}

.approval.ready {
  border-color: var(--brass-line);
  background: var(--brass-soft);
}

.approval .text {
  flex: 1;
}

.approval h3 {
  margin-bottom: 4px;
}

.approval p {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--ink-2);
}

.report + .report {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--line);
}

.report.older {
  opacity: 0.8;
}

.byline {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 var(--space-2);
}

.approvals {
  list-style: none;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.approvals p {
  margin: 2px 0 0;
}
</style>
