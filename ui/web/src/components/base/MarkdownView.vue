<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdown } from '@/lib/markdown'

const props = defineProps<{ source: string }>()
const html = computed(() => renderMarkdown(props.source))
</script>

<template>
  <!-- markdown-it runs with raw HTML disabled, so the output only contains generated markup. -->
  <div class="prose" v-html="html" />
</template>
