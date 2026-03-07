<script lang="ts" setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useProjectStore } from '../../stores/project'
import { useThemeStore } from '../../stores/theme'
import { LaunchWebDashboard, StopWebDashboard, IsWebDashboardRunning } from '../../../wailsjs/go/main/App'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const projectStore = useProjectStore()
const themeStore = useThemeStore()
const webRunning = ref(false)

onMounted(async () => {
  try { webRunning.value = await IsWebDashboardRunning() } catch {}
})

const projectName = computed(() => {
  const dir = projectStore.current
  return dir ? dir.split('/').filter(Boolean).pop() || dir : ''
})

const navItems = [
  { name: 'stats', icon: 'grid' },
  { name: 'status', key: 'sessionStatus', icon: 'activity' },
  { name: 'issues', key: 'issueTracking', icon: 'alert-circle' },
  { name: 'tasks', key: 'taskManagement', icon: 'check-square' },
  { name: 'project-memories', key: 'projectMemories', icon: 'folder' },
  { name: 'user-memories', key: 'globalMemories', icon: 'user' },
  { name: 'tags', key: 'tagManagement', icon: 'tag' },
  { name: 'maintenance', icon: 'wrench' },
  { name: 'settings', icon: 'settings' },
]

function isActive(name: string) {
  return route.name === name
}

function navigate(name: string) {
  router.push({ name })
}

function goBack() {
  projectStore.setCurrent('')
  router.push('/')
}

function toggleTheme() {
  const next = themeStore.resolvedTheme() === 'dark' ? 'light' : 'dark'
  themeStore.setMode(next)
}

async function toggleWebDashboard() {
  try {
    if (webRunning.value) {
      await StopWebDashboard()
      webRunning.value = false
    } else {
      await LaunchWebDashboard()
      webRunning.value = true
    }
  } catch {}
}
</script>

<template>
  <aside class="sidebar">
    <div class="logo">
      <svg class="logo-icon" viewBox="0 0 32 32">
        <circle class="node" cx="16" cy="6" r="3"/>
        <circle class="node" cx="6" cy="26" r="3"/>
        <circle class="node" cx="26" cy="26" r="3"/>
        <line class="edge" x1="16" y1="6" x2="6" y2="26"/>
        <line class="edge" x1="16" y1="6" x2="26" y2="26"/>
        <line class="edge" x1="6" y1="26" x2="26" y2="26"/>
      </svg>
      <span>AVM</span>
    </div>

    <div class="sidebar-project-info" @click="goBack">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="15 18 9 12 15 6"/></svg>
      <span class="sidebar-project-info__name">{{ projectName }}</span>
    </div>

    <ul class="nav-list">
      <li
        v-for="item in navItems"
        :key="item.name"
        class="nav-item"
        :class="{ active: isActive(item.name) }"
        @click="navigate(item.name)"
      >
        <span class="nav-icon">{{ item.icon === 'grid' ? '▦' : item.icon === 'activity' ? '◈' : item.icon === 'alert-circle' ? '⚠' : item.icon === 'check-square' ? '☑' : item.icon === 'folder' ? '📁' : item.icon === 'user' ? '👤' : item.icon === 'tag' ? '🏷' : item.icon === 'wrench' ? '🔧' : '⚙' }}</span>
        {{ t(item.key || item.name) }}
      </li>
    </ul>

    <div class="sidebar-bottom">
      <button class="sidebar-btn" @click="toggleTheme">
        {{ themeStore.resolvedTheme() === 'dark' ? '☀' : '🌙' }}
      </button>
      <button class="sidebar-btn" :class="{ 'sidebar-btn--active': webRunning }" @click="toggleWebDashboard" :title="t('webDashboard')">
        {{ webRunning ? '🟢' : '🌐' }}
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  background: var(--bg-sidebar);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
}
.logo {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-mono);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
}
.logo-icon { width: 28px; height: 28px; }
.logo-icon .node { fill: var(--accent); }
.logo-icon .edge { stroke: var(--accent); stroke-width: 1.2; opacity: 0.5; }
.nav-list { list-style: none; padding: 12px 0; flex: 1; overflow-y: auto; }
.nav-item {
  padding: 10px 24px;
  cursor: pointer;
  transition: all var(--transition-fast);
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 10px;
  border-left: 3px solid transparent;
}
.nav-icon { width: 18px; flex-shrink: 0; text-align: center; font-size: 14px; }
.nav-item:hover { background: var(--bg-hover); color: var(--text-heading); }
.nav-item.active {
  background: var(--accent-bg-light);
  color: var(--text-primary);
  border-left-color: var(--accent);
  font-weight: 500;
}
.sidebar-project-info {
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all var(--transition-fast);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.sidebar-project-info:hover { background: var(--bg-hover); color: var(--text-heading); }
.sidebar-project-info svg { width: 14px; height: 14px; flex-shrink: 0; }
.sidebar-project-info__name {
  font-family: var(--font-mono);
  font-weight: 500;
  color: var(--text-heading);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sidebar-bottom {
  padding: 12px 24px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 8px;
}
.sidebar-btn {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 6px 12px;
  cursor: pointer;
  font-size: 16px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}
.sidebar-btn:hover { border-color: var(--accent); background: var(--accent-bg-subtle); }
</style>
