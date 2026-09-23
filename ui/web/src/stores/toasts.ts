/** Transient confirmations and errors shown in the corner of the screen. */

import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Toast {
  id: number
  tone: 'ok' | 'error' | 'info' | 'brass'
  title: string
  detail?: string
  command?: string
  task?: number | null
}

export const useToasts = defineStore('toasts', () => {
  const items = ref<Toast[]>([])
  let counter = 0

  function push(toast: Omit<Toast, 'id'>, timeout = toast.tone === 'error' ? 9000 : 4500): number {
    counter += 1
    const id = counter
    items.value = [...items.value.slice(-4), { ...toast, id }]
    if (timeout > 0) window.setTimeout(() => dismiss(id), timeout)
    return id
  }

  function dismiss(id: number) {
    items.value = items.value.filter((item) => item.id !== id)
  }

  return { items, push, dismiss }
})
