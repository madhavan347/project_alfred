<script setup lang="ts">
defineProps<{
  id?: string
  placeholder?: string
  mono?: boolean
  type?: string
  disabled?: boolean
  invalid?: boolean
  autofocus?: boolean
}>()
const model = defineModel<string | number>({ default: '' })
</script>

<template>
  <input
    :id="id"
    v-model="model"
    class="input"
    :class="{ mono, invalid }"
    :type="type ?? 'text'"
    :placeholder="placeholder"
    :disabled="disabled"
    :aria-invalid="invalid || undefined"
    :autofocus="autofocus"
    spellcheck="false"
  />
</template>

<style scoped>
.input {
  width: 100%;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--ink);
  font-size: var(--text-base);
}

.input.mono {
  font-family: var(--font-mono);
  font-size: 13px;
}

.input::placeholder {
  color: var(--ink-3);
}

.input:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 0;
  border-color: var(--focus);
}

.input.invalid {
  border-color: var(--danger);
}

.input:disabled {
  opacity: 0.6;
}
</style>
