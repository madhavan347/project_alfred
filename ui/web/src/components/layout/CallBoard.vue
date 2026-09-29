<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { BellRing, Cog } from 'lucide-vue-next'
import { api } from '@/api/http'
import { useRequest } from '@/composables/useRequest'
import { useLive, type Call } from '@/stores/live'

/** The strip of everything waiting on a person: reviews, plans, failures, and dead sessions. */
const live = useLive()
const route = useRoute()
const router = useRouter()
const { pending, run } = useRequest()

function open(call: Call) {
  if (call.task === null) return
  const tab = call.kind === 'plan' ? 'plan' : call.kind === 'session' ? 'agents' : 'overview'
  void router.push({ path: route.path, query: { ...route.query, task: String(call.task), tab } })
}

async function processCompletions() {
  await run(() => api.post('/coordinator/once'), { command: 'alfred coordinator once' })
}
</script>

<template>
  <section v-if="live.calls.length" class="callboard" aria-label="Needs your attention">
    <span class="heading">
      <BellRing :size="16" aria-hidden="true" />
      Needs you
    </span>
    <ul class="calls">
      <li v-for="call in live.calls" :key="call.key">
        <button
          v-if="call.kind !== 'completions'"
          type="button"
          class="call"
          :class="call.tone"
          :title="call.detail"
          :data-call="call.kind"
          @click="open(call)"
        >
          <span class="number">#{{ call.task }}</span>
          <span class="what">{{ call.label }}</span>
        </button>
        <span v-else class="call brass waiting" :title="call.detail" data-call="completions">
          <span class="what">{{ call.label }}</span>
          <button type="button" class="inline" :disabled="pending" @click="processCompletions">
            <Cog :size="13" aria-hidden="true" /> Process now
          </button>
        </span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.callboard {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 8px var(--space-5);
  border-bottom: 1px solid var(--brass-line);
  background: var(--brass-soft);
  overflow-x: auto;
  scrollbar-width: thin;
}

.heading {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: none;
  color: var(--brass);
  font-weight: 750;
  font-stretch: 112%;
  font-size: var(--text-sm);
}

.calls {
  display: flex;
  gap: 6px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.call {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  border-radius: var(--radius);
  border: 1px solid var(--brass-line);
  background: var(--panel);
  color: var(--ink);
  font-size: var(--text-sm);
  cursor: pointer;
  white-space: nowrap;
}

button.call:hover {
  border-color: var(--brass);
}

.call.danger {
  border-color: color-mix(in srgb, var(--danger) 50%, var(--line));
  color: var(--danger);
}

.number {
  font-weight: 750;
  font-feature-settings: 'tnum' 1;
}

.waiting {
  cursor: default;
}

.inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: var(--brass-strong);
  color: #fff;
  border-radius: var(--radius-s);
  padding: 2px 8px;
  font-size: var(--text-xs);
  font-weight: 650;
  cursor: pointer;
}
</style>
