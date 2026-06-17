import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as ElIcons from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import './styles/main.scss'
// 全局设计 Token(含 Element Plus 主题覆盖、薄雾青主题)
import './styles/tokens.scss'

const app = createApp(App)

// 全局注册 Element Plus 图标
for (const [key, comp] of Object.entries(ElIcons)) {
  app.component(key, comp)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

app.mount('#app')
