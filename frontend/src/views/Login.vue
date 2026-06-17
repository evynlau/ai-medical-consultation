<template>
  <div class="login-page">
    <el-card class="login-card" shadow="hover">
      <h2 class="title">
        <el-icon :size="32" color="#409EFF"><FirstAidKit /></el-icon>
        Sora 米医
      </h2>
      <p class="subtitle">{{ mode === 'login' ? '登录以使用完整功能' : '注册新账号' }}</p>

      <el-tabs v-model="mode" stretch>
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="3-50 个字符" :prefix-icon="User" />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="example@email.com" :prefix-icon="Message" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" :prefix-icon="Lock" @keydown.enter="handleSubmit" />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" label="年龄" prop="age">
          <el-input-number v-model="form.age" :min="0" :max="150" placeholder="可选" style="width: 100%" />
        </el-form-item>

        <el-form-item v-if="mode === 'register'" label="性别">
          <el-radio-group v-model="form.gender">
            <el-radio value="male">男</el-radio>
            <el-radio value="female">女</el-radio>
            <el-radio value="other">其他</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-button
          type="primary"
          :loading="loading"
          style="width: 100%; margin-top: 8px"
          size="large"
          @click="handleSubmit"
        >
          {{ mode === 'login' ? '登 录' : '注 册' }}
        </el-button>

        <div class="tip">
          <el-text type="info" size="small">
            💡 您也可以
            <el-link type="primary" @click="$router.push('/chat')">匿名体验</el-link>
            ,无需登录即可使用核心问诊功能
          </el-text>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Message, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const formRef = ref(null)
const mode = ref('login')
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  age: null,
  gender: ''
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '3-50 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' }
  ]
}

const handleSubmit = async () => {
  await formRef.value.validate()
  loading.value = true
  try {
    if (mode.value === 'login') {
      await userStore.login({ username: form.username, password: form.password })
      ElMessage.success('登录成功')
    } else {
      await userStore.register({
        username: form.username,
        email: form.email,
        password: form.password,
        age: form.age,
        gender: form.gender
      })
      ElMessage.success('注册成功,已自动登录')
    }
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    // 错误已由 http 拦截器弹窗
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: calc(100vh - 60px - 48px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4ecf7 100%);
  padding: 24px;
}

.login-card {
  width: 100%;
  max-width: 440px;
  border-radius: 12px;
  padding: 24px 8px;
}

.title {
  text-align: center;
  margin: 0 0 8px;
  font-size: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.subtitle {
  text-align: center;
  color: #909399;
  margin: 0 0 24px;
}

.tip {
  text-align: center;
  margin-top: 16px;
}
</style>
