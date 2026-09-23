<script setup lang="ts">
import { computed } from 'vue'
import { FolderOpen, TriangleAlert } from 'lucide-vue-next'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'

/** Explain why workspace data is unavailable and where to fix it. */
const live = useLive()
const problem = computed(() => live.error)
</script>

<template>
  <section v-if="problem" class="problem" :class="problem.kind" role="alert">
    <FolderOpen v-if="problem.kind === 'no_workspace'" :size="22" aria-hidden="true" />
    <TriangleAlert v-else :size="22" aria-hidden="true" />
    <div class="text">
      <h2>
        {{
          problem.kind === 'no_workspace'
            ? 'Open or create an Alfred workspace'
            : problem.kind === 'config'
              ? 'The configuration could not be loaded'
              : 'Alfred state could not be read'
        }}
      </h2>
      <p class="message">{{ problem.message }}</p>
      <p v-if="problem.kind === 'state'" class="muted small">
        Alfred refuses to replace corrupt or wrong-version state. Inspect the file named above and restore it from a
        backup; the UI keeps working once it reads cleanly.
      </p>
    </div>
    <RouterLink v-if="problem.kind !== 'state'" :to="problem.kind === 'config' ? '/settings#configuration' : '/settings#workspace'">
      <AppButton tone="primary">{{ problem.kind === 'config' ? 'Fix the configuration' : 'Open settings' }}</AppButton>
    </RouterLink>
  </section>
</template>

<style scoped>
.problem {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  padding: var(--space-5);
  margin-bottom: var(--space-5);
  border-radius: var(--radius-l);
  border: 1px solid var(--brass-line);
  background: var(--brass-soft);
  color: var(--ink);
}

.problem.config,
.problem.state {
  border-color: color-mix(in srgb, var(--danger) 40%, var(--line));
  background: var(--danger-soft);
}

.text {
  flex: 1;
  min-width: 0;
}

.message {
  margin: 6px 0 0;
  font-family: var(--font-mono);
  font-size: 12.5px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
