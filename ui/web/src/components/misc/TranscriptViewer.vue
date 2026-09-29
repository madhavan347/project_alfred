<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, query } from '@/api/http'
import type { Transcript } from '@/api/types'
import { absolute, bytes, humanize } from '@/lib/format'
import CopyButton from '@/components/base/CopyButton.vue'

/** Saved session transcripts: pick one and read it, with search. */
const props = defineProps<{ transcripts: Transcript[]; emptyLabel?: string }>()
const chosen = ref<string>('')
const content = ref('')
const failure = ref('')
const filter = ref('')

watch(
  () => props.transcripts,
  (list) => {
    if (!list.some((item) => item.relative === chosen.value)) chosen.value = list[0]?.relative ?? ''
  },
  { immediate: true },
)

watch(
  chosen,
  async (relative) => {
    content.value = ''
    failure.value = ''
    if (!relative) return
    try {
      const result = await api.get<Transcript>(`/transcripts/read${query({ path: relative })}`)
      content.value = result.content ?? ''
    } catch (error) {
      failure.value = error instanceof Error ? error.message : String(error)
    }
  },
  { immediate: true },
)

const lines = computed(() => {
  const all = content.value.split('\n')
  const needle = filter.value.trim().toLowerCase()
  if (!needle) return all
  return all.filter((line) => line.toLowerCase().includes(needle))
})
</script>

<template>
  <div class="viewer">
    <p v-if="!transcripts.length" class="muted small">{{ emptyLabel ?? 'No transcripts yet.' }}</p>
    <template v-else>
      <div class="bar">
        <label class="visually-hidden" for="transcript-choice">Transcript</label>
        <select id="transcript-choice" v-model="chosen" class="choice">
          <option v-for="item in transcripts" :key="item.relative" :value="item.relative">
            {{ absolute(item.captured_at) }} — {{ humanize(item.reason) }} ({{ bytes(item.size) }})
          </option>
        </select>
        <input v-model="filter" class="filter" type="search" placeholder="Filter lines" aria-label="Filter transcript lines" />
        <CopyButton :text="content" label="Copy" />
      </div>
      <p v-if="failure" class="muted small">{{ failure }}</p>
      <pre v-else class="text scroll-y">{{ lines.join('\n') }}</pre>
    </template>
  </div>
</template>

<style scoped>
.viewer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.choice,
.filter {
  height: 30px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius);
  background: var(--panel);
  padding: 0 8px;
  font-size: var(--text-sm);
}

.choice {
  flex: 1;
  min-width: min(240px, 100%);
}

.text {
  margin: 0;
  max-height: 460px;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: var(--screen);
  color: var(--screen-ink);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
