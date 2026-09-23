<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '@/api/http'
import type { TaskDetail } from '@/api/types'
import { humanize } from '@/lib/format'
import { NOTIFICATION_META, eventGroup } from '@/lib/status'
import { useRequest } from '@/composables/useRequest'
import AppButton from '@/components/base/AppButton.vue'
import RelativeTime from '@/components/base/RelativeTime.vue'
import SegmentedControl from '@/components/base/SegmentedControl.vue'
import EventRow from '@/components/misc/EventRow.vue'

/** The task's complete audit trail and its notifications. */
const props = defineProps<{ detail: TaskDetail }>()
const { pending, run } = useRequest()
const order = ref<'newest' | 'oldest'>('newest')
const group = ref('all')

const events = computed(() => {
  const filtered = props.detail.events.filter((event) => group.value === 'all' || eventGroup(event.event_type) === group.value)
  return order.value === 'newest' ? [...filtered].reverse() : filtered
})
const notifications = computed(() => [...props.detail.notifications].reverse())

async function acknowledge() {
  const number = props.detail.task.task_number
  await run(() => api.post('/notifications/ack', { task: number }), { command: `alfred notifications ack --task ${number}` })
}
</script>

<template>
  <div class="activity">
    <section class="panel">
      <header class="panel-header wrap">
        <h3>Events</h3>
        <span class="faint small">{{ detail.events.length }} recorded</span>
        <span class="spacer" />
        <SegmentedControl
          v-model="group"
          :options="[
            { value: 'all', label: 'All' },
            { value: 'run', label: 'Runs' },
            { value: 'agent', label: 'Agent' },
            { value: 'status', label: 'Status' },
            { value: 'review', label: 'Review' },
            { value: 'lifecycle', label: 'Lifecycle' },
            { value: 'other', label: 'Other' },
          ]"
          label="Event type"
        />
        <SegmentedControl
          v-model="order"
          :options="[
            { value: 'newest', label: 'Newest first' },
            { value: 'oldest', label: 'Oldest first' },
          ]"
          label="Order"
        />
      </header>
      <ol class="panel-body timeline">
        <EventRow v-for="event in events" :key="event.index" :event="event" />
        <li v-if="!events.length" class="muted">No events of this kind.</li>
      </ol>
    </section>

    <section class="panel">
      <header class="panel-header">
        <h3>Notifications</h3>
        <span class="spacer" />
        <AppButton
          v-if="notifications.some((item) => !item.acknowledged)"
          size="sm"
          tone="brass"
          :loading="pending"
          @click="acknowledge"
        >
          Acknowledge all
        </AppButton>
      </header>
      <ul class="panel-body notes">
        <li v-if="!notifications.length" class="muted">None for this task.</li>
        <li v-for="item in notifications" :key="item.notification_id" :class="{ done: item.acknowledged }">
          <p class="line">
            <strong>{{ NOTIFICATION_META[item.notification_type]?.label ?? humanize(item.notification_type) }}</strong>
            <RelativeTime class="faint small" :value="item.created_at" />
            <span v-if="item.acknowledged" class="faint small">acknowledged <RelativeTime :value="item.acknowledged_at" /></span>
          </p>
          <p v-if="item.details.summary || item.details.message" class="small">{{ item.details.summary || item.details.message }}</p>
          <p class="faint small">
            <template v-if="item.details.agent">Agent {{ item.details.agent }}. </template>
            <template v-if="item.details.repositories?.length">Repositories {{ item.details.repositories.join(', ') }}. </template>
            <template v-if="item.details.session_name">Session {{ item.details.session_name }}.</template>
          </p>
          <ul v-if="item.details.validation_issues?.length" class="issues">
            <li v-for="issue in item.details.validation_issues" :key="issue">{{ issue }}</li>
          </ul>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.activity {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5) var(--space-6);
}

.wrap {
  flex-wrap: wrap;
}

.timeline {
  list-style: none;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.notes {
  list-style: none;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notes li.done {
  opacity: 0.65;
}

.notes p {
  margin: 0;
}

.line {
  display: flex;
  gap: 8px;
  align-items: baseline;
  flex-wrap: wrap;
}

.issues {
  margin: 4px 0 0;
  padding-left: 1.2em;
  color: var(--danger);
  font-size: var(--text-sm);
}
</style>
