<script setup lang="ts">
import { computed } from 'vue'
import { absolute, parseTime, relative } from '@/lib/format'

const props = defineProps<{ value: string | number | null | undefined }>()
const iso = computed(() => {
  const time = parseTime(props.value)
  return time === null ? undefined : new Date(time).toISOString()
})
</script>

<template>
  <time :datetime="iso" :title="absolute(value)">{{ relative(value) }}</time>
</template>
