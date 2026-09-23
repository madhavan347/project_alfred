<script setup lang="ts">
import { computed, useId } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ExternalLink } from 'lucide-vue-next'
import { useTaskDetail } from '@/composables/useTaskDetail'
import ModalDialog from '@/components/base/ModalDialog.vue'
import TaskPanel from './TaskPanel.vue'

/** The task detail drawer, opened from anywhere with ?task=N (and ?tab=...). */
const route = useRoute()
const router = useRouter()
const headingId = useId()

const number = computed(() => {
  const value = Number(route.query.task)
  return Number.isInteger(value) && value > 0 && route.name !== 'task' ? value : null
})
const tab = computed(() => String(route.query.tab ?? 'overview'))
const { detail, failure, loading } = useTaskDetail(number)

function close() {
  const query = { ...route.query }
  delete query.task
  delete query.tab
  void router.push({ path: route.path, query })
}

function setTab(value: string) {
  void router.replace({ path: route.path, query: { ...route.query, tab: value } })
}
</script>

<template>
  <ModalDialog
    :open="number !== null"
    variant="drawer"
    :title="detail ? `Task ${detail.task.task_number}` : `Task ${number ?? ''}`"
    width="var(--drawer-width)"
    :labelled-by="detail ? headingId : undefined"
    @close="close"
  >
    <template #title>
      <p class="crumb">
        Task {{ number }}
        <RouterLink v-if="number !== null" class="full" :to="{ name: 'task', params: { number }, query: { tab } }">
          <ExternalLink :size="13" aria-hidden="true" /> Open as page
        </RouterLink>
      </p>
    </template>
    <p v-if="failure" class="failure" role="alert">{{ failure }}</p>
    <p v-else-if="loading || !detail" class="loading" role="status">Loading task {{ number }}…</p>
    <TaskPanel v-else :detail="detail" :tab="tab" :heading-id="headingId" @tab="setTab" />
  </ModalDialog>
</template>

<style scoped>
.crumb {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  font-size: var(--text-sm);
  color: var(--ink-2);
  font-weight: 600;
}

.full {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.failure,
.loading {
  padding: var(--space-5);
}

.failure {
  color: var(--danger);
}
</style>
