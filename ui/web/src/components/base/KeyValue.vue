<script setup lang="ts">
defineProps<{ items: { label: string; value?: string | number | null; mono?: boolean; key?: string }[] }>()
</script>

<template>
  <dl class="kv">
    <template v-for="item in items" :key="item.key ?? item.label">
      <dt>{{ item.label }}</dt>
      <dd :class="{ mono: item.mono }">
        <slot :name="item.key ?? item.label" :item="item">{{ item.value === '' || item.value === null || item.value === undefined ? '—' : item.value }}</slot>
      </dd>
    </template>
  </dl>
</template>

<style scoped>
.kv {
  display: grid;
  grid-template-columns: minmax(120px, max-content) 1fr;
  gap: 6px var(--space-4);
  margin: 0;
  font-size: var(--text-sm);
}

dt {
  color: var(--ink-2);
}

dd {
  margin: 0;
  min-width: 0;
  overflow-wrap: anywhere;
}

dd.mono {
  font-family: var(--font-mono);
  font-size: 12px;
}
</style>
