<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="header-inner">
        <div class="logo" @click="$router.push('/')">
          <el-icon :size="22" color="#fff"><FirstAidKit /></el-icon>
          <span>AI 智能问诊系统</span>
        </div>
        <el-menu mode="horizontal" :default-active="$route.path" router class="nav">
          <el-menu-item index="/">首页</el-menu-item>
          <el-menu-item index="/chat">在线问诊</el-menu-item>
          <el-menu-item index="/ocr">OCR 识别</el-menu-item>
          <el-menu-item index="/history">问诊记录</el-menu-item>
          <el-menu-item index="/knowledge">知识库</el-menu-item>
        </el-menu>
        <div class="user-area">
          <template v-if="userStore.isLogin">
            <el-dropdown>
              <span class="user-name">
                <el-icon><User /></el-icon>
                {{ userStore.displayName }}
                <el-icon><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="goProfile">个人资料</el-dropdown-item>
                  <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-else>
            <el-button type="primary" size="small" @click="$router.push('/login')">登录/注册</el-button>
          </template>
        </div>
      </div>
    </el-header>

    <el-main class="main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </el-main>

    <el-footer height="48px" class="footer">
      <span>⚠️ 本系统仅供健康参考,不能替代专业医生诊断。如有紧急情况请立即拨打 120。</span>
      <span class="copyright">© 2026 AI 智能问诊系统</span>
    </el-footer>
  </el-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

onMounted(() => {
  if (userStore.token) userStore.fetchProfile()
})

const handleLogout = () => {
  userStore.logout()
  router.push('/')
}

const goProfile = () => {
  router.push('/login')
}
</script>

<style lang="scss" scoped>
.layout { min-height: 100vh; }

.header {
  background: linear-gradient(135deg, #409EFF 0%, #2c7be5 100%);
  padding: 0;
  height: 60px !important;

  .header-inner {
    max-width: 1200px;
    margin: 0 auto;
    height: 100%;
    display: flex;
    align-items: center;
    color: #fff;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 18px;
    font-weight: 600;
    margin-right: 40px;
    cursor: pointer;
  }

  .nav {
    background: transparent !important;
    border-bottom: none !important;
    flex: 1;
    :deep(.el-menu-item) {
      color: rgba(255,255,255,0.85) !important;
      &:hover, &.is-active {
        color: #fff !important;
        background: rgba(255,255,255,0.1) !important;
        border-bottom-color: #fff !important;
      }
    }
  }

  .user-area .user-name {
    color: #fff;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    padding: 0 8px;
  }
}

.main {
  padding: 0;
  background: #f5f7fa;
}

.footer {
  text-align: center;
  color: #909399;
  font-size: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  background: #fff;
  border-top: 1px solid #ebeef5;

  .copyright { color: #c0c4cc; }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
