/** Run an API call with a pending flag, a success toast, and a readable error. */

import { ref } from 'vue'
import { ApiError } from '@/api/http'
import type { ActionResult } from '@/api/types'
import { useLive } from '@/stores/live'
import { useToasts } from '@/stores/toasts'

/** Incremented after every successful change, so views of data outside the snapshot refresh. */
export const completedActions = ref(0)

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return String(error)
}

export function useRequest() {
  const pending = ref(false)
  const error = ref('')
  const toasts = useToasts()
  const live = useLive()

  async function run<T extends Partial<ActionResult>>(
    call: () => Promise<T>,
    options: { command?: string | null; task?: number | null; quiet?: boolean; toastErrors?: boolean } = {},
  ): Promise<T | null> {
    pending.value = true
    error.value = ''
    try {
      const result = await call()
      completedActions.value += 1
      if (!options.quiet) {
        toasts.push({
          tone: 'ok',
          title: result.message ?? 'Done',
          command: options.command ?? undefined,
          task: options.task ?? null,
        })
      }
      void live.refresh().catch(() => undefined)
      return result
    } catch (caught) {
      error.value = errorMessage(caught)
      if (options.toastErrors) toasts.push({ tone: 'error', title: error.value, task: options.task ?? null })
      return null
    } finally {
      pending.value = false
    }
  }

  return { pending, error, run }
}
