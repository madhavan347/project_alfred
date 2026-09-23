<script setup lang="ts">
import { computed } from 'vue'
import {
  Activity,
  Bell,
  BookOpen,
  ChartColumn,
  History,
  Kanban,
  MonitorPlay,
  Settings,
  Wrench,
} from 'lucide-vue-next'
import { useLive } from '@/stores/live'

const live = useLive()
const liveSessions = computed(() => live.sessions.filter((session) => session.kind === 'task').length)

const items = computed(() => [
  { to: '/', label: 'Board', icon: Kanban, badge: null as number | null, tone: '' },
  { to: '/sessions', label: 'Agent sessions', icon: MonitorPlay, badge: liveSessions.value || null, tone: 'live' },
  { to: '/feed', label: 'Live feed', icon: Activity, badge: null, tone: '' },
  { to: '/runs', label: 'Runs', icon: History, badge: null, tone: '' },
  {
    to: '/notifications',
    label: 'Notifications',
    icon: Bell,
    badge: live.pendingNotifications.length || null,
    tone: 'brass',
  },
  { to: '/knowledge', label: 'Knowledge', icon: BookOpen, badge: null, tone: '' },
  { to: '/reports', label: 'Reports', icon: ChartColumn, badge: null, tone: '' },
  { to: '/operations', label: 'Operations', icon: Wrench, badge: null, tone: '' },
  { to: '/settings', label: 'Settings', icon: Settings, badge: null, tone: '' },
])
</script>

<template>
  <nav class="rail" aria-label="Main">
    <RouterLink to="/" class="brand" aria-label="Alfred board">
      <span class="mark" aria-hidden="true"><span class="bulb go" /><span class="bulb call" /></span>
      <span class="word">Alfred</span>
    </RouterLink>
    <ul>
      <li v-for="item in items" :key="item.to">
        <RouterLink :to="item.to" class="link" active-class="" exact-active-class="active">
          <component :is="item.icon" :size="18" aria-hidden="true" />
          <span class="label">{{ item.label }}</span>
          <span v-if="item.badge" class="badge" :class="item.tone">{{ item.badge }}</span>
        </RouterLink>
      </li>
    </ul>
    <p class="versions" v-if="live.snapshot">
      Alfred {{ live.snapshot.versions.alfred }}<br />UI {{ live.snapshot.versions.ui }}
    </p>
  </nav>
</template>

<style scoped>
.rail {
  display: flex;
  flex-direction: column;
  width: var(--rail-width);
  flex: none;
  height: 100vh;
  position: sticky;
  top: 0;
  padding: var(--space-4) var(--space-3);
  border-right: 1px solid var(--line);
  background: var(--panel);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 18px;
  color: var(--ink);
  text-decoration: none;
}

.mark {
  display: inline-flex;
  gap: 3px;
  padding: 5px;
  border-radius: 7px;
  background: var(--accent);
}

.bulb {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.bulb.go {
  background: var(--lamp-running);
}

.bulb.call {
  background: var(--brass-strong);
}

.word {
  font-size: 1.35rem;
  font-weight: 800;
  font-stretch: 125%;
  letter-spacing: -0.02em;
}

ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.link {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius);
  color: var(--ink-2);
  text-decoration: none;
  font-weight: 600;
  font-size: var(--text-sm);
}

.link:hover {
  background: var(--panel-2);
  color: var(--ink);
}

.link.active {
  background: var(--accent-soft);
  color: var(--accent);
}

.label {
  flex: 1;
}

.badge {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--panel-3);
  color: var(--ink);
}

.badge.brass {
  background: var(--brass-strong);
  color: #fff;
}

.badge.live {
  background: color-mix(in srgb, var(--lamp-running) 22%, var(--panel));
  color: var(--ink);
}

.versions {
  margin: auto 8px 0;
  font-size: var(--text-xs);
  color: var(--ink-3);
}

@media (max-width: 900px) {
  .rail {
    width: 64px;
    padding-inline: 8px;
  }

  .word,
  .label,
  .versions {
    display: none;
  }

  .badge {
    position: absolute;
    transform: translate(12px, -10px);
    min-width: 16px;
    height: 16px;
    font-size: 10px;
  }

  .link {
    position: relative;
    justify-content: center;
  }
}
</style>
