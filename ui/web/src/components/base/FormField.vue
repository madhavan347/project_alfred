<script setup lang="ts">
defineProps<{ label: string; help?: string; error?: string; required?: boolean; forId?: string; inline?: boolean }>()
</script>

<template>
  <div class="field" :class="{ inline }">
    <label v-if="forId" class="label" :for="forId">
      {{ label }}<span v-if="required" class="required" aria-hidden="true"> *</span>
    </label>
    <span v-else class="label">{{ label }}<span v-if="required" class="required" aria-hidden="true"> *</span></span>
    <div class="control"><slot /></div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-else-if="help" class="help">{{ help }}</p>
  </div>
</template>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.field.inline {
  flex-direction: row;
  align-items: center;
  gap: var(--space-3);
}

.label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink);
}

.required {
  color: var(--danger);
}

.help,
.error {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.error {
  color: var(--danger);
}
</style>
