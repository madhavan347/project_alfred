<script setup lang="ts">
import { computed } from 'vue'
import { parseDiff } from '@/lib/diff'

const props = defineProps<{ text: string; truncated?: boolean; emptyLabel?: string }>()
const files = computed(() => parseDiff(props.text))
</script>

<template>
  <div class="diff">
    <p v-if="!files.length" class="empty">{{ emptyLabel ?? 'No changes.' }}</p>
    <details v-for="file in files" :key="file.path" class="file" open>
      <summary>
        <span class="path mono">{{ file.path }}</span>
        <span class="counts"><span class="add">+{{ file.additions }}</span> <span class="del">−{{ file.deletions }}</span></span>
      </summary>
      <div class="lines" role="table" :aria-label="`Changes in ${file.path}`">
        <div v-for="(line, index) in file.lines" :key="index" class="line" :class="line.kind" role="row">
          <span class="number" role="cell">{{ line.oldNumber ?? '' }}</span>
          <span class="number" role="cell">{{ line.newNumber ?? '' }}</span>
          <span class="sign" role="cell">{{ line.kind === 'add' ? '+' : line.kind === 'remove' ? '−' : '' }}</span>
          <span class="code" role="cell">{{ line.text }}</span>
        </div>
      </div>
    </details>
    <p v-if="truncated" class="empty">The diff is longer than the UI shows; open the worktree to see the rest.</p>
  </div>
</template>

<style scoped>
.diff {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty {
  margin: 0;
  color: var(--ink-2);
  font-size: var(--text-sm);
}

.file {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--panel);
}

summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  background: var(--panel-2);
  cursor: pointer;
  font-size: var(--text-sm);
}

.path {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 12px;
}

.counts {
  font-family: var(--font-mono);
  font-size: 12px;
}

.add {
  color: var(--ok);
}

.del {
  color: var(--danger);
}

.lines {
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
}

.line {
  display: grid;
  grid-template-columns: 44px 44px 16px 1fr;
  min-width: max-content;
}

.number {
  color: var(--ink-3);
  text-align: right;
  padding-right: 8px;
  user-select: none;
}

.sign {
  user-select: none;
  color: var(--ink-3);
}

.code {
  white-space: pre;
  padding-right: 16px;
}

.line.add {
  background: color-mix(in srgb, var(--ok-soft) 80%, transparent);
}

.line.remove {
  background: color-mix(in srgb, var(--danger-soft) 80%, transparent);
}

.line.hunk,
.line.meta {
  color: var(--ink-2);
  background: var(--panel-2);
}

.line.hunk .code,
.line.meta .code {
  font-style: italic;
}
</style>
