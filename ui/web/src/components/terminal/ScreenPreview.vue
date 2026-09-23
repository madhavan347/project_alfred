<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '@/api/http'
import type { PaneInfo } from '@/api/types'
import { ansiToHtml } from '@/lib/ansi'

/**
 * A lightweight, read-only view of a session's current screen. It polls `capture-pane` only
 * while visible and never attaches a tmux client, so it cannot resize or disturb the agent.
 */
const props = withDefaults(defineProps<{ session: string; interval?: number; maxFont?: number; minRows?: number }>(), {
  interval: 1500,
  maxFont: 12,
  minRows: 0,
})

const host = ref<HTMLDivElement>()
const content = ref('')
const pane = ref<PaneInfo | null>(null)
const failure = ref('')
const width = ref(0)
let timer: number | undefined
let visible = false
let observer: IntersectionObserver | null = null
let sizer: ResizeObserver | null = null
let inflight = false

const html = computed(() => ansiToHtml(trimTrailing(content.value)))
const fontSize = computed(() => {
  const columns = pane.value?.width || 80
  if (!width.value) return props.maxFont
  return Math.max(4.5, Math.min(props.maxFont, (width.value - 16) / (columns * 0.602)))
})

function trimTrailing(text: string): string {
  const lines = text.replace(/\n+$/, '').split('\n')
  return lines.join('\n')
}

async function poll() {
  if (!visible || document.visibilityState === 'hidden' || inflight) return schedule()
  inflight = true
  try {
    const result = await api.get<{ content: string; pane: PaneInfo | null }>(
      `/sessions/${encodeURIComponent(props.session)}/capture`,
    )
    content.value = result.content
    pane.value = result.pane
    failure.value = ''
  } catch (error) {
    failure.value = error instanceof Error ? error.message : String(error)
  } finally {
    inflight = false
    schedule()
  }
}

function schedule() {
  window.clearTimeout(timer)
  timer = window.setTimeout(poll, props.interval)
}

onMounted(() => {
  observer = new IntersectionObserver((entries) => {
    const wasVisible = visible
    visible = entries.some((entry) => entry.isIntersecting)
    if (visible && !wasVisible) void poll()
  })
  observer.observe(host.value!)
  sizer = new ResizeObserver((entries) => {
    width.value = entries[0]?.contentRect.width ?? 0
  })
  sizer.observe(host.value!)
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
  observer?.disconnect()
  sizer?.disconnect()
})

watch(
  () => props.session,
  () => {
    content.value = ''
    pane.value = null
    void poll()
  },
)

defineExpose({ refresh: poll })
</script>

<template>
  <div ref="host" class="preview" data-testid="screen-preview">
    <p v-if="failure" class="failure">{{ failure }}</p>
    <!-- ansiToHtml escapes all text and only emits styled span elements. -->
    <pre
      v-else
      class="screen"
      :style="{ fontSize: `${fontSize}px`, minHeight: minRows ? `${minRows * 1.25}em` : undefined }"
      v-html="html || '<span style=&quot;opacity:.5&quot;>Waiting for output…</span>'"
    />
  </div>
</template>

<style scoped>
.preview {
  background: var(--screen);
  color: var(--screen-ink);
  border-radius: var(--radius);
  padding: 8px;
  overflow: hidden;
  min-width: 0;
}

.screen {
  margin: 0;
  font-family: var(--font-mono);
  line-height: 1.25;
  white-space: pre;
  overflow: hidden;
}

.failure {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--screen-dim);
}
</style>
