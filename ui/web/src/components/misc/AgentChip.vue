<script setup lang="ts">
import { computed } from 'vue'
import { Bot } from 'lucide-vue-next'
import type { InvolvedAgent } from '@/api/types'
import { useLive } from '@/stores/live'
import LampDot from '@/components/base/LampDot.vue'

/** An agent involved in a task: alias, the CLI and model it runs, and whether it is live. */
const props = defineProps<{ agent: InvolvedAgent; session?: string | null; detailed?: boolean }>()
const live = useLive()
const description = computed(() => {
  const parts = [props.agent.cli, props.agent.model ? `model ${props.agent.model}` : '']
  return parts.filter(Boolean).join(', ')
})
const title = computed(
  () =>
    `${props.agent.alias}${description.value ? ` (${description.value})` : ''}` +
    `${props.agent.live ? ', session live' : ''}; ${props.agent.roles.join(', ')}`,
)
</script>

<template>
  <span class="agent" :class="{ assigned: agent.assigned, missing: !agent.configured }" :title="title">
    <LampDot v-if="agent.live" color="var(--lamp-running)" :size="7" :pulse="live.isBusy(session)" />
    <Bot v-else :size="13" aria-hidden="true" />
    <span class="alias">{{ agent.alias }}</span>
    <span v-if="detailed || agent.model" class="model">{{ agent.model || agent.cli }}</span>
  </span>
</template>

<style scoped>
.agent {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 22px;
  max-width: 100%;
  padding: 0 7px;
  border-radius: 11px;
  border: 1px solid var(--line);
  background: var(--panel);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
}

.agent.assigned {
  color: var(--ink);
  border-color: var(--line-strong);
}

.agent.missing {
  border-style: dashed;
}

.alias {
  overflow: hidden;
  text-overflow: ellipsis;
}

.model {
  font-weight: 500;
  color: var(--ink-3);
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
