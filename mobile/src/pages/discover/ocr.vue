<template>
  <view class="ocr-page">
    <view class="type-selector">
      <view
        v-for="t in types"
        :key="t.value"
        class="type-btn"
        :class="{ active: imageType === t.value }"
        @click="imageType = t.value"
      >{{ t.label }}</view>
    </view>

    <view v-if="!result" class="upload-area">
      <view class="upload-card" @click="chooseImage">
        <view class="upload-icon">📄</view>
        <view class="upload-text">点击上传报告</view>
        <view class="upload-desc">处方 / 检验报告,最大 10MB</view>
      </view>
      <view v-if="previewUrl" class="preview">
        <image :src="previewUrl" mode="aspectFit" class="preview-img" />
        <view class="preview-row">
          <view class="btn btn-secondary" @click="clear">重新选择</view>
          <view class="btn" :class="{ 'btn-disabled': uploading }" @click="submit">
            {{ uploading ? '识别中…' : '开始识别' }}
          </view>
        </view>
      </view>
    </view>

    <view v-else class="result">
      <view class="result-card">
        <view class="result-row">
          <text class="lbl">置信度</text>
          <text class="val">{{ (result.confidence * 100).toFixed(0) }}%</text>
        </view>
        <view class="result-row">
          <text class="lbl">文档类型</text>
          <text class="val">{{ typeLabel(result.structured_data?.document_type) }}</text>
        </view>
        <view v-if="result.raw_text" class="raw-text">
          <view class="section-title">识别原文</view>
          <view class="raw-content">{{ result.raw_text }}</view>
        </view>
      </view>

      <view class="btn" @click="reset" style="margin-top: 16px">识别新报告</view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '@/api/index.js'

const imageType = ref('auto')
const file = ref(null)
const previewUrl = ref('')
const uploading = ref(false)
const result = ref(null)

const types = [
  { value: 'auto', label: '自动' },
  { value: 'prescription', label: '处方' },
  { value: 'report', label: '报告' },
]
const typeLabel = (t) => ({ prescription: '处方', report: '报告', other: '其他', auto: '自动' }[t] || t)

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

const clear = () => { file.value = null; previewUrl.value = '' }
const submit = async () => {
  if (!file.value) return
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file.value)
    form.append('image_type', imageType.value)
    result.value = await api.ocrUpload(form)
  } finally {
    uploading.value = false
  }
}
const reset = () => { result.value = null; clear() }
</script>

<style lang="scss" scoped>
.ocr-page { min-height: 100vh; background: #F2F2F7; padding: 16px; }
.type-selector {
  display: flex;
  background: #F2F2F7;
  border-radius: 10px;
  padding: 4px;
  margin-bottom: 12px;
}
.type-btn {
  flex: 1;
  text-align: center;
  padding: 8px;
  font-size: 13px;
  color: #3C3C43;
  border-radius: 8px;
  &.active { background: #1C1C1E; color: #fff; }
}

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
.preview-img { width: 100%; height: 320px; background: #fff; border-radius: 14px; }
.preview-row { display: flex; gap: 12px; margin-top: 12px; }
.preview-row .btn { flex: 1; }

.result-card {
  background: #fff;
  border-radius: 14px;
  padding: 16px;
}
.result-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 0.5px solid #E5E5EA;
  &:last-of-type { border-bottom: none; }
  .lbl { font-size: 14px; color: #8E8E93; }
  .val { font-size: 14px; color: #1C1C1E; font-weight: 500; }
}
.raw-text { margin-top: 12px; }
.section-title { font-size: 13px; color: #8E8E93; margin-bottom: 8px; }
.raw-content {
  font-size: 13px;
  color: #1C1C1E;
  background: #F2F2F7;
  padding: 12px;
  border-radius: 8px;
  max-height: 280px;
  overflow-y: auto;
  white-space: pre-wrap;
  line-height: 1.6;
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
