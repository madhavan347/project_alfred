<script setup lang="ts">
import { computed } from 'vue'
import { Bot, UserRoundCog } from 'lucide-vue-next'
import type { AgentRun, TaskDetail } from '@/api/types'
import { absolute, duration, shortId } from '@/lib/format'
import { shellJoin } from '@/lib/cli'
import { RUN_META, runLamp } from '@/lib/status'
import { useDialogs } from '@/stores/dialogs'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'
import CopyButton from '@/components/base/CopyButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import KeyValue from '@/components/base/KeyValue.vue'
import LampDot from '@/components/base/LampDot.vue'
import RelativeTime from '@/components/base/RelativeTime.vue'
import TagChip from '@/components/base/TagChip.vue'

/** Which agents and models work on this task, how they are launched, and every run attempt. */
const props = defineProps<{ detail: TaskDetail }>()
const live = useLive()
const dialogs = useDialogs()

const task = computed(() => props.detail.task)
const assigned = computed(() => live.agentMap.get(task.value.assigned_agent_alias))
const runs = computed(() => [...props.detail.runs].reverse())

function sessionAlive(run: AgentRun): boolean {
  return live.sessionMap.has(run.session_name)
}
</script>

<template>
  <div class="agents">
    <section class="panel">
      <header class="panel-header">
        <UserRoundCog :size="16" aria-hidden="true" />
        <h3>Assigned agent</h3>
        <span class="spacer" />
        <AppButton size="sm" @click="dialogs.openAction(task.assigned_agent_alias ? 'reassign' : 'assign', task.task_number)">
          {{ task.assigned_agent_alias ? 'Reassign' : 'Assign' }}
        </AppButton>
      </header>
      <div class="panel-body">
        <EmptyState v-if="!task.assigned_agent_alias" compact title="No agent is assigned">
          Assign one of the configured agents before triggering.
        </EmptyState>
        <p v-else-if="!assigned" class="muted">
          <strong>{{ task.assigned_agent_alias }}</strong> is no longer in the configuration, so this task cannot be dispatched until it is reassigned.
        </p>
        <div v-else class="assigned">
          <div class="identity">
            <Bot :size="28" aria-hidden="true" />
            <div>
              <p class="alias">{{ assigned.alias }}</p>
              <p class="muted small">{{ assigned.cli }}<template v-if="assigned.model">, model {{ assigned.model }}</template></p>
            </div>
          </div>
          <KeyValue
            :items="[
              { label: 'Runtime target', value: assigned.runtime_target },
              { label: 'Executable', value: assigned.executable, mono: true },
              { label: 'Model', value: assigned.model || 'CLI default' },
            ]"
          />
          <div class="commands">
            <div v-for="phase in ['plan', 'execution', 'direct'] as const" :key="phase" class="command">
              <p class="phase">
                <strong>{{ phase === 'direct' ? 'Learner (direct)' : `${phase[0].toUpperCase()}${phase.slice(1)} phase` }}</strong>
                <TagChip :tone="assigned.prompt_delivery[phase] === 'argument' ? 'ok' : 'brass'">
                  {{ assigned.prompt_delivery[phase] === 'argument' ? 'prompt passed as an argument' : 'prompt pasted after start' }}
                </TagChip>
              </p>
              <code class="line">{{ shellJoin(assigned.commands[phase]) }}</code>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="panel">
      <header class="panel-header"><h3>Everyone involved</h3></header>
      <div class="panel-body table-scroll">
        <table v-if="task.derived.agents.length" class="table">
          <thead>
            <tr>
              <th scope="col">Agent</th>
              <th scope="col">CLI and model</th>
              <th scope="col">Role</th>
              <th scope="col">Runs</th>
              <th scope="col">Events</th>
              <th scope="col">Last seen</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="agent in task.derived.agents" :key="agent.alias">
              <td>
                <span class="row">
                  <LampDot color="var(--lamp-running)" :lit="agent.live" :size="8" :label="agent.live ? 'Session live' : 'No live session'" />
                  <strong>{{ agent.alias }}</strong>
                  <TagChip v-if="!agent.configured" tone="danger">not configured</TagChip>
                </span>
              </td>
              <td>{{ agent.cli || '—' }}<template v-if="agent.model">, {{ agent.model }}</template></td>
              <td>{{ agent.roles.join(', ') }}</td>
              <td>{{ agent.runs }}</td>
              <td>{{ agent.events }}</td>
              <td><RelativeTime :value="agent.last_seen" /></td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">No agent has touched this task yet.</p>
      </div>
    </section>

    <section class="panel">
      <header class="panel-header">
        <h3>Runs</h3>
        <span class="faint small">{{ detail.runs.length }} attempt{{ detail.runs.length === 1 ? '' : 's' }}</span>
      </header>
      <div class="panel-body runs">
        <p v-if="!runs.length" class="muted">Not dispatched yet.</p>
        <article v-for="run in runs" :key="run.run_id" class="run" :data-run="run.run_id">
          <header class="run-head">
            <LampDot :color="runLamp(run.run_status)" :lit="sessionAlive(run) && ['running', 'blocked'].includes(run.run_status)" />
            <strong>{{ RUN_META[run.run_status].label }}</strong>
            <span class="muted">{{ run.phase }} phase, {{ run.agent_alias }}</span>
            <span class="spacer" />
            <span class="mono small" :title="run.run_id">{{ shortId(run.run_id) }}</span>
            <CopyButton :text="run.run_id" />
          </header>
          <KeyValue
            :items="[
              { label: 'Started', value: absolute(run.started_at) },
              { label: 'Ended', value: run.ended_at ? absolute(run.ended_at) : 'Still active' },
              { label: 'Duration', value: duration(run.started_at, run.ended_at || null) },
              { label: 'Runtime target', value: run.runtime_target },
              { label: 'Session', value: run.session_name, mono: true },
              { label: 'Session status', value: `${run.session_status}${sessionAlive(run) ? ' (tmux session exists)' : ''}` },
              { label: 'Last event', value: absolute(run.last_event_at) },
              { label: 'Summary', value: run.summary },
            ]"
          />
          <p class="label small">Command</p>
          <code class="line">{{ run.command_preview || '—' }}</code>
          <template v-if="Object.keys(run.worktree_paths).length">
            <p class="label small">Worktrees</p>
            <ul class="paths">
              <li v-for="(path, repository) in run.worktree_paths" :key="repository">
                <strong>{{ repository }}</strong> <span class="mono small">{{ path }}</span>
              </li>
            </ul>
          </template>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.agents {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5) var(--space-6);
}

.assigned {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.identity {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.identity p {
  margin: 0;
}

.alias {
  font-size: var(--text-lg);
  font-weight: 750;
  font-stretch: 110%;
}

.commands {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.phase {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 4px;
  font-size: var(--text-sm);
}

.line {
  display: block;
  padding: 6px 10px;
  border-radius: var(--radius);
  background: var(--screen);
  color: var(--screen-ink);
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.runs {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.run {
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.run-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.label {
  margin: 4px 0 0;
  font-weight: 650;
  color: var(--ink-2);
}

.paths {
  list-style: none;
  margin: 0;
  padding: 0;
}
</style>
