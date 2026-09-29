<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLive } from '@/stores/live'
import ModalDialog from '@/components/base/ModalDialog.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import CopyButton from '@/components/base/CopyButton.vue'
import TerminalView from './TerminalView.vue'
import SendBar from './SendBar.vue'

/** A large terminal for any Alfred session, opened with ?session=NAME. */
const route = useRoute()
const router = useRouter()
const live = useLive()
const mode = ref<'interactive' | 'readonly'>('interactive')

const name = computed(() => (typeof route.query.session === 'string' ? route.query.session : ''))
const session = computed(() => live.sessionMap.get(name.value))

function close() {
  const query = { ...route.query }
  delete query.session
  void router.push({ path: route.path, query })
}
</script>

<template>
  <ModalDialog :open="!!name" :title="name" width="min(1400px, 96vw)" @close="close">
    <template #header-actions>
      <SegmentedControl
        v-model="mode"
        :options="[
          { value: 'interactive', label: 'Interactive' },
          { value: 'readonly', label: 'Watch only' },
        ]"
        label="Terminal mode"
      />
    </template>
    <div class="body">
      <p v-if="!session" class="muted">This session is not running.</p>
      <template v-else>
        <div class="screen"><TerminalView :key="`${name}-${mode}`" :session="name" :mode="mode" autofocus /></div>
        <SendBar :session="name" />
        <p class="attach small">
          <code>tmux attach-session -t {{ name }}</code>
          <CopyButton :text="`tmux attach-session -t ${name}`" label="Copy" />
        </p>
      </template>
    </div>
  </ModalDialog>
</template>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.screen {
  height: min(68vh, 760px);
}

.attach {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  color: var(--ink-2);
}
</style>
