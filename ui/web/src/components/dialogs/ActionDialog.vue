<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { TriangleAlert } from 'lucide-vue-next'
import { api } from '@/api/http'
import { ACTIONS, initialValues, type ActionContext, type Values } from '@/lib/actions'
import { useRequest } from '@/composables/useRequest'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import { usePrefs } from '@/stores/prefs'
import ModalDialog from '@/components/base/ModalDialog.vue'
import AppButton from '@/components/base/AppButton.vue'
import CommandLine from '@/components/base/CommandLine.vue'
import FieldControl from './FieldControl.vue'

const dialogs = useDialogs()
const live = useLive()
const prefs = usePrefs()
const { pending, error, run } = useRequest()

const state = computed(() => dialogs.action)
const spec = computed(() => (state.value ? ACTIONS[state.value.id] : null))
const task = computed(() =>
  state.value?.taskNumber !== null && state.value?.taskNumber !== undefined
    ? (live.taskMap.get(state.value.taskNumber) ?? null)
    : null,
)
const context = computed<ActionContext>(() => ({ task: task.value, config: live.config, actor: prefs.values.actor }))
const values = reactive<Values>({})
const attempted = ref(false)

watch(
  state,
  (current) => {
    for (const key of Object.keys(values)) delete values[key]
    attempted.value = false
    error.value = ''
    if (current && spec.value) Object.assign(values, initialValues(spec.value, context.value, current.overrides))
  },
  { immediate: true },
)

const visibleFields = computed(() =>
  (spec.value?.fields ?? []).filter((field) => !field.visible || field.visible(values, context.value)),
)
const missing = computed(() =>
  visibleFields.value.filter((field) => {
    if (!field.required) return false
    const value = values[field.key]
    return Array.isArray(value) ? value.length === 0 : String(value ?? '').trim() === ''
  }),
)
const gate = computed(() => (spec.value?.gate && task.value ? task.value.derived.actions[spec.value.gate] : null))
const command = computed(() => (spec.value ? spec.value.command(values, context.value) : null))
const warning = computed(() => spec.value?.warning?.(values, context.value) ?? null)
const title = computed(() => {
  if (!spec.value) return ''
  const base = spec.value.title(context.value)
  return task.value ? `${base}: #${task.value.task_number}` : base
})
const submitLabel = computed(() => {
  const submit = spec.value?.submit
  return typeof submit === 'function' ? submit(values, context.value) : (submit ?? 'Apply')
})

function close() {
  dialogs.action = null
}

async function submit() {
  attempted.value = true
  if (!spec.value || missing.value.length) return
  const request = spec.value.request(values, context.value)
  const result = await run(
    () => (request.method === 'PATCH' ? api.patch(request.path, request.body) : api.post(request.path, request.body)),
    { command: command.value, task: task.value?.task_number ?? null },
  )
  if (result) close()
}
</script>

<template>
  <ModalDialog
    :open="!!spec"
    :title="title"
    :description="spec?.description?.(context)"
    width="600px"
    @close="close"
  >
    <form v-if="spec" id="action-form" class="stack" @submit.prevent="submit">
      <p v-if="task" class="subject">{{ task.title }}</p>
      <p v-if="gate && !gate.enabled" class="blocked" role="note">
        <TriangleAlert :size="15" aria-hidden="true" />
        <span>Alfred will refuse this right now: {{ gate.reason }}</span>
      </p>
      <FieldControl
        v-for="field in visibleFields"
        :key="field.key"
        :field="field"
        :values="values"
        :context="context"
        :invalid="attempted && missing.includes(field)"
      />
      <p v-if="warning" class="warning" role="note">
        <TriangleAlert :size="15" aria-hidden="true" />
        <span>{{ warning }}</span>
      </p>
      <CommandLine :command="command" />
      <p v-if="command === null" class="faint tiny">No CLI equivalent: the UI applies this through Alfred's services.</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </form>
    <template #footer>
      <span v-if="attempted && missing.length" class="missing">Fill in {{ missing.map((field) => field.label.toLowerCase()).join(', ') }}.</span>
      <AppButton tone="quiet" @click="close">Cancel</AppButton>
      <AppButton
        type="submit"
        form="action-form"
        :tone="spec?.tone === 'danger' ? 'danger' : spec?.tone === 'brass' ? 'brass' : 'primary'"
        :loading="pending"
        :disabled="gate ? !gate.enabled : false"
        data-testid="action-submit"
      >
        {{ submitLabel }}
      </AppButton>
    </template>
  </ModalDialog>
</template>

<style scoped>
.subject {
  margin: 0;
  font-weight: 650;
}

.blocked,
.warning {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius);
  font-size: var(--text-sm);
}

.blocked {
  background: var(--danger-soft);
  color: var(--danger);
}

.warning {
  background: var(--brass-soft);
  color: var(--brass);
}

.error {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: var(--text-sm);
  font-weight: 600;
  white-space: pre-wrap;
}

.missing {
  margin-right: auto;
  color: var(--danger);
  font-size: var(--text-sm);
}
</style>
