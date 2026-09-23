<script setup lang="ts">
defineProps<{ options: { value: string; label: string; disabled?: boolean; hint?: string }[]; label?: string }>()
const model = defineModel<string>({ default: '' })
</script>

<template>
  <div class="segmented" role="radiogroup" :aria-label="label">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      class="segment"
      :class="{ active: model === option.value }"
      :aria-checked="model === option.value"
      :disabled="option.disabled"
      :title="option.hint"
      @click="model = option.value"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.segmented {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel-2);
}

.segment {
  border: 0;
  background: transparent;
  color: var(--ink-2);
  padding: 5px 10px;
  border-radius: 4px;
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}

.segment:hover:not(:disabled) {
  color: var(--ink);
}

.segment.active {
  background: var(--panel);
  color: var(--ink);
  box-shadow: 0 0 0 1px var(--line-strong);
}

.segment:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
