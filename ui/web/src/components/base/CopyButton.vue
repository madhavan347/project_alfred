<script setup lang="ts">
import { ref } from 'vue'
import { Check, Copy } from 'lucide-vue-next'

const props = defineProps<{ text: string; label?: string }>()
const copied = ref(false)

async function copy() {
  try {
    await navigator.clipboard.writeText(props.text)
  } catch {
    const area = document.createElement('textarea')
    area.value = props.text
    document.body.append(area)
    area.select()
    document.execCommand('copy')
    area.remove()
  }
  copied.value = true
  window.setTimeout(() => (copied.value = false), 1400)
}
</script>

<template>
  <button type="button" class="copy" :title="label ?? 'Copy'" :aria-label="label ?? 'Copy'" @click.stop="copy">
    <Check v-if="copied" :size="14" aria-hidden="true" />
    <Copy v-else :size="14" aria-hidden="true" />
    <span v-if="label" class="text">{{ copied ? 'Copied' : label }}</span>
  </button>
</template>

<style scoped>
.copy {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  color: inherit;
  opacity: 0.75;
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-s);
  font-size: var(--text-xs);
}

.copy:hover {
  opacity: 1;
  background: color-mix(in srgb, currentColor 12%, transparent);
}
</style>
