<script setup lang="ts">
import { computed, ref } from 'vue'

/** A plain-text editor with line numbers and a highlighted problem line. */
const props = defineProps<{ errorLine?: number | null; label: string; id?: string }>()
const model = defineModel<string>({ required: true })
const area = ref<HTMLTextAreaElement>()
const gutter = ref<HTMLDivElement>()
const lines = computed(() => Math.max(1, model.value.split('\n').length))

function sync() {
  if (gutter.value && area.value) gutter.value.scrollTop = area.value.scrollTop
}

function onKeydown(event: KeyboardEvent) {
  if (event.key !== 'Tab' || event.shiftKey || event.metaKey || event.ctrlKey || event.altKey) return
  event.preventDefault()
  const target = event.currentTarget as HTMLTextAreaElement
  const start = target.selectionStart
  const end = target.selectionEnd
  model.value = `${model.value.slice(0, start)}  ${model.value.slice(end)}`
  requestAnimationFrame(() => target.setSelectionRange(start + 2, start + 2))
}

defineExpose({
  goTo(line: number) {
    const text = model.value.split('\n')
    const offset = text.slice(0, Math.max(0, line - 1)).reduce((sum, item) => sum + item.length + 1, 0)
    area.value?.focus()
    area.value?.setSelectionRange(offset, offset + (text[line - 1]?.length ?? 0))
  },
})
</script>

<template>
  <div class="editor">
    <div ref="gutter" class="gutter" aria-hidden="true">
      <span v-for="line in lines" :key="line" :class="{ error: line === props.errorLine }">{{ line }}</span>
    </div>
    <textarea
      :id="id"
      ref="area"
      v-model="model"
      class="text"
      spellcheck="false"
      autocapitalize="off"
      autocomplete="off"
      wrap="off"
      :aria-label="label"
      @scroll="sync"
      @keydown="onKeydown"
    />
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  height: 540px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  overflow: hidden;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 20px;
}

.gutter {
  flex: none;
  width: 48px;
  padding: 10px 8px 10px 0;
  text-align: right;
  color: var(--ink-3);
  background: var(--panel-2);
  border-right: 1px solid var(--line);
  overflow: hidden;
  user-select: none;
}

.gutter span {
  display: block;
}

.gutter span.error {
  color: #fff;
  background: var(--danger);
  border-radius: 0 3px 3px 0;
}

.text {
  flex: 1;
  border: 0;
  outline: none;
  resize: none;
  padding: 10px 12px;
  background: transparent;
  color: var(--ink);
  font: inherit;
  line-height: inherit;
  white-space: pre;
  overflow: auto;
  tab-size: 2;
}
</style>
