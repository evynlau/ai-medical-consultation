<template>
  <view class="xray-page">
    <view class="tip">
      ⚠️ AI 辅助诊断工具,不替代专业医生诊断
    </view>

    <view v-if="!result" class="upload-area">
      <view class="upload-card" @click="chooseImage">
        <view class="upload-icon">🩻</view>
        <view class="upload-text">点击上传胸片影像</view>
        <view class="upload-desc">支持 JPEG / PNG,不超过 10MB</view>
      </view>
      <view v-if="previewUrl" class="preview">
        <image :src="previewUrl" mode="aspectFit" class="preview-img" />
        <view class="preview-row">
          <view class="btn btn-secondary" @click="clear">重新选择</view>
          <view class="btn" :class="{ 'btn-disabled': analyzing }" @click="analyze">
            {{ analyzing ? '分析中…' : '开始 AI 分析' }}
          </view>
        </view>
      </view>
    </view>

    <view v-else class="result">
      <view class="result-card">
        <view class="diagnosis">
          <view class="diag-icon">{{ result.diagnosis === 'NORMAL' ? '✅' : '⚠️' }}</view>
          <view class="diag-text">
            <view class="diag-label">{{ result.diagnosis_cn || result.diagnosis }}</view>
            <view class="diag-confidence">置信度 {{ (result.confidence * 100).toFixed(1) }}%</view>
          </view>
        </view>
      </view>

      <view class="result-card">
        <view class="section-title">多分类结果</view>
        <view
          v-for="p in result.pathologies"
          :key="p.pathology"
          class="pathology"
          :class="{ positive: p.positive }"
        >
          <view class="row">
            <text class="name">{{ p.label_cn || p.pathology }}</text>
            <text class="tag" :class="p.positive ? 'tag-danger' : 'tag-success'">
              {{ p.positive ? '阳性' : '阴性' }}
            </text>
          </view>
          <view class="bar">
            <view class="bar-fill" :class="p.positive ? 'bar-danger' : 'bar-success'"
              :style="{ width: (p.probability * 100) + '%' }" />
          </view>
        </view>
      </view>

      <view class="btn" @click="reset" style="margin-top: 16px">分析新影像</view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '@/api/index.js'

const file = ref(null)
const previewUrl = ref('')
const analyzing = ref(false)
const result = ref(null)

const chooseImage = () => {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['album', 'camera'],
    success: (res) => {
      file.value = res.tempFiles[0]
      previewUrl.value = res.tempFilePaths[0]
    },
  })
}

const clear = () => {
  file.value = null
  previewUrl.value = ''
}

const analyze = async () => {
  if (!file.value) return
  analyzing.value = true
  try {
    const form = new FormData()
    form.append('file', file.value)
    const data = await api.analyzeXray(form)
    result.value = data
  } finally {
    analyzing.value = false
  }
}

const reset = () => {
  result.value = null
  clear()
}
</script>

<style lang="scss" scoped>
.xray-page { min-height: 100vh; background: #F2F2F7; padding: 16px; }
.tip {
  background: #FFF1DD;
  color: #B25E00;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
  margin-bottom: 12px;
}
.upload-area { }
.upload-card {
  background: #fff;
  border: 1.5px dashed #C7C7CC;
  border-radius: 14px;
  padding: 60px 20px;
  text-align: center;
  .upload-icon { font-size: 48px; }
  .upload-text { font-size: 16px; color: #1C1C1E; font-weight: 500; margin-top: 12px; }
  .upload-desc { font-size: 12px; color: #8E8E93; margin-top: 6px; }
}
.preview { margin-top: 12px; }
.preview-img {
  width: 100%;
  height: 320px;
  background: #fff;
  border-radius: 14px;
}
.preview-row { display: flex; gap: 12px; margin-top: 12px; }
.preview-row .btn { flex: 1; }

.result-card {
  background: #fff;
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 12px;
}
.diagnosis { display: flex; align-items: center; gap: 12px; }
.diag-icon { font-size: 36px; }
.diag-label { font-size: 20px; font-weight: 600; color: #1C1C1E; }
.diag-confidence { font-size: 13px; color: #8E8E93; margin-top: 4px; }

.section-title { font-size: 14px; font-weight: 600; color: #1C1C1E; margin-bottom: 12px; }
.pathology {
  padding: 10px 0;
  border-bottom: 0.5px solid #E5E5EA;
  &:last-child { border-bottom: none; }
  .row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
  .name { font-size: 14px; color: #1C1C1E; }
  .tag { padding: 2px 8px; border-radius: 6px; font-size: 11px; }
  .tag-danger { background: #FFE5E3; color: #FF3B30; }
  .tag-success { background: #E3F8E8; color: #1B7F36; }
  .bar { height: 6px; background: #F2F2F7; border-radius: 3px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
  .bar-danger { background: #FF3B30; }
  .bar-success { background: #34C759; }
  &.positive .name { font-weight: 600; }
}

.btn {
  display: flex; align-items: center; justify-content: center;
  height: 44px; border-radius: 12px;
  background: #1C1C1E; color: #fff;
  font-size: 16px;
  &.btn-secondary { background: #F2F2F7; color: #1C1C1E; }
  &.btn-disabled { background: #E5E5EA; color: #8E8E93; }
}
</style>
