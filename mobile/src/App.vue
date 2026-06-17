<script>
import { api, getToken, setUser, clearAuth } from '@/api/index.js'

export default {
  onLaunch: async () => {
    console.log('[App] onLaunch')
    // 有 token 就拉一次用户信息(过期就清掉)
    if (getToken()) {
      try {
        const profile = await api.fetchProfile()
        setUser(profile)
      } catch {
        clearAuth()
      }
    }
  },
  onShow: () => {
    console.log('[App] onShow')
  },
  onHide: () => {
    console.log('[App] onHide')
  },
}
</script>

<style lang="scss">
@import '@/styles/tokens.scss';

/* 全局 uni-app 组件样式覆盖 */
uni-page {
  background: #F2F2F7;
}
</style>
