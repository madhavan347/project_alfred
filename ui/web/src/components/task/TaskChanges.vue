<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FolderGit2, GitBranch, GitCommitHorizontal, Plus, Trash2, Upload } from 'lucide-vue-next'
import { api } from '@/api/http'
import type { TaskDetail, WorktreeDetail } from '@/api/types'
import { absolute } from '@/lib/format'
import { completedActions, errorMessage } from '@/composables/useRequest'
import { useDialogs } from '@/stores/dialogs'
import AppButton from '@/components/base/AppButton.vue'
import CopyButton from '@/components/base/CopyButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import TagChip from '@/components/base/TagChip.vue'
import DiffView from '@/components/misc/DiffView.vue'

/** The task's worktrees: uncommitted changes, commits on the branch, push state, and diffs. */
const props = defineProps<{ detail: TaskDetail }>()
const dialogs = useDialogs()
const worktrees = ref<WorktreeDetail[]>([])
const failure = ref('')
const loading = ref(false)
const view = ref<Record<string, 'working' | 'branch'>>({})

const task = computed(() => props.detail.task)
const signature = computed(() => JSON.stringify(task.value.derived.worktrees) + task.value.updated_at)

async function load() {
  loading.value = worktrees.value.length === 0
  try {
    const result = await api.get<{ worktrees: WorktreeDetail[] }>(`/tasks/${task.value.task_number}/worktrees?diff=true`)
    worktrees.value = result.worktrees
    failure.value = ''
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}

watch([signature, completedActions], load, { immediate: true })

// Agents can commit without changing anything Alfred records, so poll while the tab is open.
let timer: number | undefined
onMounted(() => {
  timer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void load()
  }, 5000)
})
onBeforeUnmount(() => window.clearInterval(timer))

function mode(repository: string): 'working' | 'branch' {
  return view.value[repository] ?? 'working'
}
</script>

<template>
  <div class="changes">
    <div class="toolbar">
      <AppButton size="sm" :icon="Plus" :disabled="!task.derived.actions.worktree_create.enabled" :title="task.derived.actions.worktree_create.reason" @click="dialogs.openAction('worktree_create', task.task_number)">
        Create worktrees
      </AppButton>
      <AppButton size="sm" tone="primary" :icon="GitCommitHorizontal" :disabled="!task.derived.actions.commit.enabled" :title="task.derived.actions.commit.reason" @click="dialogs.openAction('commit', task.task_number)">
        Commit
      </AppButton>
      <AppButton size="sm" tone="brass" :icon="Upload" :disabled="!task.derived.actions.push.enabled" :title="task.derived.actions.push.reason" @click="dialogs.openAction('push', task.task_number)">
        Push
      </AppButton>
      <span class="spacer" />
      <AppButton size="sm" tone="danger" :icon="Trash2" :disabled="!task.derived.actions.remove_worktrees.enabled" :title="task.derived.actions.remove_worktrees.reason" @click="dialogs.openAction('remove_worktrees', task.task_number)">
        Remove worktrees
      </AppButton>
    </div>

    <p v-if="failure" class="failure">{{ failure }}</p>
    <p v-else-if="loading" class="muted">Reading worktrees…</p>
    <EmptyState v-else-if="!worktrees.length" :icon="FolderGit2" title="No worktrees for this task">
      <template v-if="task.worktree_mode === 'disabled'">Worktrees are disabled; the agent works in the workspace root.</template>
      <template v-else-if="task.execution_mode === 'plan-execution' && task.planning_state !== 'completed' && task.planning_state !== 'approved'">
        Plan-first tasks get their worktrees when the plan is approved.
      </template>
      <template v-else>Worktrees are created when the task is triggered, or create them now.</template>
    </EmptyState>

    <section v-for="worktree in worktrees" :key="worktree.repository" class="panel worktree" :data-repository="worktree.repository">
      <header class="panel-header head">
        <h3>{{ worktree.repository }}</h3>
        <TagChip mono><GitBranch :size="11" aria-hidden="true" />{{ worktree.branch || 'detached' }}</TagChip>
        <TagChip v-if="worktree.dirty" tone="brass">{{ worktree.changes.length }} uncommitted</TagChip>
        <TagChip v-else tone="ok">clean</TagChip>
        <span class="spacer" />
        <span class="mono small path" :title="worktree.path">{{ worktree.path }}</span>
        <CopyButton :text="worktree.path" />
      </header>
      <div class="panel-body stack">
        <dl class="facts">
          <div>
            <dt>Head</dt>
            <dd><span class="mono">{{ worktree.head }}</span> {{ worktree.head_subject }}</dd>
          </div>
          <div>
            <dt>Against {{ worktree.base || 'default branch' }}</dt>
            <dd>{{ worktree.ahead ?? '?' }} ahead, {{ worktree.behind ?? '?' }} behind</dd>
          </div>
          <div>
            <dt>Remote {{ worktree.remote.remote }}</dt>
            <dd>
              <template v-if="!worktree.remote.exists">Not pushed yet</template>
              <template v-else-if="worktree.remote.unpushed">{{ worktree.remote.unpushed }} commit{{ worktree.remote.unpushed === 1 ? '' : 's' }} not pushed</template>
              <template v-else>Up to date with {{ worktree.remote.ref.replace('refs/remotes/', '') }}</template>
            </dd>
          </div>
        </dl>

        <div v-if="worktree.changes.length" class="changed">
          <h4>Uncommitted files</h4>
          <ul>
            <li v-for="change in worktree.changes" :key="change.path">
              <TagChip :tone="change.label === 'deleted' || change.label === 'conflict' ? 'danger' : change.label === 'untracked' || change.label === 'added' ? 'ok' : 'default'">
                {{ change.label }}
              </TagChip>
              <span class="mono small">{{ change.original ? `${change.original} → ` : '' }}{{ change.path }}</span>
            </li>
          </ul>
        </div>

        <div v-if="worktree.commits.length" class="commits">
          <h4>Commits on this branch</h4>
          <ul>
            <li v-for="commit in worktree.commits" :key="commit.hash">
              <span class="mono small">{{ commit.short }}</span>
              <span class="subject">{{ commit.subject }}</span>
              <span class="faint small">{{ commit.author }}, {{ absolute(commit.date) }}</span>
            </li>
          </ul>
        </div>

        <SegmentedControl
          :model-value="mode(worktree.repository)"
          :options="[
            { value: 'working', label: 'Uncommitted diff' },
            { value: 'branch', label: `Branch vs ${worktree.base || 'base'}` },
          ]"
          label="Diff"
          @update:model-value="view[worktree.repository] = $event as 'working' | 'branch'"
        />
        <template v-if="mode(worktree.repository) === 'working'">
          <pre v-if="worktree.diff_stat" class="stat">{{ worktree.diff_stat }}</pre>
          <DiffView :text="worktree.diff?.text ?? ''" :truncated="worktree.diff?.truncated" empty-label="No changes to tracked files." />
          <div v-for="file in worktree.untracked ?? []" :key="file.path" class="untracked">
            <h4><span class="mono">{{ file.path }}</span> <span class="faint small">new file</span></h4>
            <p v-if="file.binary" class="muted small">Binary file.</p>
            <pre v-else class="stat">{{ file.content }}{{ file.truncated ? '\n…' : '' }}</pre>
          </div>
        </template>
        <template v-else>
          <pre v-if="worktree.committed_stat" class="stat">{{ worktree.committed_stat }}</pre>
          <DiffView :text="worktree.committed_diff?.text ?? ''" :truncated="worktree.committed_diff?.truncated" empty-label="No commits on this branch yet." />
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped>
.changes {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5) var(--space-6);
}

.toolbar {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.failure {
  color: var(--danger);
}

.head {
  flex-wrap: wrap;
}

.path {
  max-width: 40ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--ink-3);
}

.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr));
  gap: var(--space-3);
  margin: 0;
}

.facts dt {
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.facts dd {
  margin: 2px 0 0;
  font-size: var(--text-sm);
}

.changed ul,
.commits ul {
  list-style: none;
  margin: 6px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.changed li,
.commits li {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.subject {
  font-weight: 600;
  font-size: var(--text-sm);
}

.stat {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius);
  background: var(--panel-2);
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: pre-wrap;
  overflow-x: auto;
}

.untracked h4 {
  margin: var(--space-2) 0 4px;
}
</style>
