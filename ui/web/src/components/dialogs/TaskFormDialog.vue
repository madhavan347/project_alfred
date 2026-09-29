<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TriangleAlert } from 'lucide-vue-next'
import { api } from '@/api/http'
import type { ActionResult, Task } from '@/api/types'
import { alfredCommand, csv } from '@/lib/cli'
import { PRIORITIES } from '@/lib/status'
import { useRequest } from '@/composables/useRequest'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import { usePrefs } from '@/stores/prefs'
import ModalDialog from '@/components/base/ModalDialog.vue'
import AppButton from '@/components/base/AppButton.vue'
import CommandLine from '@/components/base/CommandLine.vue'
import FormField from '@/components/base/FormField.vue'
import TextInput from '@/components/base/TextInput.vue'
import TextArea from '@/components/base/TextArea.vue'
import SelectInput from '@/components/base/SelectInput.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import CheckList from '@/components/base/CheckList.vue'

interface Form {
  task: string
  title: string
  description: string
  category: string
  priority: string
  deadline: string
  notes: string
  assign: string
  dispatch: 'auto' | 'queued'
  branch: string
  mode: 'direct' | 'plan-execution'
  worktree: 'enabled' | 'disabled'
  repos: string[]
  dependencies: string[]
}

const dialogs = useDialogs()
const live = useLive()
const prefs = usePrefs()
const route = useRoute()
const router = useRouter()
const { pending, error, run } = useRequest()

const state = computed(() => dialogs.taskForm)
const editing = computed(() => state.value?.mode === 'edit')
const original = computed<Task | null>(() =>
  state.value?.taskNumber ? (live.taskMap.get(state.value.taskNumber) ?? null) : null,
)
const form = reactive<Form>(blank())
const branchTouched = ref(false)
const attempted = ref(false)

function blank(): Form {
  return {
    task: '',
    title: '',
    description: '',
    category: 'General',
    priority: 'P2',
    deadline: '',
    notes: '',
    assign: '',
    dispatch: 'auto',
    branch: '',
    mode: 'direct',
    worktree: 'enabled',
    repos: [],
    dependencies: [],
  }
}

watch(
  state,
  (current) => {
    Object.assign(form, blank())
    attempted.value = false
    error.value = ''
    branchTouched.value = false
    if (!current) return
    const task = original.value
    if (current.mode === 'edit' && task) {
      Object.assign(form, {
        task: String(task.task_number),
        title: task.title,
        description: task.description,
        category: task.category,
        priority: task.priority,
        deadline: task.deadline,
        notes: task.notes,
        assign: task.assigned_agent_alias,
        dispatch: task.dispatch_mode,
        branch: task.branch_name,
        mode: task.execution_mode,
        worktree: task.worktree_mode,
        repos: [...task.target_repositories],
        dependencies: task.dependencies.map(String),
      })
      branchTouched.value = true
    } else {
      const highest = Math.max(0, ...live.tasks.map((item) => item.task_number))
      form.task = String(highest + 1)
      form.assign = live.config?.agents[0]?.alias ?? ''
      form.repos = (live.config?.repositories ?? []).filter((item) => item.selected_by_default).map((item) => item.name)
    }
  },
  { immediate: true },
)

function slug(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
    .replace(/-+$/, '')
}

watch(
  () => [form.title, form.task],
  () => {
    if (editing.value || branchTouched.value || form.worktree === 'disabled') return
    form.branch = form.title.trim() ? `feature/${slug(form.title)}-${form.task}` : ''
  },
)

const agentOptions = computed(() => [
  { value: '', label: 'Unassigned' },
  ...(live.config?.agents ?? []).map((agent) => ({
    value: agent.alias,
    label: agent.alias,
    hint: [agent.cli, agent.model && `model ${agent.model}`].filter(Boolean).join(', '),
  })),
])
const repositoryOptions = computed(() =>
  (live.config?.repositories ?? []).map((repository) => ({
    value: repository.name,
    label: repository.name,
    hint: repository.selected_by_default ? 'default' : undefined,
  })),
)
const dependencyOptions = computed(() =>
  live.tasks
    .filter((task) => String(task.task_number) !== form.task)
    .map((task) => ({ value: String(task.task_number), label: `#${task.task_number}`, hint: task.title })),
)

const problems = computed(() => {
  const list: string[] = []
  const number = Number(form.task)
  if (!Number.isInteger(number) || number <= 0) list.push('Task number must be a positive whole number')
  else if (!editing.value && live.taskMap.has(number)) list.push(`Task ${number} already exists`)
  if (!form.title.trim()) list.push('Title is required')
  if (!form.description.trim()) list.push('Description is required')
  if (form.worktree === 'enabled' && !form.branch.trim()) list.push('A branch is required when worktrees are enabled')
  return list
})

const modeChanged = computed(() => editing.value && original.value && original.value.execution_mode !== form.mode)

const changes = computed(() => {
  const task = original.value
  if (!editing.value || !task) return {}
  const diff: Record<string, unknown> = {}
  const compare: [keyof Form, string, unknown][] = [
    ['title', 'title', task.title],
    ['description', 'description', task.description],
    ['category', 'category', task.category],
    ['priority', 'priority', task.priority],
    ['deadline', 'deadline', task.deadline],
    ['notes', 'notes', task.notes],
    ['branch', 'branch', task.branch_name],
    ['mode', 'mode', task.execution_mode],
    ['worktree', 'worktree', task.worktree_mode],
  ]
  for (const [field, key, previous] of compare) if (form[field] !== previous) diff[key] = form[field]
  if (csv(form.repos) !== csv(task.target_repositories)) diff.repos = form.repos
  if (csv(form.dependencies) !== csv(task.dependencies.map(String))) diff.dependencies = form.dependencies.map(Number)
  return diff
})

const command = computed(() => {
  if (editing.value) {
    const diff = changes.value
    if (!Object.keys(diff).length) return null
    return alfredCommand(
      'task',
      'update',
      ['--task', form.task],
      ...(['title', 'description', 'category', 'priority', 'deadline', 'notes', 'branch', 'mode', 'worktree'] as const).map(
        (key) => (key in diff ? ([`--${key}`, String(diff[key]), true] as const) : false),
      ),
      'repos' in diff ? (['--repos', csv(form.repos), true] as const) : false,
      'dependencies' in diff ? (['--dependencies', csv(form.dependencies), true] as const) : false,
    )
  }
  return alfredCommand(
    'task',
    'create',
    ['--task', form.task || '<number>'],
    ['--title', form.title || '<title>'],
    ['--description', form.description || '<description>'],
    ['--category', form.category === 'General' ? '' : form.category],
    ['--priority', form.priority === 'P2' ? '' : form.priority],
    ['--deadline', form.deadline],
    ['--notes', form.notes],
    ['--assign', form.assign],
    ['--dispatch', form.dispatch === 'auto' ? '' : form.dispatch],
    ['--branch', form.branch],
    ['--mode', form.mode === 'direct' ? '' : form.mode],
    ['--worktree', form.worktree === 'enabled' ? '' : form.worktree],
    ['--repos', csv(form.repos)],
    ['--dependencies', csv(form.dependencies)],
  )
})

function close() {
  dialogs.taskForm = null
}

async function submit() {
  attempted.value = true
  if (problems.value.length) return
  let result: ActionResult | null
  if (editing.value) {
    if (!Object.keys(changes.value).length) {
      close()
      return
    }
    result = await run(
      () => api.patch<ActionResult>(`/tasks/${form.task}`, { ...changes.value, actor: prefs.values.actor }),
      { command: command.value, task: Number(form.task) },
    )
  } else {
    result = await run(
      () =>
        api.post<ActionResult>('/tasks', {
          task: Number(form.task),
          title: form.title,
          description: form.description,
          category: form.category.trim() || 'General',
          priority: form.priority,
          deadline: form.deadline,
          notes: form.notes,
          assign: form.assign,
          dispatch: form.dispatch,
          branch: form.branch,
          mode: form.mode,
          worktree: form.worktree,
          repos: form.repos,
          dependencies: form.dependencies.map(Number),
          actor: prefs.values.actor,
        }),
      { command: command.value, task: Number(form.task) },
    )
  }
  if (result) {
    const number = form.task
    close()
    if (!editing.value) void router.push({ path: route.path, query: { ...route.query, task: number } })
  }
}
</script>

<template>
  <ModalDialog
    :open="!!state"
    :title="editing ? `Edit task #${form.task}` : 'New task'"
    :description="editing ? 'Assignment has its own action; everything else can change here.' : 'Everything alfred task create accepts.'"
    width="760px"
    @close="close"
  >
    <form id="task-form" class="grid" @submit.prevent="submit">
      <FormField label="Number" required for-id="task-number" class="narrow">
        <TextInput id="task-number" v-model="form.task" inputmode="numeric" :disabled="editing" :invalid="attempted && problems.some((item) => item.startsWith('Task'))" />
      </FormField>
      <FormField label="Title" required for-id="task-title" class="wide">
        <TextInput id="task-title" v-model="form.title" placeholder="Add health endpoint" :invalid="attempted && !form.title.trim()" />
      </FormField>
      <FormField label="Description" required for-id="task-description" class="full" help="Agents receive this in their prompt. Markdown is fine.">
        <TextArea id="task-description" v-model="form.description" :rows="4" :invalid="attempted && !form.description.trim()" />
      </FormField>
      <FormField label="Priority" class="half">
        <SegmentedControl v-model="form.priority" :options="PRIORITIES.map((value) => ({ value, label: value }))" label="Priority" />
      </FormField>
      <FormField label="Category" for-id="task-category" class="quarter">
        <TextInput id="task-category" v-model="form.category" />
      </FormField>
      <FormField label="Deadline" for-id="task-deadline" class="quarter">
        <TextInput id="task-deadline" v-model="form.deadline" type="date" />
      </FormField>
      <FormField v-if="!editing" label="Agent" for-id="task-agent" class="half">
        <SelectInput id="task-agent" v-model="form.assign" :options="agentOptions" />
      </FormField>
      <FormField v-if="!editing" label="Dispatch" class="half" help="Queued tasks start as Queued and are picked up by Trigger all queued.">
        <SegmentedControl
          v-model="form.dispatch"
          :options="[
            { value: 'auto', label: 'Trigger explicitly' },
            { value: 'queued', label: 'Queue it' },
          ]"
          label="Dispatch"
        />
      </FormField>
      <FormField label="Execution" class="half" help="Plan first sends a planning prompt and waits for your approval before any worktree exists.">
        <SegmentedControl
          v-model="form.mode"
          :options="[
            { value: 'direct', label: 'Direct' },
            { value: 'plan-execution', label: 'Plan first' },
          ]"
          label="Execution mode"
        />
      </FormField>
      <FormField label="Worktrees" class="half">
        <SegmentedControl
          v-model="form.worktree"
          :options="[
            { value: 'enabled', label: 'Isolated worktrees' },
            { value: 'disabled', label: 'Workspace root' },
          ]"
          label="Worktree mode"
        />
      </FormField>
      <FormField label="Branch" for-id="task-branch" class="full" :help="form.worktree === 'enabled' ? 'Created from each repository’s default branch, or reused if it exists and has not diverged.' : 'Optional without worktrees.'">
        <TextInput
          id="task-branch"
          v-model="form.branch"
          mono
          placeholder="feature/health"
          :invalid="attempted && form.worktree === 'enabled' && !form.branch.trim()"
          @input="branchTouched = true"
        />
      </FormField>
      <FormField label="Repositories" class="full" help="With none selected, repositories marked selected_by_default are used.">
        <CheckList v-model="form.repos" :options="repositoryOptions" label="Repositories" />
      </FormField>
      <FormField label="Depends on" class="full" help="Descriptive only: dependencies appear in reports and do not block dispatch.">
        <CheckList v-model="form.dependencies" :options="dependencyOptions" label="Dependencies" />
      </FormField>
      <FormField label="Notes" for-id="task-notes" class="full" help="Also sent to the agent as the task’s latest notes.">
        <TextArea id="task-notes" v-model="form.notes" :rows="2" />
      </FormField>
    </form>
    <p v-if="modeChanged" class="warning">
      <TriangleAlert :size="15" aria-hidden="true" /> Changing the execution mode resets the planning state.
    </p>
    <CommandLine :command="command" />
    <ul v-if="attempted && problems.length" class="problems" role="alert">
      <li v-for="problem in problems" :key="problem">{{ problem }}</li>
    </ul>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <template #footer>
      <AppButton tone="quiet" @click="close">Cancel</AppButton>
      <AppButton type="submit" form="task-form" tone="primary" :loading="pending" data-testid="task-form-submit">
        {{ editing ? 'Save changes' : 'Create task' }}
      </AppButton>
    </template>
  </ModalDialog>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.narrow {
  grid-column: span 1;
}

.wide {
  grid-column: span 3;
}

.full {
  grid-column: 1 / -1;
}

.half {
  grid-column: span 2;
}

.quarter {
  grid-column: span 1;
}

.warning,
.error {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0 0 var(--space-3);
  padding: 8px 10px;
  border-radius: var(--radius);
  font-size: var(--text-sm);
}

.warning {
  background: var(--brass-soft);
  color: var(--brass);
}

.error {
  background: var(--danger-soft);
  color: var(--danger);
  font-weight: 600;
}

.problems {
  margin: var(--space-3) 0 0;
  padding-left: 1.2em;
  color: var(--danger);
  font-size: var(--text-sm);
}

@media (max-width: 720px) {
  .grid > * {
    grid-column: 1 / -1;
  }
}
</style>
