<script setup lang="ts">
import { nextTick, onMounted, ref, useId, watch } from 'vue'
import { X } from 'lucide-vue-next'

/**
 * An accessible modal built on the native <dialog> element (focus trapping, Escape, top layer).
 * Escape pressed inside a live terminal is left to the terminal so agents can receive it.
 */
const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    width?: string
    description?: string
    variant?: 'dialog' | 'drawer'
    labelledBy?: string
  }>(),
  { width: '560px', variant: 'dialog' },
)
const emit = defineEmits<{ close: [] }>()
const element = ref<HTMLDialogElement>()
const titleId = useId()
let pressedInside = false

function sync(open: boolean) {
  const dialog = element.value
  if (!dialog) return
  if (open && !dialog.open) {
    dialog.showModal()
    focusFirst(dialog)
  } else if (!open && dialog.open) dialog.close()
}

// Forms start in their first field; everything else starts on the dialog itself, so opening
// a drawer does not light up a focus ring on its first link.
function focusFirst(dialog: HTMLDialogElement) {
  const target =
    dialog.querySelector<HTMLElement>('[autofocus]') ??
    dialog.querySelector<HTMLElement>('.body input:not([type=checkbox]):not([disabled]), .body textarea, .body select')
  if (target) target.focus()
  else dialog.focus()
}

watch(
  () => props.open,
  async (open) => {
    await nextTick()
    sync(open)
  },
)
onMounted(() => sync(props.open))

function onCancel(event: Event) {
  event.preventDefault()
  const active = document.activeElement
  if (active && active.closest('.xterm')) return
  emit('close')
}

function onPointerDown(event: PointerEvent) {
  pressedInside = event.target !== element.value
}

function onClick(event: MouseEvent) {
  if (event.target === element.value && !pressedInside) emit('close')
  pressedInside = false
}
</script>

<template>
  <dialog
    ref="element"
    tabindex="-1"
    class="modal"
    :class="variant"
    :style="{ '--width': width }"
    :aria-labelledby="labelledBy ?? titleId"
    @cancel="onCancel"
    @pointerdown="onPointerDown"
    @click="onClick"
  >
    <div v-if="open" class="frame">
      <header class="header">
        <div class="heading">
          <slot name="title">
            <h2 :id="titleId" class="title">{{ title }}</h2>
          </slot>
          <p v-if="description" class="description">{{ description }}</p>
        </div>
        <slot name="header-actions" />
        <button type="button" class="close" aria-label="Close" @click="emit('close')">
          <X :size="18" aria-hidden="true" />
        </button>
      </header>
      <div class="body scroll-y"><slot /></div>
      <footer v-if="$slots.footer" class="footer"><slot name="footer" /></footer>
    </div>
  </dialog>
</template>

<style scoped>
.modal {
  padding: 0;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-l);
  background: var(--panel);
  color: var(--ink);
  width: min(var(--width), calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  box-shadow: var(--shadow-float);
}

.modal:focus {
  outline: none;
}

.modal::backdrop {
  background: var(--scrim);
}

.modal[open] {
  animation: rise 160ms var(--ease);
}

.modal.drawer {
  margin: 0 0 0 auto;
  height: 100vh;
  max-height: 100vh;
  width: var(--width);
  max-width: 100vw;
  border-radius: 0;
  border-width: 0 0 0 1px;
}

.modal.drawer[open] {
  animation: slide 200ms var(--ease);
}

.frame {
  display: flex;
  flex-direction: column;
  max-height: inherit;
  height: 100%;
}

.drawer .frame {
  height: 100vh;
}

.header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5) var(--space-3);
  border-bottom: 1px solid var(--line);
}

.heading {
  flex: 1;
  min-width: 0;
}

.title {
  font-size: var(--text-lg);
}

.description {
  margin: 4px 0 0;
  color: var(--ink-2);
  font-size: var(--text-sm);
}

.close {
  flex: none;
  border: 0;
  background: transparent;
  color: var(--ink-2);
  padding: 4px;
  border-radius: var(--radius);
  cursor: pointer;
}

.close:hover {
  background: var(--panel-2);
  color: var(--ink);
}

.body {
  flex: 1;
  min-height: 0;
  padding: var(--space-5);
}

.drawer .body {
  padding: 0;
}

.footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--line);
  background: var(--panel);
}

@keyframes rise {
  from {
    transform: translateY(8px);
    opacity: 0;
  }
}

@keyframes slide {
  from {
    transform: translateX(32px);
    opacity: 0.4;
  }
}
</style>
