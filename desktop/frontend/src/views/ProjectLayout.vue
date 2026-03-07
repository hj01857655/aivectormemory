<script lang="ts" setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '../stores/project'
import Sidebar from '../components/layout/Sidebar.vue'

const projectStore = useProjectStore()
const router = useRouter()

onMounted(() => {
  if (!projectStore.current) router.replace('/')
})
</script>

<template>
  <Sidebar />
  <main class="content">
    <router-view />
  </main>
</template>
