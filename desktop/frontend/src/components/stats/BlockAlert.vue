<script lang="ts" setup>
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

const { t } = useI18n()
const router = useRouter()

const props = defineProps<{
  isBlocked: boolean
  blockReason?: string
  currentTask?: string
}>()

function goToStatus() {
  router.push('/project/status')
}
</script>

<template>
  <div :class="['block-alert', !isBlocked && 'block-alert--ok']" @click="goToStatus" style="cursor: pointer">
    <div class="block-alert__header">
      <span class="block-alert__dot" />
      <span class="block-alert__title">{{ isBlocked ? t('blocked') : t('normalStatus') }}</span>
    </div>
    <div v-if="isBlocked && blockReason" class="block-alert__reason">{{ blockReason }}</div>
    <div v-if="currentTask" class="block-alert__task">
      <span class="block-alert__label">{{ t('currentTask') }}</span>{{ currentTask }}
    </div>
  </div>
</template>

<style scoped>
.block-alert {
  background: var(--bg-surface); border: 1px solid var(--color-error); border-radius: var(--radius-lg);
  padding: 20px 24px; margin-bottom: 16px; transition: border-color 0.2s ease;
}
.block-alert__header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.block-alert__dot {
  width: 10px; height: 10px; border-radius: 50%; background: var(--color-error);
  flex-shrink: 0; animation: pulse 2s infinite;
}
.block-alert__title {
  font-family: var(--font-mono); font-size: 12px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.5px; color: var(--color-error);
}
.block-alert__reason { font-size: 15px; color: var(--text-primary); line-height: 1.5; }
.block-alert__task { font-size: 13px; color: var(--text-secondary); margin-top: 8px; }
.block-alert__label { font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--text-muted); margin-right: 8px; }

.block-alert--ok { border-color: var(--color-success-dot); }
.block-alert--ok .block-alert__dot { background: var(--color-success-dot); animation: none; }
.block-alert--ok .block-alert__title { color: var(--color-success); }
.block-alert:hover { box-shadow: var(--shadow-card); }
</style>
