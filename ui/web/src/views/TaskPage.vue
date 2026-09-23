<script setup lang="ts">
import { computed, useId } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import { useTaskDetail } from '@/composables/useTaskDetail'
import TaskPanel from '@/components/task/TaskPanel.vue'

const route = useRoute()
const router = useRouter()
const headingId = useId()
const number = computed(() => {
  const value = Number(route.params.number)
  return Number.isInteger(value) && value > 0 ? value : null
})
const tab = computed(() => String(route.query.tab ?? 'overview'))
const { detail, failure, loading } = useTaskDetail(number)

function setTab(value: string) {
  void router.replace({ query: { ...route.query, tab: value } })
}
</script>

<template>
  <div class="task-page">
    <RouterLink to="/" class="back"><ArrowLeft :size="15" aria-hidden="true" /> Board</RouterLink>
    <p v-if="failure" class="failure" role="alert">{{ failure }}</p>
    <p v-else-if="loading || !detail" class="muted" role="status">Loading task {{ number }}…</p>
    <div v-else class="panel sheet">
      <TaskPanel :detail="detail" :tab="tab" :heading-id="headingId" @tab="setTab" />
    </div>
  </div>
</template>

<style scoped>
.task-page {
  padding: var(--space-4) var(--space-5) var(--space-7);
  max-width: 1320px;
}

.back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: var(--space-3);
  font-weight: 600;
}

.sheet {
  overflow: hidden;
}

.failure {
  color: var(--danger);
}
</style>
