<script setup lang="ts">
import { computed } from 'vue'
import LampDot from '@/components/base/LampDot.vue'

/**
 * Horizontal bars for one series across nominal categories: every bar in the same hue, the
 * category's identity carried by the label (and an optional status lamp beside it).
 */
const props = defineProps<{
  rows: { key: string; label: string; value: number; lamp?: string; note?: string }[]
  unit?: string
  caption: string
  format?: (value: number) => string
}>()

const max = computed(() => Math.max(1, ...props.rows.map((row) => row.value)))
const show = (value: number) => (props.format ? props.format(value) : value.toLocaleString())
</script>

<template>
  <figure class="bars">
    <figcaption class="visually-hidden">{{ caption }}</figcaption>
    <p v-if="!rows.length" class="muted small">No data yet.</p>
    <ul v-else class="rows">
      <li
        v-for="row in rows"
        :key="row.key"
        class="row"
        tabindex="0"
        :aria-label="`${row.label}: ${show(row.value)}${unit ? ` ${unit}` : ''}`"
        :title="`${row.label}: ${show(row.value)}${unit ? ` ${unit}` : ''}${row.note ? ` (${row.note})` : ''}`"
      >
        <span class="label">
          <LampDot v-if="row.lamp" :color="row.lamp" :size="8" />
          <span class="text">{{ row.label }}</span>
        </span>
        <span class="track" aria-hidden="true">
          <span class="bar" :style="{ width: `${(row.value / max) * 100}%` }" />
        </span>
        <span class="value">{{ show(row.value) }}</span>
      </li>
    </ul>
  </figure>
</template>

<style scoped>
.bars {
  margin: 0;
}

.rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row {
  display: grid;
  grid-template-columns: minmax(110px, 38%) 1fr 56px;
  align-items: center;
  gap: 10px;
  padding: 4px 6px;
  border-radius: var(--radius);
}

.row:hover,
.row:focus-visible {
  background: var(--panel-2);
}

.label {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: var(--text-sm);
}

.text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.track {
  height: 10px;
}

.bar {
  display: block;
  height: 10px;
  min-width: 2px;
  background: var(--accent);
  border-radius: 0 4px 4px 0;
}

.value {
  text-align: right;
  font-size: var(--text-sm);
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
</style>
