<template>
  <div class="layout">
    <header class="top-nav">
      <div class="top-nav-inner">
        <div class="brand" @click="$router.push('/')">
          <div class="brand-icon">⌘</div>
          <span class="brand-name">Sora 米医</span>
        </div>
        <nav class="nav-links">
          <a
            v-for="link in navLinks"
            :key="link.path"
            :class="{ active: isActive(link.path) }"
            @click="$router.push(link.path)"
          >{{ link.label }}</a>
        </nav>
        <div class="nav-actions">
          <template v-if="userStore.isLogin">
            <el-dropdown>
              <span class="user-chip">
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
            <button class="nav-btn nav-btn-ghost" @click="$router.push('/login')">登录</button>
            <button class="nav-btn nav-btn-primary" @click="$router.push('/login')">免费体验</button>
          </template>
        </div>
      </div>
    </header>

    <main class="main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <footer class="bottom-bar">
      <span>⚠️ 本系统仅供健康参考,不能替代专业医生诊断。如有紧急情况请立即拨打 120。</span>
      <span class="copyright">© 2026 AI 智能问诊系统</span>
    </footer>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/* 顶部菜单 —— 在设计稿 4 项基础上,补全项目已存在的"首页"和"问诊记录"两个入口 */
const navLinks = [
  { path: '/',          label: '首页' },
  { path: '/chat',      label: '智能问诊' },
  { path: '/imaging',   label: '胸片分析' },
  { path: '/ocr',       label: '报告识别' },
  { path: '/doctors',   label: '名医录' },
  { path: '/knowledge', label: '知识库' },
  { path: '/history',   label: '问诊记录' },
]
// 共 7 项;「问诊记录」挪到最末,「知识库」前移,与"知识参考"语义就近

const isActive = (path) => {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(path + '/')
}

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
@use '@/styles/tokens.scss' as t;

.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: t.c('bg-soft');
}

/* ============================================
   顶部导航 —— 对齐设计稿 .top-nav
   毛玻璃半透明白底,深色文字,深色品牌,active/hover 用主色
   ============================================ */
.top-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  height: 64px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid t.c('border');
  display: flex;
  align-items: center;
  padding: 0 t.sp(8);
}

.top-nav-inner {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: t.sp(6);
}

.brand {
  display: flex;
  align-items: center;
  gap: t.sp(2);
  cursor: pointer;
  user-select: none;
}

.brand-icon {
  width: 36px;
  height: 36px;
  border-radius: t.r('md');
  background: linear-gradient(135deg, t.c('primary-500'), t.c('primary-700'));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: 300;
  box-shadow: 0 4px 12px rgba(79, 179, 169, 0.30);
}

.brand-name {
  font-family: t.font("serif");
  font-size: 24px;
  font-weight: 700;
  color: t.c('primary-700');
  letter-spacing: 0.02em;
}

.nav-links {
  display: flex;
  gap: t.sp(6);
  flex: 1;
  justify-content: center;

  a {
    padding: t.sp(2) t.sp(3);
    border-radius: t.r('md');
    font-size: 16px;
    font-weight: 500;
    color: t.c('text-2');
    cursor: pointer;
    user-select: none;
    transition: all t.dur("base") t.ease("out");

    &:hover {
      color: t.c('primary-600');
      background: t.c('primary-50');
    }

    &.active {
      color: t.c('primary-700');
      background: t.c('primary-50');
      font-weight: 600;   /* 比默认 500 再重一档,保留激活态识别 */
    }
  }
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: t.sp(3);
}

.nav-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: t.sp(2) t.sp(4);
  border-radius: t.r('md');
  font-size: 14px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  font-family: inherit;
  transition: all t.dur("base") t.ease("out");
  line-height: 1.2;
}
.nav-btn-ghost {
  background: transparent;
  color: t.c('text-2');
  &:hover { color: t.c('primary-600'); }
}
.nav-btn-primary {
  background: t.c('primary-500');
  color: #fff;
  box-shadow: 0 4px 12px rgba(79, 179, 169, 0.30);
  &:hover {
    background: t.c('primary-600');
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(79, 179, 169, 0.40);
  }
}

/* 已登录用户胶囊(对齐设计稿 .nav-actions 内文字按钮) */
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: t.sp(2) t.sp(3);
  border-radius: t.r('md');
  font-size: 14px;
  color: t.c('text-1');
  cursor: pointer;
  user-select: none;
  transition: all t.dur("base") t.ease("out");

  &:hover {
    color: t.c('primary-600');
    background: t.c('primary-50');
  }
}

/* ============================================
   主区
   ============================================ */
.main {
  flex: 1;
  padding: 0;
  background: t.c('bg-soft');
}

/* ============================================
   底部条
   ============================================ */
.bottom-bar {
  text-align: center;
  color: t.c('text-2');
  font-size: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  padding: t.sp(3) t.sp(4);
  background: t.c('surface');
  border-top: 1px solid t.c('border');
  .copyright { color: t.c('text-3'); }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* 顶部导航响应式:中等屏隐藏部分菜单,小屏只保留核心 */
@media (max-width: 960px) {
  .top-nav { padding: 0 t.sp(4); }
  .nav-links { gap: t.sp(2); }
  .nav-links a { padding: t.sp(2); }
}
@media (max-width: 720px) {
  .brand-name { display: none; }
  .nav-links { display: none; }   // 小屏交给汉堡/侧栏(本期不实现)
  .nav-actions { gap: t.sp(2); }
}
</style>
