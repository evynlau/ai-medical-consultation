<template>
  <view class="chat-page">
    <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />

    <!-- 顶栏 -->
    <view class="chat-header">
      <view class="header-left" @click="back">
        <text class="back-icon">‹</text>
      </view>
      <view class="header-title">
        <view class="title-text">{{ title }}</view>
        <view v-if="consultation" class="title-meta">
          <text v-if="consultation.urgency_level" class="tag" :class="`urgency-${consultation.urgency_level}`">
            紧急度 {{ urgencyLabel }}
          </text>
        </view>
      </view>
      <view class="header-right" @click="showStart = true">
        <text class="header-action">＋</text>
      </view>
    </view>

    <!-- 消息区 -->
    <scroll-view
      :scroll-y="true"
      :scroll-into-view="scrollToView"
      class="messages"
      :style="{ height: messagesHeight + 'px' }"
    >
      <view v-if="!messages.length" class="empty">
        <view class="empty-icon">✚</view>
        <view class="empty-title">还没有问诊</view>
        <view class="empty-desc">点击右上角 + 开始,或从症状胶囊开始</view>
      </view>

      <view
        v-for="(m, idx) in messages"
        :key="m.id || idx"
        :id="`msg-${idx}`"
        class="msg"
        :class="m.role === 'user' ? 'msg-user' : 'msg-ai'"
      >
        <view class="bubble">{{ m.content }}</view>
        <view class="time">{{ formatTime(m.created_at) }}</view>
      </view>

      <view v-if="loading" class="msg msg-ai" :id="`msg-${messages.length}`">
        <view class="bubble">
          <text class="loading-dot">●</text>
          <text class="loading-dot">●</text>
          <text class="loading-dot">●</text>
        </view>
      </view>
    </scroll-view>

    <!-- 输入区 -->
    <view class="input-bar safe-bottom">
      <textarea
        v-model="inputText"
        class="input"
        placeholder="描述症状…"
        auto-height
        :maxlength="500"
        :disabled="loading"
        @confirm="handleSend"
      />
      <view
        class="send-btn"
        :class="{ 'send-disabled': !inputText.trim() || loading }"
        @click="handleSend"
      >发送</view>
    </view>

    <!-- 开始问诊弹层 -->
    <view v-if="showStart" class="modal-mask" @click.self="showStart = false">
      <view class="modal">
        <view class="modal-title">开始新问诊</view>
        <textarea
          v-model="startForm.complaint"
          class="textarea"
          placeholder="请用一两句话描述您的主要不适,例如:头痛 3 天,伴有低烧"
          :maxlength="500"
          :auto-height="true"
        />
        <view class="examples">
          <text v-for="ex in examples" :key="ex" class="example-tag" @click="startForm.complaint = ex">{{ ex }}</text>
        </view>
        <view class="modal-actions">
          <view class="btn btn-secondary" @click="showStart = false">取消</view>
          <view class="btn" :class="{ 'btn-disabled': !startForm.complaint.trim() }" @click="handleStart">开始</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { api, getToken } from '@/api/index.js'

const statusBarHeight = ref(20)
const messagesHeight = ref(400)
try {
  const sys = uni.getSystemInfoSync()
  statusBarHeight.value = sys.statusBarHeight || 20
  messagesHeight.value = sys.windowHeight - 60 - 80 - sys.statusBarHeight
} catch {}

const messages = ref([])
const consultation = ref(null)
const inputText = ref('')
const loading = ref(false)
const showStart = ref(false)
const scrollToView = ref('')

const startForm = ref({ complaint: '' })
const examples = [
  '头痛 3 天,伴有低烧 37.8°C',
  '最近 1 周咳嗽,有黄痰',
  '胃痛,饭后加重,反酸',
  '血压偏高 150/95,偶尔头晕',
  '皮肤出现红色疹子,瘙痒',
]

const title = computed(() => consultation.value?.chief_complaint
  ? (consultation.value.chief_complaint.length > 20
      ? consultation.value.chief_complaint.slice(0, 20) + '...'
      : consultation.value.chief_complaint)
  : '智能问诊')

const urgencyLabel = computed(() => {
  const map = ['', '无需就医', '择期就医', '尽快就医', '立即急诊']
  return map[consultation.value?.urgency_level || 1] || ''
})

const back = () => uni.switchTab({ url: '/pages/home/home' })

const formatTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

const scrollToBottom = async () => {
  await nextTick()
  setTimeout(() => {
    scrollToView.value = `msg-${messages.value.length - 1}`
  }, 50)
}

const loadCurrent = async () => {
  // 简易版:不持久化当前问诊到本地,每次进首页都开新会话
  // 完整版会调 api.listConsultations 拉最近一次 active
}

const handleStart = async () => {
  if (!startForm.value.complaint.trim()) return
  showStart.value = false
  loading.value = true
  try {
    const data = await api.startConsultation({ chief_complaint: startForm.value.complaint.trim() })
    consultation.value = data
    messages.value = []
    startForm.value.complaint = ''
  } catch (e) {
    // toast already shown
  } finally {
    loading.value = false
  }
}

const handleSend = async () => {
  const text = inputText.value.trim()
  if (!text || !consultation.value || loading.value) return
  // 立刻显示用户消息
  messages.value.push({
    id: Date.now(),
    role: 'user',
    content: text,
    created_at: new Date().toISOString(),
  })
  inputText.value = ''
  scrollToBottom()
  loading.value = true
  try {
    const reply = await api.sendMessage(consultation.value.id, { content: text, role: 'user' })
    messages.value.push({
      id: reply.id || Date.now() + 1,
      role: reply.role || 'ai',
      content: reply.content,
      created_at: reply.created_at || new Date().toISOString(),
    })
    // 更新紧急度
    if (reply.urgency_level) {
      consultation.value.urgency_level = reply.urgency_level
    }
  } catch {} finally {
    loading.value = false
    scrollToBottom()
  }
}

onShow(() => {
  // 从首页 quickAsk 来的待问诊主诉
  const pending = uni.getStorageSync('pending_complaint')
  if (pending) {
    uni.removeStorageSync('pending_complaint')
    if (!consultation.value) {
      startForm.value.complaint = pending
      handleStart()
    }
  }
})

onMounted(() => {
  if (!getToken()) {
    uni.showModal({
      title: '需要登录',
      content: '请先登录后使用问诊功能',
      confirmText: '去登录',
      showCancel: false,
      success: () => uni.navigateTo({ url: '/pages/login/login' }),
    })
  }
  loadCurrent()
})
</script>

<style lang="scss" scoped>
.chat-page {
  min-height: 100vh;
  background: #F2F2F7;
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  align-items: center;
  height: 56px;
  padding: 0 16px;
  background: #fff;
  border-bottom: 0.5px solid #E5E5EA;
  .header-left, .header-right {
    width: 40px; height: 40px;
    display: flex; align-items: center; justify-content: center;
  }
  .back-icon { font-size: 32px; color: #1C1C1E; font-weight: 300; }
  .header-action { font-size: 24px; color: #1C1C1E; }
  .header-title { flex: 1; text-align: center; }
  .title-text { font-size: 16px; font-weight: 600; color: #1C1C1E; }
  .title-meta { margin-top: 2px; }
}

.messages {
  flex: 1;
  padding: 12px 16px;
}
.empty {
  text-align: center;
  padding: 80px 0;
  .empty-icon { font-size: 40px; color: #C7C7CC; }
  .empty-title { font-size: 16px; color: #3C3C43; margin-top: 12px; }
  .empty-desc { font-size: 13px; color: #8E8E93; margin-top: 6px; }
}

.msg {
  display: flex;
  flex-direction: column;
  margin-bottom: 16px;
  &.msg-user { align-items: flex-end; }
  &.msg-ai { align-items: flex-start; }
  .bubble {
    max-width: 75%;
    padding: 10px 14px;
    border-radius: 16px;
    font-size: 15px;
    line-height: 1.5;
    word-break: break-word;
  }
  &.msg-user .bubble {
    background: #1C1C1E;
    color: #fff;
  }
  &.msg-ai .bubble {
    background: #fff;
    color: #1C1C1E;
  }
  .time {
    font-size: 11px;
    color: #8E8E93;
    margin-top: 4px;
  }
  .loading-dot {
    font-size: 8px;
    color: #8E8E93;
    margin: 0 2px;
    animation: pulse 1.2s infinite;
  }
  .loading-dot:nth-child(2) { animation-delay: 0.4s; }
  .loading-dot:nth-child(3) { animation-delay: 0.8s; }
}
@keyframes pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}

.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 12px;
  background: #fff;
  border-top: 0.5px solid #E5E5EA;
  .input {
    flex: 1;
    background: #F2F2F7;
    border-radius: 18px;
    padding: 8px 14px;
    font-size: 15px;
    min-height: 36px;
    max-height: 100px;
    box-sizing: border-box;
  }
  .send-btn {
    height: 36px;
    padding: 0 16px;
    background: #1C1C1E;
    color: #fff;
    border-radius: 18px;
    font-size: 14px;
    display: flex; align-items: center; justify-content: center;
    &.send-disabled { background: #E5E5EA; color: #8E8E93; }
  }
}

.modal-mask {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex; align-items: flex-end;
  z-index: 999;
}
.modal {
  width: 100%;
  background: #fff;
  border-radius: 16px 16px 0 0;
  padding: 20px 16px;
  padding-bottom: calc(20px + env(safe-area-inset-bottom));
  .modal-title { font-size: 17px; font-weight: 600; color: #1C1C1E; margin-bottom: 12px; }
  .textarea {
    width: 100%;
    background: #F2F2F7;
    border-radius: 12px;
    padding: 12px;
    font-size: 15px;
    min-height: 100px;
    box-sizing: border-box;
  }
  .examples {
    display: flex; flex-wrap: wrap; gap: 6px;
    margin-top: 10px;
    .example-tag {
      padding: 4px 10px;
      background: #F2F2F7;
      color: #3C3C43;
      border-radius: 12px;
      font-size: 12px;
    }
  }
  .modal-actions {
    display: flex; gap: 12px;
    margin-top: 16px;
    .btn {
      flex: 1; height: 44px;
      border-radius: 12px;
      display: flex; align-items: center; justify-content: center;
      font-size: 16px;
      &.btn-secondary { background: #F2F2F7; color: #1C1C1E; }
      &.btn-disabled { background: #E5E5EA; color: #8E8E93; }
    }
  }
}

.tag {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  &.urgency-1, &.urgency-2 { background: #E3F8E8; color: #1B7F36; }
  &.urgency-3 { background: #FFF1DD; color: #B25E00; }
  &.urgency-4 { background: #FFE5E3; color: #FF3B30; }
}
</style>
