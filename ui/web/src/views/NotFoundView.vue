<script setup lang="ts">
import EmptyState from '@/components/base/EmptyState.vue'
import AppButton from '@/components/base/AppButton.vue'
</script>

<template>
  <div class="page">
    <EmptyState title="There is no page here">
      The link may be out of date.
      <template #actions>
        <RouterLink to="/"><AppButton tone="primary">Go to the board</AppButton></RouterLink>
      </template>
    </EmptyState>
  </div>
</template>
