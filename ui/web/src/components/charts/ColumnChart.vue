<script setup lang="ts">
import { computed, ref } from 'vue'

/** Single-series columns over time with a hover and focus readout. */
const props = defineProps<{ points: { label: string; value: number }[]; caption: string; unit: string }>()
const width = 640
const height = 180
const pad = { top: 18, right: 8, bottom: 26, left: 32 }
const hover = ref<number | null>(null)

const niceMax = computed(() => {
  const max = Math.max(1, ...props.points.map((point) => point.value))
  const step = max <= 5 ? 1 : max <= 10 ? 2 : Math.ceil(max / 5)
  return Math.ceil(max / step) * step
})
const ticks = computed(() => {
  const step = niceMax.value <= 5 ? 1 : niceMax.value / 5
  const list: number[] = []
  for (let value = 0; value <= niceMax.value; value += step) list.push(Math.round(value))
  return list
})
const plotWidth = width - pad.left - pad.right
const plotHeight = height - pad.top - pad.bottom
const band = computed(() => plotWidth / Math.max(1, props.points.length))
const barWidth = computed(() => Math.max(3, Math.min(24, band.value - 2)))
const peak = computed(() => props.points.reduce((best, point, index) => (point.value > (props.points[best]?.value ?? -1) ? index : best), 0))
const y = (value: number) => pad.top + plotHeight - (value / niceMax.value) * plotHeight
const x = (index: number) => pad.left + index * band.value + (band.value - barWidth.value) / 2

function columnPath(index: number, value: number): string {
  const left = x(index)
  const top = y(value)
  const bottom = pad.top + plotHeight
  const w = barWidth.value
  const radius = Math.min(4, w / 2, bottom - top)
  return `M${left},${bottom} L${left},${top + radius} Q${left},${top} ${left + radius},${top} L${left + w - radius},${top} Q${left + w},${top} ${left + w},${top + radius} L${left + w},${bottom} Z`
}

const labelEvery = computed(() => Math.max(1, Math.ceil(props.points.length / 8)))
</script>

<template>
  <figure class="columns">
    <figcaption class="visually-hidden">{{ caption }}</figcaption>
    <p v-if="!points.length" class="muted small">No data yet.</p>
    <div v-else class="frame">
      <svg :viewBox="`0 0 ${width} ${height}`" role="img" :aria-label="caption" preserveAspectRatio="none">
        <g class="grid">
          <line v-for="tick in ticks" :key="tick" :x1="pad.left" :x2="width - pad.right" :y1="y(tick)" :y2="y(tick)" />
        </g>
        <g class="axis">
          <text v-for="tick in ticks" :key="`t${tick}`" :x="pad.left - 6" :y="y(tick) + 4" text-anchor="end">{{ tick }}</text>
          <template v-for="(point, index) in points" :key="`x${point.label}`">
            <text v-if="index % labelEvery === 0" :x="x(index) + barWidth / 2" :y="height - 8" text-anchor="middle">{{ point.label.slice(5) }}</text>
          </template>
        </g>
        <g>
          <path
            v-for="(point, index) in points"
            :key="point.label"
            class="column"
            :class="{ hovered: hover === index }"
            :d="columnPath(index, point.value)"
          />
          <text v-if="points[peak]?.value" class="peak" :x="x(peak) + barWidth / 2" :y="y(points[peak].value) - 5" text-anchor="middle">
            {{ points[peak].value }}
          </text>
          <rect
            v-for="(point, index) in points"
            :key="`hit${point.label}`"
            class="hit"
            :x="pad.left + index * band"
            :y="pad.top"
            :width="band"
            :height="plotHeight"
            tabindex="0"
            :aria-label="`${point.label}: ${point.value} ${unit}`"
            @pointerenter="hover = index"
            @pointerleave="hover = null"
            @focus="hover = index"
            @blur="hover = null"
          />
        </g>
      </svg>
      <div v-if="hover !== null && points[hover]" class="tooltip" role="status" :style="{ left: `${((x(hover) + barWidth / 2) / width) * 100}%` }">
        <strong>{{ points[hover].value }}</strong> {{ unit }}
        <span>{{ points[hover].label }}</span>
      </div>
    </div>
  </figure>
</template>

<style scoped>
.columns {
  margin: 0;
}

.frame {
  position: relative;
}

svg {
  width: 100%;
  height: 180px;
  overflow: visible;
}

.grid line {
  stroke: var(--line);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}

.axis text,
.peak {
  fill: var(--ink-2);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.peak {
  fill: var(--ink);
  font-weight: 650;
}

.column {
  fill: var(--accent);
}

.column.hovered {
  fill: var(--accent-hover);
}

.hit {
  fill: transparent;
  cursor: default;
  outline: none;
}

.tooltip {
  position: absolute;
  top: -6px;
  transform: translate(-50%, -100%);
  padding: 4px 8px;
  border-radius: var(--radius);
  background: var(--panel);
  border: 1px solid var(--line-strong);
  box-shadow: var(--shadow-float);
  font-size: var(--text-xs);
  white-space: nowrap;
  pointer-events: none;
}

.tooltip span {
  color: var(--ink-2);
  margin-left: 4px;
}
</style>
