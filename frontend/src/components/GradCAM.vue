<!-- GradCAM.vue - AI 关注的影像区域叠加显示 -->
<template>
  <div class="gradcam-container">
    <div v-if="!src" class="placeholder">
      <el-icon class="placeholder-icon"><Picture /></el-icon>
      <div class="placeholder-text">AI 关注区域</div>
      <div class="placeholder-hint">上传影像后显示</div>
    </div>
    <img
      v-else
      :src="src"
      class="gradcam-image"
      :style="{ opacity: opacity }"
      alt="Grad-CAM 热力图"
    />
    <div v-if="src" class="legend">
      <span class="legend-label">低关注</span>
      <div class="legend-gradient"></div>
      <span class="legend-label">高关注</span>
    </div>
  </div>
</template>

<script setup>
import { Picture } from '@element-plus/icons-vue'

defineProps({
  src: {
    type: String,
    default: ''
  },
  opacity: {
    type: Number,
    default: 0.5,
    validator: (v) => v >= 0 && v <= 1
  }
})
</script>

<style lang="scss" scoped>
.gradcam-container {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  background: #f5f7fa;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.gradcam-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.placeholder {
  text-align: center;
  color: #909399;
}

.placeholder-icon {
  font-size: 64px;
  color: #c0c4cc;
  margin-bottom: 12px;
}

.placeholder-text {
  font-size: 16px;
  font-weight: 500;
  color: #606266;
  margin-bottom: 4px;
}

.placeholder-hint {
  font-size: 12px;
  color: #909399;
}

.legend {
  position: absolute;
  bottom: 12px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.9);
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
}

.legend-label {
  color: #606266;
  white-space: nowrap;
}

.legend-gradient {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: linear-gradient(
    to right,
    rgb(0, 0, 255),
    rgb(0, 255, 255),
    rgb(0, 255, 0),
    rgb(255, 255, 0),
    rgb(255, 0, 0)
  );
}
</style>