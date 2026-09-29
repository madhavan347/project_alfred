<script setup lang="ts">
/** A status lamp: lit when the thing it represents is live, pulsing only on real activity. */
withDefaults(defineProps<{ color: string; lit?: boolean; pulse?: boolean; size?: number; label?: string }>(), {
  lit: true,
  pulse: false,
  size: 10,
})
</script>

<template>
  <span
    class="lamp"
    :class="{ lit, pulse }"
    :style="{ '--lamp': color, width: `${size}px`, height: `${size}px` }"
    :role="label ? 'img' : undefined"
    :aria-label="label"
    :aria-hidden="label ? undefined : 'true'"
    :title="label"
  />
</template>

<style scoped>
.lamp {
  position: relative;
  display: inline-block;
  flex: none;
  border-radius: 50%;
  background: color-mix(in srgb, var(--lamp) 28%, var(--panel-3));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lamp) 55%, transparent);
}

.lamp.lit {
  background: radial-gradient(circle at 35% 30%, color-mix(in srgb, var(--lamp) 55%, white) 0, var(--lamp) 60%);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--lamp) 70%, black),
    0 0 7px 1px color-mix(in srgb, var(--lamp) 55%, transparent);
}

.lamp.pulse::after {
  content: '';
  position: absolute;
  inset: -4px;
  border-radius: 50%;
  border: 2px solid var(--lamp);
  opacity: 0;
  animation: ring 1.6s var(--ease) infinite;
}

@keyframes ring {
  0% {
    transform: scale(0.6);
    opacity: 0.7;
  }
  100% {
    transform: scale(1.5);
    opacity: 0;
  }
}
</style>
