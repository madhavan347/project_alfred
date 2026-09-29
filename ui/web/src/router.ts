import { createRouter, createWebHistory } from 'vue-router'
import BoardView from '@/views/BoardView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'board', component: BoardView, meta: { title: 'Board' } },
    { path: '/tasks/:number', name: 'task', component: () => import('@/views/TaskPage.vue'), meta: { title: 'Task' } },
    { path: '/sessions', name: 'sessions', component: () => import('@/views/SessionsView.vue'), meta: { title: 'Agent sessions' } },
    { path: '/feed', name: 'feed', component: () => import('@/views/FeedView.vue'), meta: { title: 'Live feed' } },
    { path: '/runs', name: 'runs', component: () => import('@/views/RunsView.vue'), meta: { title: 'Runs' } },
    { path: '/notifications', name: 'notifications', component: () => import('@/views/NotificationsView.vue'), meta: { title: 'Notifications' } },
    { path: '/knowledge', name: 'knowledge', component: () => import('@/views/KnowledgeView.vue'), meta: { title: 'Knowledge' } },
    { path: '/reports', name: 'reports', component: () => import('@/views/ReportsView.vue'), meta: { title: 'Reports' } },
    { path: '/operations', name: 'operations', component: () => import('@/views/OperationsView.vue'), meta: { title: 'Operations' } },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue'), meta: { title: 'Settings' } },
    { path: '/:rest(.*)*', name: 'missing', component: () => import('@/views/NotFoundView.vue'), meta: { title: 'Not found' } },
  ],
  scrollBehavior(to, from) {
    if (to.path !== from.path) return { top: 0 }
    return false
  },
})
