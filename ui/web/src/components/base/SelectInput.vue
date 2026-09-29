<script setup lang="ts">
defineProps<{
  id?: string
  options: { value: string; label: string; hint?: string; disabled?: boolean }[]
  placeholder?: string
  invalid?: boolean
}>()
const model = defineModel<string>({ default: '' })
</script>

<template>
  <div class="select" :class="{ invalid }">
    <select :id="id" v-model="model" :aria-invalid="invalid || undefined">
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <option v-for="option in options" :key="option.value" :value="option.value" :disabled="option.disabled">
        {{ option.hint ? `${option.label} — ${option.hint}` : option.label }}
      </option>
    </select>
  </div>
</template>

<style scoped>
.select {
  position: relative;
}

.select::after {
  content: '';
  position: absolute;
  right: 12px;
  top: 50%;
  width: 7px;
  height: 7px;
  border-right: 1.5px solid var(--ink-2);
  border-bottom: 1.5px solid var(--ink-2);
  transform: translateY(-70%) rotate(45deg);
  pointer-events: none;
}

select {
  appearance: none;
  width: 100%;
  height: 34px;
  padding: 0 32px 0 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--ink);
  font-size: var(--text-base);
}

select:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 0;
}

.invalid select {
  border-color: var(--danger);
}
</style>
