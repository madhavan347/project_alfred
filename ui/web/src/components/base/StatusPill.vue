<script setup lang="ts">
import LampDot from './LampDot.vue'

defineProps<{ label: string; color: string; lit?: boolean; pulse?: boolean; title?: string }>()
</script>

<template>
  <span class="pill" :title="title" :style="{ '--pill': color }">
    <LampDot :color="color" :lit="lit ?? true" :pulse="pulse" :size="8" />
    <span>{{ label }}</span>
  </span>
</template>

<style scoped>
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 22px;
  padding: 0 8px 0 7px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--pill) 40%, var(--line));
  background: color-mix(in srgb, var(--pill) 10%, var(--panel));
  color: var(--ink);
  font-size: var(--text-xs);
  font-weight: 600;
  white-space: nowrap;
}
</style>
