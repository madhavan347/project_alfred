/** Which dialog is open, and with what task or session. */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Values } from '@/lib/actions'

export interface ActionDialogState {
  id: string
  taskNumber: number | null
  overrides: Values
}

export interface ConfirmState {
  title: string
  message: string
  confirm: string
  tone: 'primary' | 'danger'
  resolve: (value: boolean) => void
}

export const useDialogs = defineStore('dialogs', () => {
  const action = ref<ActionDialogState | null>(null)
  const taskForm = ref<{ mode: 'create' | 'edit'; taskNumber: number | null } | null>(null)
  const trigger = ref<{ tasks: number[] } | null>(null)
  const message = ref<{ session: string; taskNumber: number | null } | null>(null)
  const confirmation = ref<ConfirmState | null>(null)
  const palette = ref(false)

  function openAction(id: string, taskNumber: number | null, overrides: Values = {}) {
    action.value = { id, taskNumber, overrides }
  }

  function openTaskForm(mode: 'create' | 'edit', taskNumber: number | null = null) {
    taskForm.value = { mode, taskNumber }
  }

  function openTrigger(tasks: number[] = []) {
    trigger.value = { tasks }
  }

  function openMessage(session: string, taskNumber: number | null) {
    message.value = { session, taskNumber }
  }

  function confirm(options: Omit<ConfirmState, 'resolve' | 'tone'> & { tone?: ConfirmState['tone'] }): Promise<boolean> {
    return new Promise((resolve) => {
      confirmation.value = { tone: 'primary', ...options, resolve }
    })
  }

  function settle(value: boolean) {
    confirmation.value?.resolve(value)
    confirmation.value = null
  }

  return {
    action,
    taskForm,
    trigger,
    message,
    confirmation,
    palette,
    openAction,
    openTaskForm,
    openTrigger,
    openMessage,
    confirm,
    settle,
  }
})
