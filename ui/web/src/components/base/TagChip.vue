<script setup lang="ts">
defineProps<{ mono?: boolean; tone?: 'default' | 'brass' | 'danger' | 'ok' | 'accent'; title?: string }>()
</script>

<template>
  <span class="chip" :class="[`tone-${tone ?? 'default'}`, { mono }]" :title="title"><slot /></span>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  height: 20px;
  padding: 0 6px;
  border-radius: var(--radius-s);
  background: var(--panel-2);
  color: var(--ink-2);
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chip.mono {
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: 11px;
}

.tone-brass {
  background: var(--brass-soft);
  color: var(--brass);
}

.tone-danger {
  background: var(--danger-soft);
  color: var(--danger);
}

.tone-ok {
  background: var(--ok-soft);
  color: var(--ok);
}

.tone-accent {
  background: var(--accent-soft);
  color: var(--accent);
}
</style>
