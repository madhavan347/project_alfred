<script setup lang="ts">
import { onMounted, ref, watch, type Component } from 'vue'

const props = defineProps<{
  tabs: { key: string; label: string; icon?: Component; badge?: string | number | null; tone?: 'brass' | 'danger' | null }[]
  label: string
}>()
const model = defineModel<string>({ required: true })
const list = ref<HTMLElement | null>(null)

/** Scroll the tab strip (never the page) so the selected tab is visible on narrow screens. */
function reveal() {
  const container = list.value
  const active = container?.querySelector<HTMLElement>('.tab.active')
  if (!container || !active) return
  const box = container.getBoundingClientRect()
  const tab = active.getBoundingClientRect()
  if (tab.left < box.left) container.scrollLeft -= box.left - tab.left + 16
  else if (tab.right > box.right) container.scrollLeft += tab.right - box.right + 16
}

onMounted(reveal)
watch(model, reveal, { flush: 'post' })

function move(event: KeyboardEvent, index: number) {
  const direction = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
  if (!direction) return
  event.preventDefault()
  const next = (index + direction + props.tabs.length) % props.tabs.length
  model.value = props.tabs[next].key
  const buttons = (event.currentTarget as HTMLElement).parentElement?.querySelectorAll<HTMLButtonElement>('[role=tab]')
  buttons?.[next]?.focus()
}
</script>

<template>
  <div ref="list" class="tabs" role="tablist" :aria-label="label">
    <button
      v-for="(tab, index) in tabs"
      :key="tab.key"
      type="button"
      role="tab"
      class="tab"
      :class="{ active: model === tab.key }"
      :aria-selected="model === tab.key"
      :tabindex="model === tab.key ? 0 : -1"
      :data-tab="tab.key"
      @click="model = tab.key"
      @keydown="move($event, index)"
    >
      <component :is="tab.icon" v-if="tab.icon" :size="15" aria-hidden="true" />
      <span>{{ tab.label }}</span>
      <span v-if="tab.badge !== null && tab.badge !== undefined && tab.badge !== ''" class="badge" :class="tab.tone">
        {{ tab.badge }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 2px;
  overflow-x: auto;
  scrollbar-width: none;
  border-bottom: 1px solid var(--line);
  padding: 0 var(--space-4);
}

.tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--ink-2);
  padding: 10px 10px 9px;
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  white-space: nowrap;
}

.tab:hover {
  color: var(--ink);
}

.tab.active {
  color: var(--ink);
  border-bottom-color: var(--accent);
}

.badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--panel-2);
  color: var(--ink-2);
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.badge.brass {
  background: var(--brass-soft);
  color: var(--brass);
}

.badge.danger {
  background: var(--danger-soft);
  color: var(--danger);
}
</style>
