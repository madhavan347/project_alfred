<script setup lang="ts">
import { useDialogs } from '@/stores/dialogs'
import ModalDialog from '@/components/base/ModalDialog.vue'
import AppButton from '@/components/base/AppButton.vue'

const dialogs = useDialogs()
</script>

<template>
  <ModalDialog :open="!!dialogs.confirmation" :title="dialogs.confirmation?.title ?? ''" width="460px" @close="dialogs.settle(false)">
    <p class="message">{{ dialogs.confirmation?.message }}</p>
    <template #footer>
      <AppButton tone="quiet" @click="dialogs.settle(false)">Cancel</AppButton>
      <AppButton :tone="dialogs.confirmation?.tone === 'danger' ? 'danger' : 'primary'" @click="dialogs.settle(true)">
        {{ dialogs.confirmation?.confirm }}
      </AppButton>
    </template>
  </ModalDialog>
</template>

<style scoped>
.message {
  margin: 0;
  white-space: pre-wrap;
}
</style>
