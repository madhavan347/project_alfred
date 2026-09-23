<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '@/api/http'
import type { ActionResult } from '@/api/types'
import { alfredCommand, csv } from '@/lib/cli'
import { useRequest } from '@/composables/useRequest'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import { usePrefs } from '@/stores/prefs'
import ModalDialog from '@/components/base/ModalDialog.vue'
import AppButton from '@/components/base/AppButton.vue'
import CommandLine from '@/components/base/CommandLine.vue'
import FormField from '@/components/base/FormField.vue'
import TextInput from '@/components/base/TextInput.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import CheckList from '@/components/base/CheckList.vue'

/** `alfred run trigger` for several tasks, all queued tasks, and a parallel limit. */
const dialogs = useDialogs()
const live = useLive()
const prefs = usePrefs()
const { pending, error, run } = useRequest()

const scope = ref<'selected' | 'queued'>('selected')
const selected = ref<string[]>([])
const parallel = ref('1')

const candidates = computed(() =>
  live.tasks
    .filter((task) => task.derived.actions.trigger.enabled)
    .map((task) => ({
      value: String(task.task_number),
      label: `#${task.task_number}`,
      hint: `${task.title} (${task.execution_mode === 'plan-execution' && task.planning_state === 'pending' ? 'plan' : 'execution'})`,
    })),
)
const queued = computed(() => live.tasks.filter((task) => task.status === 'Queued').map((task) => task.task_number))

watch(
  () => dialogs.trigger,
  (state) => {
    if (!state) return
    error.value = ''
    selected.value = state.tasks.map(String)
    scope.value = state.tasks.length || !queued.value.length ? 'selected' : 'queued'
    parallel.value = String(Math.max(1, state.tasks.length || queued.value.length || 1))
  },
)

const numbers = computed(() => (scope.value === 'queued' ? queued.value : selected.value.map(Number)))
const limit = computed(() => Math.max(1, Math.floor(Number(parallel.value) || 1)))
const skipped = computed(() => numbers.value.slice(limit.value))
const command = computed(() =>
  alfredCommand(
    'run',
    'trigger',
    scope.value === 'queued' ? '--all' : ['--tasks', csv(selected.value) || '<tasks>'],
    ['--parallel', limit.value === 1 ? '' : limit.value],
    ['--actor', prefs.values.actor === 'manager' ? '' : prefs.values.actor],
  ),
)

async function submit() {
  const body =
    scope.value === 'queued'
      ? { all: true, parallel: limit.value, actor: prefs.values.actor }
      : { tasks: selected.value.map(Number), parallel: limit.value, actor: prefs.values.actor }
  const result = await run(() => api.post<ActionResult>('/runs/trigger', body), { command: command.value })
  if (result) dialogs.trigger = null
}
</script>

<template>
  <ModalDialog
    :open="!!dialogs.trigger"
    title="Trigger agents"
    description="Dispatch several tasks at once. Each starts its planning or execution phase in its own tmux session."
    width="620px"
    @close="dialogs.trigger = null"
  >
    <form id="trigger-form" class="stack" @submit.prevent="submit">
      <SegmentedControl
        v-model="scope"
        :options="[
          { value: 'selected', label: 'Choose tasks' },
          { value: 'queued', label: `All queued (${queued.length})`, disabled: !queued.length },
        ]"
        label="Which tasks"
      />
      <FormField v-if="scope === 'selected'" label="Tasks ready to trigger">
        <CheckList v-model="selected" :options="candidates" label="Tasks" />
      </FormField>
      <p v-else class="muted small">Tasks with status Queued: {{ queued.map((item) => `#${item}`).join(', ') }}</p>
      <FormField label="Start at most" for-id="trigger-parallel" help="Tasks beyond the limit are listed and left undispatched, as with --parallel.">
        <TextInput id="trigger-parallel" v-model="parallel" inputmode="numeric" />
      </FormField>
      <p v-if="skipped.length" class="muted small">Not dispatched this time: {{ skipped.map((item) => `#${item}`).join(', ') }}</p>
      <CommandLine :command="command" />
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </form>
    <template #footer>
      <AppButton tone="quiet" @click="dialogs.trigger = null">Cancel</AppButton>
      <AppButton type="submit" form="trigger-form" tone="primary" :loading="pending" :disabled="!numbers.length">
        Trigger {{ Math.min(numbers.length, limit) || '' }}
      </AppButton>
    </template>
  </ModalDialog>
</template>

<style scoped>
.error {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius);
  background: var(--danger-soft);
  color: var(--danger);
  font-weight: 600;
  font-size: var(--text-sm);
}
</style>
