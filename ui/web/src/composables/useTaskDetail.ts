/** Load one task's full detail and refresh it whenever the live snapshot shows it changed. */

import { computed, ref, watch, type Ref } from 'vue'
import { api } from '@/api/http'
import type { TaskDetail } from '@/api/types'
import { errorMessage } from '@/composables/useRequest'
import { useLive } from '@/stores/live'

export function useTaskDetail(number: Ref<number | null>) {
  const live = useLive()
  const detail = ref<TaskDetail | null>(null)
  const loading = ref(false)
  const failure = ref('')
  let timer: number | undefined
  let generation = 0

  const summary = computed(() => (number.value !== null ? live.taskMap.get(number.value) : undefined))

  // Everything that can change what the detail view shows.
  const signature = computed(() => {
    const task = summary.value
    if (!task) return ''
    const derived = task.derived
    return [
      task.updated_at,
      task.status,
      derived.event_count,
      derived.run_count,
      derived.transcripts,
      derived.knowledge_count,
      derived.notifications.pending,
      derived.session?.alive,
      derived.completion_pending,
      derived.active_run?.run_status,
      derived.active_run?.phase,
      JSON.stringify(derived.worktrees),
      live.snapshot?.completions?.processed,
      live.snapshot?.completions?.invalid,
    ].join('|')
  })

  async function load() {
    if (number.value === null) return
    const current = ++generation
    loading.value = !detail.value || detail.value.task.task_number !== number.value
    try {
      const result = await api.get<TaskDetail>(`/tasks/${number.value}`)
      if (current === generation) {
        detail.value = result
        failure.value = ''
      }
    } catch (error) {
      if (current === generation) failure.value = errorMessage(error)
    } finally {
      if (current === generation) loading.value = false
    }
  }

  watch(
    number,
    (value) => {
      detail.value = null
      failure.value = ''
      if (value !== null) void load()
    },
    { immediate: true },
  )

  watch(signature, (value, previous) => {
    if (!value || value === previous || number.value === null) return
    window.clearTimeout(timer)
    timer = window.setTimeout(load, 200)
  })

  return { detail, summary, loading, failure, reload: load }
}
