<script setup lang="ts">
import type { Component } from 'vue'
import { LoaderCircle } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    tone?: 'default' | 'primary' | 'danger' | 'brass' | 'quiet'
    size?: 'sm' | 'md'
    icon?: Component
    loading?: boolean
    disabled?: boolean
    type?: 'button' | 'submit'
    title?: string
  }>(),
  { tone: 'default', size: 'md', type: 'button' },
)
</script>

<template>
  <button
    :type="type"
    class="button"
    :class="[`tone-${tone}`, `size-${size}`, { loading }]"
    :disabled="disabled || loading"
    :title="title"
    :aria-busy="loading || undefined"
  >
    <LoaderCircle v-if="loading" class="icon spin" :size="size === 'sm' ? 14 : 16" aria-hidden="true" />
    <component :is="icon" v-else-if="icon" class="icon" :size="size === 'sm' ? 14 : 16" aria-hidden="true" />
    <span v-if="$slots.default" class="label"><slot /></span>
  </button>
</template>

<style scoped>
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--line-strong);
  background: var(--panel);
  color: var(--ink);
  border-radius: var(--radius);
  font-weight: 600;
  font-stretch: 96%;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background 120ms var(--ease),
    border-color 120ms var(--ease),
    color 120ms var(--ease);
}

.size-md {
  height: 34px;
  padding: 0 14px;
  font-size: var(--text-base);
}

.size-sm {
  height: 28px;
  padding: 0 10px;
  font-size: var(--text-sm);
}

.button:hover:not(:disabled) {
  background: var(--panel-2);
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.tone-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-ink);
}

.tone-primary:hover:not(:disabled) {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}

.tone-danger {
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 45%, var(--line));
}

.tone-danger:hover:not(:disabled) {
  background: var(--danger-soft);
}

.tone-brass {
  color: var(--brass);
  border-color: var(--brass-line);
  background: var(--brass-soft);
}

.tone-brass:hover:not(:disabled) {
  background: color-mix(in srgb, var(--brass-soft) 70%, var(--brass-line));
}

.tone-quiet {
  border-color: transparent;
  background: transparent;
  color: var(--ink-2);
}

.tone-quiet:hover:not(:disabled) {
  background: var(--panel-2);
  color: var(--ink);
}

.spin {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
