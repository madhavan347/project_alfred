<script setup lang="ts">
defineProps<{ id?: string; placeholder?: string; rows?: number; mono?: boolean; invalid?: boolean }>()
const model = defineModel<string>({ default: '' })
</script>

<template>
  <textarea
    :id="id"
    v-model="model"
    class="area"
    :class="{ mono, invalid }"
    :rows="rows ?? 3"
    :placeholder="placeholder"
    :aria-invalid="invalid || undefined"
  />
</template>

<style scoped>
.area {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  color: var(--ink);
  font-size: var(--text-base);
  line-height: 1.45;
  resize: vertical;
}

.area.mono {
  font-family: var(--font-mono);
  font-size: 12.5px;
}

.area::placeholder {
  color: var(--ink-3);
}

.area:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 0;
  border-color: var(--focus);
}

.area.invalid {
  border-color: var(--danger);
}
</style>
