<script setup lang="ts">
import { ref } from 'vue'
import { KeyRound } from 'lucide-vue-next'
import { api, signInRequired } from '@/api/http'
import { errorMessage } from '@/composables/useRequest'
import { useLive } from '@/stores/live'
import AppButton from '@/components/base/AppButton.vue'
import TextInput from '@/components/base/TextInput.vue'

/** Shown when the server wants its access token. */
const token = ref('')
const failure = ref('')
const pending = ref(false)
const live = useLive()
const invalid = new URLSearchParams(window.location.search).get('signin') === 'invalid'

async function signIn() {
  pending.value = true
  failure.value = ''
  try {
    await api.post('/auth/login', { token: token.value.trim() })
    signInRequired.value = false
    live.disconnect()
    live.connect()
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <div class="signin" role="dialog" aria-modal="true" aria-labelledby="signin-title">
    <form class="card panel" @submit.prevent="signIn">
      <KeyRound :size="28" aria-hidden="true" />
      <h1 id="signin-title">Sign in to Alfred</h1>
      <p class="muted">
        This server only accepts browsers that have its access token, because it can type into agent sessions. Open
        the link that <code>alfred-ui</code> printed when it started, or paste the token from it.
      </p>
      <p v-if="invalid" class="failure">The token in that link was not accepted.</p>
      <label class="visually-hidden" for="token">Access token</label>
      <TextInput id="token" v-model="token" mono placeholder="Access token" autofocus />
      <p v-if="failure" class="failure" role="alert">{{ failure }}</p>
      <AppButton type="submit" tone="primary" :loading="pending" :disabled="!token.trim()">Sign in</AppButton>
    </form>
  </div>
</template>

<style scoped>
.signin {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  background: var(--paper);
  padding: var(--space-4);
}

.card {
  width: min(440px, 100%);
  padding: var(--space-6);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.card p {
  margin: 0;
}

.failure {
  color: var(--danger);
}
</style>
