<script lang="ts" setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  HealthCheck, GetDBStats, RepairMissingEmbeddings, RebuildAllEmbeddings,
  BackupDB, RestoreDB, ListBackups,
} from '../../wailsjs/go/main/App'
import Badge from '../components/common/Badge.vue'
import Modal from '../components/layout/Modal.vue'

const { t } = useI18n()

const dbStats = ref<any>(null)
const health = ref<any>(null)
const backups = ref<any[]>([])
const loading = ref(true)
const repairing = ref(false)
const rebuilding = ref(false)

const confirmRebuildShow = ref(false)
const confirmRestoreShow = ref(false)
const restoreFile = ref('')

onMounted(async () => {
  await loadAll()
})

async function loadAll() {
  loading.value = true
  try {
    const [s, h, b] = await Promise.all([GetDBStats(), HealthCheck(), ListBackups()])
    dbStats.value = s
    health.value = h
    backups.value = b || []
  } catch {}
  loading.value = false
}

async function doRepair() {
  repairing.value = true
  try {
    await RepairMissingEmbeddings()
    window.__toast?.show(t('opSuccess'), 'success')
    await loadAll()
  } catch (e: any) {
    window.__toast?.show(e?.message || 'Failed', 'error')
  }
  repairing.value = false
}

async function doRebuild() {
  confirmRebuildShow.value = false
  rebuilding.value = true
  try {
    await RebuildAllEmbeddings()
    window.__toast?.show(t('opSuccess'), 'success')
    await loadAll()
  } catch (e: any) {
    window.__toast?.show(e?.message || 'Failed', 'error')
  }
  rebuilding.value = false
}

async function doBackup() {
  try {
    await BackupDB()
    window.__toast?.show(t('backupSuccess'), 'success')
    backups.value = await ListBackups() || []
  } catch (e: any) {
    window.__toast?.show(e?.message || 'Failed', 'error')
  }
}

function openRestore(file: string) {
  restoreFile.value = file
  confirmRestoreShow.value = true
}

async function doRestore() {
  confirmRestoreShow.value = false
  try {
    await RestoreDB(restoreFile.value)
    window.__toast?.show(t('restoreSuccess'), 'success')
    await loadAll()
  } catch (e: any) {
    window.__toast?.show(e?.message || 'Failed', 'error')
  }
}

function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++ }
  return `${size.toFixed(i ? 1 : 0)} ${units[i]}`
}
</script>

<template>
  <div class="maintenance-view">
    <div class="page-header">
      <h2 class="page-title">{{ t('maintenance') }}</h2>
    </div>

    <div v-if="loading" class="empty-state">Loading...</div>
    <template v-else>
      <!-- DB Overview -->
      <section class="section">
        <h3 class="section-title">{{ t('dbOverview') }}</h3>
        <div class="info-grid" v-if="dbStats">
          <div class="info-item">
            <span class="info-label">{{ t('fileSize') }}</span>
            <span class="info-value">{{ formatSize(dbStats.file_size) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">{{ t('dbPath') }}</span>
            <span class="info-value mono">{{ dbStats.path }}</span>
          </div>
          <div v-if="dbStats.tables" class="info-item" style="grid-column: 1/-1">
            <span class="info-label">{{ t('tableCounts') }}</span>
            <div class="table-counts">
              <span v-for="(count, name) in dbStats.tables" :key="name" class="table-count-item">
                <span class="table-name">{{ name }}</span>
                <span class="table-num">{{ count }}</span>
              </span>
            </div>
          </div>
          <div v-if="dbStats.embedding_dim" class="info-item">
            <span class="info-label">{{ t('embeddingDim') }}</span>
            <span class="info-value">{{ dbStats.embedding_dim }}</span>
          </div>
        </div>
      </section>

      <!-- Health Check -->
      <section class="section">
        <h3 class="section-title">
          {{ t('healthCheck') }}
          <button class="btn btn--ghost btn--sm" @click="loadAll">{{ t('refresh') }}</button>
        </h3>
        <div v-if="health" class="health-grid">
          <div class="health-item">
            <span>{{ t('memoriesConsistency') }}</span>
            <Badge :type="health.memories_ok ? 'success' : 'warning'">{{ health.memories_ok ? 'OK' : 'Mismatch' }}</Badge>
          </div>
          <div class="health-item">
            <span>{{ t('userMemoriesConsistency') }}</span>
            <Badge :type="health.user_memories_ok ? 'success' : 'warning'">{{ health.user_memories_ok ? 'OK' : 'Mismatch' }}</Badge>
          </div>
          <div class="health-item">
            <span>{{ t('missingEmbeddings') }}</span>
            <Badge :type="(health.missing_embeddings || 0) === 0 ? 'success' : 'warning'">{{ health.missing_embeddings || 0 }}</Badge>
          </div>
          <div class="health-item">
            <span>{{ t('orphanVectors') }}</span>
            <Badge :type="(health.orphan_vectors || 0) === 0 ? 'success' : 'warning'">{{ health.orphan_vectors || 0 }}</Badge>
          </div>
        </div>
        <div class="health-actions">
          <button class="btn btn--outline" :disabled="repairing" @click="doRepair">
            {{ repairing ? '...' : t('repairEmbeddings') }}
          </button>
          <button class="btn btn--outline" :disabled="rebuilding" @click="confirmRebuildShow = true">
            {{ rebuilding ? '...' : t('rebuildEmbeddings') }}
          </button>
        </div>
      </section>

      <!-- Backup Management -->
      <section class="section">
        <h3 class="section-title">
          {{ t('backupManagement') }}
          <button class="btn btn--primary btn--sm" @click="doBackup">{{ t('backupDB') }}</button>
        </h3>
        <div v-if="backups.length === 0" class="empty-state" style="padding: 16px">{{ t('noBackups') }}</div>
        <ul v-else class="backup-list">
          <li v-for="b in backups" :key="b.name || b">
            <span class="backup-name">{{ b.name || b }}</span>
            <span v-if="b.size" class="backup-size">{{ formatSize(b.size) }}</span>
            <button class="btn btn--ghost btn--sm" @click="openRestore(b.name || b)">{{ t('restoreDB') }}</button>
          </li>
        </ul>
      </section>
    </template>

    <!-- Rebuild confirmation -->
    <Modal :show="confirmRebuildShow" :title="t('rebuildEmbeddings')" :confirm-text="t('confirm')" danger @close="confirmRebuildShow = false" @confirm="doRebuild">
      <p>{{ t('confirmRebuild') }}</p>
    </Modal>

    <!-- Restore confirmation -->
    <Modal :show="confirmRestoreShow" :title="t('restoreDB')" :confirm-text="t('confirm')" danger @close="confirmRestoreShow = false" @confirm="doRestore">
      <p>{{ t('confirmRestore') }}</p>
    </Modal>
  </div>
</template>

<style scoped>
.maintenance-view { display: flex; flex-direction: column; flex: 1; }
.section { margin-bottom: 28px; }
.section-title {
  font-family: var(--font-mono); font-size: 14px; font-weight: 600; color: var(--text-heading);
  margin-bottom: 16px; display: flex; align-items: center; gap: 12px;
}

.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-item {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 12px 16px;
}
.info-label { display: block; font-family: var(--font-mono); font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.info-value { font-size: 14px; color: var(--text-primary); }
.info-value.mono { font-family: var(--font-mono); font-size: 12px; word-break: break-all; }

.table-counts { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 4px; }
.table-count-item { display: flex; align-items: center; gap: 6px; }
.table-name { font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); }
.table-num { font-family: var(--font-mono); font-size: 14px; font-weight: 600; color: var(--accent); }

.health-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.health-item {
  display: flex; justify-content: space-between; align-items: center;
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 12px 16px; font-size: 13px; color: var(--text-heading);
}
.health-actions { display: flex; gap: 12px; }

.backup-list { list-style: none; padding: 0; }
.backup-list li {
  display: flex; align-items: center; gap: 12px; padding: 10px 16px;
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius);
  margin-bottom: 8px; font-size: 13px;
}
.backup-name { font-family: var(--font-mono); font-size: 12px; color: var(--text-heading); flex: 1; }
.backup-size { font-family: var(--font-mono); font-size: 12px; color: var(--text-muted); }
</style>
