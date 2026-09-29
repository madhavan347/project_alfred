<script setup lang="ts">
defineProps<{ label: string; id?: string; help?: string }>()
const model = defineModel<boolean>({ default: false })
</script>

<template>
  <label class="toggle">
    <input :id="id" v-model="model" type="checkbox" role="switch" :aria-checked="model" />
    <span class="track" aria-hidden="true"><span class="thumb" /></span>
    <span class="text">
      <span class="label">{{ label }}</span>
      <span v-if="help" class="help">{{ help }}</span>
    </span>
  </label>
</template>

<style scoped>
.toggle {
  display: inline-flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
}

input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
}

.track {
  flex: none;
  width: 32px;
  height: 18px;
  margin-top: 1px;
  border-radius: 999px;
  background: var(--panel-3);
  border: 1px solid var(--line-strong);
  position: relative;
  transition: background 120ms var(--ease);
}

.thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--panel);
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.3);
  transition: transform 120ms var(--ease);
}

input:checked + .track {
  background: var(--accent);
  border-color: var(--accent);
}

input:checked + .track .thumb {
  transform: translateX(14px);
}

input:focus-visible + .track {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}

.text {
  display: flex;
  flex-direction: column;
}

.label {
  font-size: var(--text-sm);
  font-weight: 600;
}

.help {
  font-size: var(--text-xs);
  color: var(--ink-2);
}
</style>
