<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{ title: string; icon?: Component; compact?: boolean }>()
</script>

<template>
  <div class="empty" :class="{ compact }">
    <component :is="icon" v-if="icon" :size="compact ? 20 : 28" class="icon" aria-hidden="true" />
    <p class="title">{{ title }}</p>
    <p v-if="$slots.default" class="body"><slot /></p>
    <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-6);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius-l);
  color: var(--ink-2);
}

.empty.compact {
  padding: var(--space-4);
}

.icon {
  color: var(--ink-3);
}

.title {
  margin: 0;
  font-weight: 650;
  color: var(--ink);
}

.body {
  margin: 0;
  max-width: 60ch;
}

.actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-2);
}
</style>
