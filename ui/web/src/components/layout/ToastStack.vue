<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { X } from 'lucide-vue-next'
import { useToasts } from '@/stores/toasts'

const toasts = useToasts()
const route = useRoute()
const router = useRouter()

function openTask(task: number | null | undefined) {
  if (task) void router.push({ path: route.path, query: { ...route.query, task: String(task) } })
}
</script>

<template>
  <div class="toasts" aria-live="polite" aria-relevant="additions">
    <div v-for="toast in toasts.items" :key="toast.id" class="toast" :class="toast.tone" role="status">
      <div class="content">
        <p class="title">
          <button v-if="toast.task" type="button" class="task" @click="openTask(toast.task)">#{{ toast.task }}</button>
          {{ toast.title }}
        </p>
        <p v-if="toast.detail" class="detail">{{ toast.detail }}</p>
        <code v-if="toast.command" class="command">{{ toast.command }}</code>
      </div>
      <button type="button" class="dismiss" aria-label="Dismiss" @click="toasts.dismiss(toast.id)">
        <X :size="14" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.toasts {
  position: fixed;
  right: var(--space-5);
  bottom: var(--space-5);
  z-index: 50;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(440px, calc(100vw - 32px));
}

.toast {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius);
  border: 1px solid var(--line-strong);
  border-left-width: 4px;
  background: var(--panel);
  box-shadow: var(--shadow-float);
  animation: in 180ms var(--ease);
}

.toast.ok {
  border-left-color: var(--lamp-running);
}

.toast.error {
  border-left-color: var(--danger);
}

.toast.brass {
  border-left-color: var(--brass-strong);
}

.toast.info {
  border-left-color: var(--accent);
}

.content {
  flex: 1;
  min-width: 0;
}

.title {
  margin: 0;
  font-weight: 600;
  font-size: var(--text-sm);
  overflow-wrap: anywhere;
}

.error .title {
  color: var(--danger);
}

.detail {
  margin: 2px 0 0;
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.command {
  display: block;
  margin-top: 6px;
  padding: 4px 6px;
  font-size: 11px;
  background: var(--screen);
  color: var(--screen-ink);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.task {
  border: 0;
  background: var(--panel-2);
  border-radius: var(--radius-s);
  padding: 0 4px;
  font-weight: 750;
  cursor: pointer;
}

.dismiss {
  border: 0;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  align-self: flex-start;
  padding: 2px;
}

@keyframes in {
  from {
    transform: translateY(8px);
    opacity: 0;
  }
}
</style>
