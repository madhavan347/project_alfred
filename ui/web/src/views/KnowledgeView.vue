<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BookOpen, BookPlus, Search } from 'lucide-vue-next'
import { api, query } from '@/api/http'
import type { KnowledgeEntry } from '@/api/types'
import { absolute } from '@/lib/format'
import { KNOWLEDGE_CATEGORIES } from '@/lib/status'
import { alfredCommand } from '@/lib/cli'
import { completedActions, errorMessage } from '@/composables/useRequest'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'
import CommandLine from '@/components/base/CommandLine.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import MarkdownView from '@/components/base/MarkdownView.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import TagChip from '@/components/base/TagChip.vue'
import WorkspaceProblem from '@/components/layout/WorkspaceProblem.vue'

/** The categorized Markdown knowledge that agents and people record while finishing work. */
const live = useLive()
const dialogs = useDialogs()
const route = useRoute()
const router = useRouter()
const category = ref('')
const task = ref('')
const search = ref('')
const entries = ref<KnowledgeEntry[]>([])
const selected = ref('')
const failure = ref('')
const directory = ref('')

// After you add an entry, show it; entries other people or agents add do not steal the selection.
let showNewest = false
watch(completedActions, () => {
  showNewest = true
})

async function load() {
  try {
    const known = new Set(entries.value.map((entry) => entry.relative))
    const result = await api.get<{ entries: KnowledgeEntry[]; directory: string }>(
      `/knowledge${query({ category: category.value, task: task.value })}`,
    )
    entries.value = result.entries
    directory.value = result.directory
    failure.value = ''
    const added = known.size ? entries.value.find((entry) => !known.has(entry.relative)) : undefined
    if (added && showNewest) {
      selected.value = added.relative
      showNewest = false
    } else if (!entries.value.some((entry) => entry.relative === selected.value)) {
      selected.value = entries.value[0]?.relative ?? ''
    }
  } catch (error) {
    failure.value = errorMessage(error)
  }
}

watch([category, task, () => live.snapshot?.knowledge?.total], load, { immediate: true })

const visible = computed(() => {
  const needle = search.value.trim().toLowerCase()
  return entries.value.filter((entry) => !needle || `${entry.title} ${entry.content}`.toLowerCase().includes(needle))
})
const current = computed(() => entries.value.find((entry) => entry.relative === selected.value))
const command = computed(() => alfredCommand('knowledge', 'list', ['--category', category.value]))

function openTask(number: number | null) {
  if (number !== null) void router.push({ path: route.path, query: { ...route.query, task: String(number), tab: 'files' } })
}
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div>
        <h1>Knowledge</h1>
        <p>
          Reusable learnings in {{ directory || 'the knowledge directory' }}. A successful completion needs
          {{ live.config?.knowledge.required_completion_entries ?? 0 }} entr{{ live.config?.knowledge.required_completion_entries === 1 ? 'y' : 'ies' }}
          for its task.
        </p>
      </div>
      <span class="spacer" />
      <AppButton tone="primary" :icon="BookPlus" :disabled="!live.config" @click="dialogs.openAction('knowledge', task ? Number(task) : null)">Add entry</AppButton>
    </header>

    <WorkspaceProblem />

    <div class="filters">
      <SegmentedControl
        v-model="category"
        :options="[{ value: '', label: 'All' }, ...KNOWLEDGE_CATEGORIES.map((value) => ({ value, label: value }))]"
        label="Category"
      />
      <label class="visually-hidden" for="knowledge-task">Task</label>
      <select id="knowledge-task" v-model="task" class="control">
        <option value="">Every task</option>
        <option v-for="item in live.tasks" :key="item.task_number" :value="String(item.task_number)">#{{ item.task_number }} {{ item.title }}</option>
      </select>
      <label class="search">
        <Search :size="15" aria-hidden="true" />
        <span class="visually-hidden">Search entries</span>
        <input v-model="search" type="search" placeholder="Search titles and content" />
      </label>
      <CommandLine class="command" :command="command" />
    </div>

    <p v-if="failure" class="failure">{{ failure }}</p>
    <EmptyState v-else-if="!visible.length" :icon="BookOpen" title="No knowledge entries">
      Agents add entries with <code>alfred knowledge add</code> before completing, and so can you.
    </EmptyState>

    <div v-else class="layout">
      <ul class="list panel" aria-label="Entries">
        <li v-for="entry in visible" :key="entry.relative">
          <button type="button" class="entry" :class="{ active: entry.relative === selected }" @click="selected = entry.relative">
            <span class="title">{{ entry.title }}</span>
            <span class="meta">
              <TagChip>{{ entry.category }}</TagChip>
              <span v-if="entry.task_number !== null">#{{ entry.task_number }}</span>
              <span v-if="entry.agent">{{ entry.agent }}</span>
            </span>
          </button>
        </li>
      </ul>
      <article v-if="current" class="panel reader">
        <header class="panel-header">
          <h2>{{ current.title }}</h2>
        </header>
        <div class="panel-body stack">
          <p class="row small muted">
            <TagChip>{{ current.category }}</TagChip>
            <button v-if="current.task_number !== null" type="button" class="task" @click="openTask(current.task_number)">Task #{{ current.task_number }}</button>
            <span v-if="current.agent">by {{ current.agent }}</span>
            <span>{{ absolute(current.created) }}</span>
          </p>
          <MarkdownView :source="current.summary || current.content" />
          <p v-if="current.files.length" class="small"><strong>Files:</strong> <span class="mono">{{ current.files.join(', ') }}</span></p>
          <p v-if="current.repositories.length" class="small"><strong>Repositories:</strong> {{ current.repositories.join(', ') }}</p>
          <p class="faint tiny mono">{{ current.path }}</p>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.control {
  height: 34px;
  padding: 0 8px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  max-width: 260px;
}

.search {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--ink-2);
}

.search input {
  border: 0;
  outline: none;
  background: transparent;
  color: var(--ink);
}

.command {
  flex: 1;
  min-width: min(240px, 100%);
}

.layout {
  display: grid;
  grid-template-columns: 340px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.list {
  list-style: none;
  margin: 0;
  padding: 6px;
  max-height: 72vh;
  overflow-y: auto;
}

.entry {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 8px 10px;
  border-radius: var(--radius);
  text-align: left;
  cursor: pointer;
}

.entry:hover {
  background: var(--panel-2);
}

.entry.active {
  background: var(--accent-soft);
}

.title {
  font-weight: 650;
}

.meta {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.task {
  border: 0;
  background: none;
  color: var(--accent);
  padding: 0;
  cursor: pointer;
  font-weight: 600;
}

.failure {
  color: var(--danger);
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
