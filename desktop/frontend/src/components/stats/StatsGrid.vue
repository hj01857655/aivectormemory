<script lang="ts" setup>
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  memories?: { project?: number; user?: number }
  issues?: { pending?: number; in_progress?: number; completed?: number; archived?: number }
}>()

const emit = defineEmits<{
  (e: 'card-click', type: 'memories' | 'issues', scope?: string, status?: string): void
}>()

interface Card {
  label: string
  num: number
  cls: string
  type: 'memories' | 'issues'
  scope?: string
  status?: string
}

function getCards(): Card[] {
  const mem = props.memories || {}
  const iss = props.issues || {}
  return [
    { label: t('projectMemories'), num: mem.project || 0, cls: 'blue', type: 'memories', scope: 'project' },
    { label: t('globalMemories'), num: mem.user || 0, cls: 'cyan', type: 'memories', scope: 'user' },
    { label: t('status.pending'), num: iss.pending || 0, cls: 'warning', type: 'issues', status: 'pending' },
    { label: t('status.in_progress'), num: iss.in_progress || 0, cls: 'info', type: 'issues', status: 'in_progress' },
    { label: t('status.completed'), num: iss.completed || 0, cls: 'success', type: 'issues', status: 'completed' },
    { label: t('status.archived'), num: iss.archived || 0, cls: 'muted', type: 'issues', status: 'archived' },
  ]
}

function onCardClick(card: Card) {
  emit('card-click', card.type, card.scope, card.status)
}
</script>

<template>
  <div class="stats-grid">
    <div
      v-for="card in getCards()"
      :key="card.label"
      :class="['mini-card', `mini-card--${card.cls}`]"
      @click="onCardClick(card)"
    >
      <div class="mini-card__label">{{ card.label }}</div>
      <div class="mini-card__number">{{ card.num }}</div>
    </div>
  </div>
</template>

<style scoped>
.stats-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; }
.mini-card {
  background: var(--bg-surface); border-radius: var(--radius-lg); padding: 20px;
  border: 1px solid var(--border); transition: all 0.2s ease; cursor: pointer; text-align: center;
}
.mini-card:hover { border-color: var(--border-hover); box-shadow: var(--shadow-card-hover); }
.mini-card__label {
  font-family: var(--font-mono); font-size: var(--font-size-xs); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 12px;
}
.mini-card__number { font-family: var(--font-mono); font-size: var(--font-size-2xl); font-weight: 700; line-height: 1; }
.mini-card--blue .mini-card__number { color: var(--accent); }
.mini-card--cyan .mini-card__number { color: var(--color-cyan); }
.mini-card--warning .mini-card__number { color: var(--color-warning); }
.mini-card--info .mini-card__number { color: var(--color-info); }
.mini-card--success .mini-card__number { color: var(--color-success); }
.mini-card--muted .mini-card__number { color: var(--text-muted); }

@media (max-width: 900px) {
  .stats-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
