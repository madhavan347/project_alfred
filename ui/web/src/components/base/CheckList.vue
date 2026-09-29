<script setup lang="ts">
defineProps<{ options: { value: string; label: string; hint?: string; disabled?: boolean }[]; label?: string }>()
const model = defineModel<string[]>({ default: () => [] })

function toggle(value: string, checked: boolean) {
  const next = new Set(model.value)
  if (checked) next.add(value)
  else next.delete(value)
  model.value = [...next]
}
</script>

<template>
  <div class="checklist" role="group" :aria-label="label">
    <p v-if="!options.length" class="none">Nothing to choose from.</p>
    <label v-for="option in options" :key="option.value" class="item" :class="{ disabled: option.disabled }">
      <input
        type="checkbox"
        :checked="model.includes(option.value)"
        :disabled="option.disabled"
        @change="toggle(option.value, ($event.target as HTMLInputElement).checked)"
      />
      <span class="name">{{ option.label }}</span>
      <span v-if="option.hint" class="hint">{{ option.hint }}</span>
    </label>
  </div>
</template>

<style scoped>
.checklist {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  cursor: pointer;
  font-size: var(--text-sm);
}

.item:has(input:checked) {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.name {
  font-weight: 600;
}

.hint {
  color: var(--ink-2);
  font-size: var(--text-xs);
}

.none {
  margin: 0;
  color: var(--ink-2);
  font-size: var(--text-sm);
}
</style>
