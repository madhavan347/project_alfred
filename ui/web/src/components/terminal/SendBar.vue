<script setup lang="ts">
import { ref } from 'vue'
import { CornerDownLeft, Send } from 'lucide-vue-next'
import { api } from '@/api/http'
import { useRequest } from '@/composables/useRequest'
import { usePrefs } from '@/stores/prefs'
import AppButton from '@/components/base/AppButton.vue'

/** Paste a message into an agent session or press common keys, such as answering a dialog. */
const props = defineProps<{ session: string; compact?: boolean }>()
const text = ref('')
const prefs = usePrefs()
const { pending, error, run } = useRequest()

const KEYS: { label: string; keys: string[]; title: string }[] = [
  { label: 'Enter', keys: ['Enter'], title: 'Press Enter' },
  { label: 'Esc', keys: ['Escape'], title: 'Press Escape (interrupts many agent CLIs)' },
  { label: 'Ctrl-C', keys: ['C-c'], title: 'Send Ctrl-C' },
  { label: '↑', keys: ['Up'], title: 'Arrow up' },
  { label: '↓', keys: ['Down'], title: 'Arrow down' },
  { label: 'y', keys: ['y'], title: 'Type y' },
  { label: 'n', keys: ['n'], title: 'Type n' },
  { label: '1', keys: ['1'], title: 'Type 1' },
  { label: '2', keys: ['2'], title: 'Type 2' },
  { label: '⇧Tab', keys: ['BTab'], title: 'Shift-Tab (cycles modes in some agent CLIs)' },
]

async function sendMessage() {
  const message = text.value
  if (!message.trim()) return
  const result = await run(
    () =>
      api.post(`/sessions/${encodeURIComponent(props.session)}/send`, {
        text: message,
        submit: true,
        actor: prefs.values.actor,
      }),
    { quiet: true, toastErrors: true },
  )
  if (result) text.value = ''
}

async function press(keys: string[]) {
  await run(() => api.post(`/sessions/${encodeURIComponent(props.session)}/keys`, { keys }), {
    quiet: true,
    toastErrors: true,
  })
}
</script>

<template>
  <div class="send" :class="{ compact }">
    <form class="message" @submit.prevent="sendMessage">
      <label class="visually-hidden" :for="`message-${session}`">Message to the agent</label>
      <input
        :id="`message-${session}`"
        v-model="text"
        class="input"
        type="text"
        placeholder="Message the agent (pasted into its session, then Enter)"
        autocomplete="off"
      />
      <AppButton type="submit" tone="primary" size="sm" :icon="Send" :loading="pending" :disabled="!text.trim()">
        Send
      </AppButton>
    </form>
    <div class="keys" role="group" aria-label="Quick keys">
      <CornerDownLeft v-if="!compact" :size="14" class="faint" aria-hidden="true" />
      <button v-for="key in KEYS" :key="key.label" type="button" class="key" :title="key.title" @click="press(key.keys)">
        {{ key.label }}
      </button>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.send {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message {
  display: flex;
  gap: 8px;
}

.input {
  flex: 1;
  min-width: 0;
  height: 30px;
  padding: 0 10px;
  border-radius: var(--radius);
  border: 1px solid var(--line-strong);
  background: var(--panel);
  font-size: var(--text-sm);
}

.keys {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.key {
  min-width: 30px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--line-strong);
  border-bottom-width: 2px;
  border-radius: var(--radius-s);
  background: var(--panel);
  font-family: var(--font-mono);
  font-size: 12px;
  cursor: pointer;
}

.key:hover {
  background: var(--panel-2);
}

.error {
  margin: 0;
  color: var(--danger);
  font-size: var(--text-xs);
}
</style>
