<script setup lang="ts">
import { computed } from 'vue'
import CopyButton from '@/components/base/CopyButton.vue'

const props = defineProps<{ value?: unknown; raw?: string; maxHeight?: string }>()
const text = computed(() => {
  if (props.raw !== undefined) {
    try {
      return JSON.stringify(JSON.parse(props.raw), null, 2)
    } catch {
      return props.raw
    }
  }
  return JSON.stringify(props.value, null, 2)
})
</script>

<template>
  <div class="json">
    <CopyButton class="copy" :text="text" label="Copy" />
    <pre class="scroll-y" :style="{ maxHeight: maxHeight ?? '360px' }">{{ text }}</pre>
  </div>
</template>

<style scoped>
.json {
  position: relative;
}

.copy {
  position: absolute;
  top: 6px;
  right: 6px;
  color: var(--screen-ink);
}

pre {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: var(--screen);
  color: var(--screen-ink);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
