<script setup lang="ts">
import { computed } from 'vue'
import CopyButton from './CopyButton.vue'
import { usePrefs } from '@/stores/prefs'
import { useLive } from '@/stores/live'
import { shellQuote } from '@/lib/cli'

/** The `alfred` command equivalent to an action, shown so every change is reproducible. */
const props = defineProps<{ command: string | null; label?: string }>()
const prefs = usePrefs()
const live = useLive()

const shown = computed(() => {
  if (!props.command) return ''
  const path = live.snapshot?.workspace.config_path
  if (!prefs.values.includeConfigInCommands || !path) return props.command
  return props.command.replace(/^alfred /gm, `alfred --config ${shellQuote(path)} `)
})
</script>

<template>
  <div v-if="shown" class="command">
    <span class="caption">{{ label ?? 'Same as' }}</span>
    <code class="text">{{ shown }}</code>
    <CopyButton :text="shown" label="Copy" />
  </div>
</template>

<style scoped>
.command {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: 8px 10px;
  border-radius: var(--radius);
  background: var(--screen);
  color: var(--screen-ink);
}

.caption {
  flex: none;
  font-size: var(--text-xs);
  color: var(--screen-dim);
  padding-top: 1px;
}

.text {
  flex: 1;
  min-width: 0;
  background: none;
  padding: 0;
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--screen-ink);
}
</style>
