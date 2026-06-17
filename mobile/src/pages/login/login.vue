<template>
  <view class="login-page">
    <view class="brand">
      <view class="brand-icon">✚</view>
      <view class="brand-name">AI 家庭医生</view>
    </view>

    <view class="hero">
      <view class="title">登录</view>
      <view class="subtitle">使用账号与密码登录</view>
    </view>

    <view class="form">
      <view class="form-item">
        <input
          v-model="form.username"
          class="input"
          placeholder="用户名 / 手机号"
          placeholder-class="placeholder"
        />
      </view>
      <view class="form-item">
        <input
          v-model="form.password"
          class="input"
          password
          placeholder="密码"
          placeholder-class="placeholder"
        />
      </view>
    </view>

    <button
      class="btn btn-block"
      :disabled="loading"
      :loading="loading"
      @click="handleLogin"
    >登录</button>

    <view class="alt">
      没有账号?
      <text class="link" @click="goRegister">立即注册</text>
    </view>

    <view class="footer">
      ⚠️ 本系统仅供健康参考,不能替代专业医生诊断
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { api, setToken, setUser } from '@/api/index.js'

const form = ref({ username: '', password: '' })
const loading = ref(false)

const handleLogin = async () => {
  if (!form.value.username.trim() || !form.value.password) {
    uni.showToast({ title: '请输入完整', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const data = await api.login({
      username: form.value.username.trim(),
      password: form.value.password,
    })
    setToken(data.access_token || data.token)
    // 拉一次用户信息
    try {
      const profile = await api.fetchProfile()
      setUser(profile)
    } catch {}
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => uni.reLaunch({ url: '/pages/home/home' }), 600)
  } catch (e) {
    // 错误已由 request 弹 toast
  } finally {
    loading.value = false
  }
}

const goRegister = () => {
  uni.showModal({
    title: '提示',
    content: '注册功能请前往 web 端或联系管理员',
    showCancel: false,
  })
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: #F2F2F7;
  padding: 80px 32px 40px;
  display: flex;
  flex-direction: column;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 60px;
}
.brand-icon {
  width: 44px; height: 44px;
  border-radius: 12px;
  background: #1C1C1E;
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; font-weight: 300;
}
.brand-name {
  font-size: 20px; font-weight: 600;
  color: #1C1C1E;
}

.hero {
  margin-bottom: 40px;
  .title {
    font-size: 36px;
    font-weight: 700;
    color: #1C1C1E;
    line-height: 1.2;
    margin-bottom: 8px;
  }
  .subtitle {
    font-size: 15px;
    color: #8E8E93;
  }
}

.form { margin-bottom: 24px; }
.form-item { margin-bottom: 12px; }
.placeholder { color: #C7C7CC; }

.alt {
  margin-top: 20px;
  text-align: center;
  font-size: 14px;
  color: #8E8E93;
  .link { color: #007AFF; }
}

.footer {
  margin-top: auto;
  text-align: center;
  font-size: 12px;
  color: #8E8E93;
  line-height: 1.6;
}
</style>
