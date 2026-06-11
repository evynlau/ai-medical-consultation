<!-- ImageViewer.vue - 通用图片查看器:支持缩放、拖动、原始大小查看 -->
<template>
  <div class="image-viewer">
    <!-- 工具栏 -->
    <div class="viewer-toolbar" v-if="src">
      <el-button-group size="small">
        <el-button @click="zoomIn" :icon="ZoomIn">放大</el-button>
        <el-button @click="zoomOut" :icon="ZoomOut">缩小</el-button>
        <el-button @click="resetZoom">还原</el-button>
        <el-button @click="rotate" :icon="RefreshRight">旋转</el-button>
      </el-button-group>
      <el-slider
        v-model="zoomPercent"
        :min="20"
        :max="500"
        :step="10"
        show-input
        :show-input-controls="false"
        class="zoom-slider"
        @input="onSliderChange"
      />
    </div>

    <!-- 图片容器 -->
    <div
      ref="containerRef"
      class="image-container"
      :class="{ draggable: zoom > 1 }"
      @wheel.prevent="onWheel"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
      @dblclick.stop="openFullscreen"
    >
      <div
        v-if="src"
        class="image-wrapper"
        :style="imageStyle"
      >
        <img
          ref="imgRef"
          :src="src"
          :alt="alt"
          class="viewer-image"
          @load="onImageLoad"
          @dragstart.prevent
        />
        <!-- 热力图叠加层(可选) -->
        <img
          v-if="overlaySrc"
          :src="overlaySrc"
          class="overlay-image"
          :style="{ opacity: overlayOpacity }"
          alt="热力图叠加"
        />
      </div>
      <div v-else class="placeholder">
        <el-icon class="placeholder-icon"><Picture /></el-icon>
        <div class="placeholder-text">{{ placeholderText }}</div>
      </div>
    </div>

    <!-- 底部信息 -->
    <div class="viewer-info" v-if="src">
      <span>{{ zoomPercent }}%</span>
      <span v-if="imageSize">{{ imageSize }}</span>
      <span class="hint">滚轮缩放 / 拖动平移 / 双击放大</span>
    </div>

    <!-- 双击放大对话框 -->
    <el-dialog
      v-model="showFullscreen"
      :title="alt || '影像查看'"
      width="95%"
      top="2vh"
      :show-close="true"
      destroy-on-close
      class="image-zoom-dialog"
    >
      <div class="fullscreen-toolbar">
        <el-button-group size="default">
          <el-button @click="zoomIn" :icon="ZoomIn">放大</el-button>
          <el-button @click="zoomOut" :icon="ZoomOut">缩小</el-button>
          <el-button @click="resetZoom">还原</el-button>
          <el-button @click="rotate" :icon="RefreshRight">旋转</el-button>
        </el-button-group>
        <el-slider
          v-model="zoomPercent"
          :min="20"
          :max="800"
          :step="10"
          show-input
          :show-input-controls="false"
          class="zoom-slider-large"
          @input="onSliderChange"
        />
        <span class="fullscreen-hint">ESC 或点击关闭退出</span>
      </div>

      <div
        ref="fsContainerRef"
        class="fullscreen-image-container"
        :class="{ draggable: zoom > 1 }"
        @wheel.prevent="onWheel"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @mouseleave="onMouseUp"
      >
        <div class="image-wrapper" :style="imageStyle">
          <img
            ref="fsImgRef"
            :src="src"
            :alt="alt"
            class="viewer-image-fullscreen"
            @dragstart.prevent
          />
          <img
            v-if="overlaySrc"
            :src="overlaySrc"
            class="overlay-image"
            :style="{ opacity: overlayOpacity }"
            alt="热力图叠加"
          />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted, onMounted, onBeforeUnmount } from 'vue'
import { ZoomIn, ZoomOut, RefreshRight, Picture } from '@element-plus/icons-vue'

const props = defineProps({
  src: { type: String, default: '' },
  overlaySrc: { type: String, default: '' },  // 热力图叠加
  overlayOpacity: { type: Number, default: 0.5 },
  alt: { type: String, default: '影像' },
  placeholderText: { type: String, default: '请上传影像' },
})

const containerRef = ref(null)
const imgRef = ref(null)
const zoom = ref(1)
const zoomPercent = ref(100)
const rotation = ref(0)
const position = ref({ x: 0, y: 0 })
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0, posX: 0, posY: 0 })
const naturalSize = ref({ w: 0, h: 0 })

// 双击放大对话框
const showFullscreen = ref(false)
const openFullscreen = () => {
  if (!props.src) return
  // 进入全屏时保留当前缩放,但重置拖动位置
  showFullscreen.value = true
  position.value = { x: 0, y: 0 }
}

const imageStyle = computed(() => ({
  transform: `translate(${position.value.x}px, ${position.value.y}px) scale(${zoom.value}) rotate(${rotation.value}deg)`,
  cursor: isDragging.value ? 'grabbing' : (zoom.value > 1 ? 'grab' : 'default'),
}))

const imageSize = computed(() => {
  if (!naturalSize.value.w) return ''
  return `${naturalSize.value.w} × ${naturalSize.value.h}`
})

const onImageLoad = () => {
  if (imgRef.value) {
    naturalSize.value = {
      w: imgRef.value.naturalWidth,
      h: imgRef.value.naturalHeight,
    }
  }
}

const zoomIn = () => {
  const newZoom = Math.min(zoom.value * 1.25, 5)
  updateZoom(newZoom)
}

const zoomOut = () => {
  const newZoom = Math.max(zoom.value / 1.25, 0.2)
  updateZoom(newZoom)
}

const updateZoom = (newZoom) => {
  zoom.value = newZoom
  zoomPercent.value = Math.round(newZoom * 100)
  if (newZoom <= 1) {
    position.value = { x: 0, y: 0 }
  }
}

const onSliderChange = (val) => {
  const newZoom = val / 100
  updateZoom(newZoom)
}

const resetZoom = () => {
  zoom.value = 1
  zoomPercent.value = 100
  rotation.value = 0
  position.value = { x: 0, y: 0 }
}

const rotate = () => {
  rotation.value = (rotation.value + 90) % 360
}

const onWheel = (e) => {
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newZoom = Math.max(0.2, Math.min(5, zoom.value * delta))
  updateZoom(newZoom)
}

const onMouseDown = (e) => {
  if (zoom.value <= 1) return
  isDragging.value = true
  dragStart.value = {
    x: e.clientX,
    y: e.clientY,
    posX: position.value.x,
    posY: position.value.y,
  }
}

const onMouseMove = (e) => {
  if (!isDragging.value) return
  position.value = {
    x: dragStart.value.posX + (e.clientX - dragStart.value.x),
    y: dragStart.value.posY + (e.clientY - dragStart.value.y),
  }
}

const onMouseUp = () => {
  isDragging.value = false
}

// 监听 src 变化时重置
watch(() => props.src, () => {
  resetZoom()
})

const handleKeydown = (e) => {
  if (e.key === 'Escape' && showFullscreen.value) {
    showFullscreen.value = false
  }
}
onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))

onUnmounted(() => {
  isDragging.value = false
})
</script>

<style lang="scss" scoped>
.image-viewer {
  display: flex;
  flex-direction: column;
  width: 100%;
  background: #fafbfc;
  border-radius: 8px;
  overflow: hidden;
}

.viewer-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;

  .zoom-slider {
    flex: 1;
    max-width: 240px;
    margin: 0;
  }
}

.image-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #1e1e1e;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 360px;
  user-select: none;

  &.draggable {
    cursor: grab;
  }
}

.image-wrapper {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transform-origin: center center;
  transition: transform 0.1s ease-out;
  will-change: transform;
}

.viewer-image-fullscreen {
  display: block;
  max-width: 100%;
  max-height: 80vh;
  object-fit: contain;
  user-select: none;
  -webkit-user-drag: none;
}

.fullscreen-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 12px;

  .zoom-slider-large {
    flex: 1;
    max-width: 400px;
    margin: 0;
  }

  .fullscreen-hint {
    color: #909399;
    font-size: 12px;
  }
}

.fullscreen-image-container {
  position: relative;
  overflow: hidden;
  background: #1e1e1e;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  border-radius: 4px;
  user-select: none;

  &.draggable {
    cursor: grab;
  }
}

:deep(.image-zoom-dialog) {
  .el-dialog__body {
    padding: 16px 20px 20px 20px;
  }
}

.viewer-image {
  display: block;
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  user-select: none;
  -webkit-user-drag: none;
}

.overlay-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
  mix-blend-mode: normal;
  user-select: none;
  -webkit-user-drag: none;
}

.placeholder {
  text-align: center;
  color: #909399;
}

.placeholder-icon {
  font-size: 64px;
  color: #555;
  margin-bottom: 12px;
}

.placeholder-text {
  font-size: 16px;
  font-weight: 500;
  color: #aaa;
}

.viewer-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #fff;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #606266;
  flex-shrink: 0;

  .hint {
    color: #909399;
  }
}
</style>