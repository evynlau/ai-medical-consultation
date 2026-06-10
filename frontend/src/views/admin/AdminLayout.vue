<template>
  <el-container class="admin-layout">
    <el-aside width="200px" class="aside">
      <div class="logo">
        <el-icon :size="20" color="#fff"><FirstAidKit /></el-icon>
        <span>问诊管理后台</span>
      </div>
      <el-menu :default-active="$route.path" router>
        <el-menu-item index="/admin">
          <el-icon><DataAnalysis /></el-icon>
          <span>数据概览</span>
        </el-menu-item>
        <el-menu-item index="/admin/consultations">
          <el-icon><ChatLineSquare /></el-icon>
          <span>问诊管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/emergency">
          <el-icon><WarningFilled /></el-icon>
          <span>紧急看板</span>
          <el-badge v-if="urgentCount > 0" :value="urgentCount" class="menu-badge" />
        </el-menu-item>
        <el-menu-item index="/admin/knowledge">
          <el-icon><Reading /></el-icon>
          <span>知识库</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/imaging">
          <el-icon><Picture /></el-icon>
          <span>影像分析</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-title">{{ $route.meta.title || '管理后台' }}</div>
        <div class="user-area">
          <el-button text @click="$router.push('/')">
            <el-icon><HomeFilled /></el-icon>
            返回前台
          </el-button>
          <el-dropdown>
            <span class="user-name">
              <el-icon><Avatar /></el-icon>
              {{ userStore.displayName }}
              <el-tag v-if="userStore.profile?.is_admin" type="danger" size="small" effect="dark">管理员</el-tag>
              <el-tag v-else-if="userStore.profile?.is_doctor" type="success" size="small" effect="dark">医生</el-tag>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { adminApi } from '@/api/admin'

const router = useRouter()
const userStore = useUserStore()
const urgentCount = ref(0)

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
  ElMessage.success('已退出登录')
}

const loadUrgent = async () => {
  try {
    const list = await adminApi.emergency({ only_active: true, limit: 100 })
    urgentCount.value = list.length
  } catch {}
}

onMounted(() => {
  if (userStore.token && !userStore.profile) userStore.fetchProfile()
  loadUrgent()
})
</script>

<style lang="scss" scoped>
.admin-layout { min-height: 100vh; }

.aside {
  background: linear-gradient(180deg, #2c3e50, #34495e);
  color: #fff;
  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 16px;
    font-size: 16px;
    font-weight: 600;
    border-bottom: 1px solid rgba(255,255,255,0.1);
  }
  :deep(.el-menu) {
    background: transparent;
    border: none;
  }
  :deep(.el-menu-item) {
    color: rgba(255,255,255,0.85);
    &:hover, &.is-active {
      background: rgba(255,255,255,0.1);
      color: #fff;
    }
  }
}

.menu-badge {
  margin-left: auto;
  :deep(.el-badge__content) { background: #f56c6c; }
}

.header {
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  .header-title { font-size: 18px; font-weight: 600; }
  .user-area { display: flex; align-items: center; gap: 16px; }
  .user-name {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    padding: 0 8px;
  }
}

.main { padding: 16px; background: #f5f7fa; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
