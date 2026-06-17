<template>
  <div class="doctor-detail" v-loading="loading">
    <!-- 顶部 Hero 条 -->
    <div v-if="doctor" class="hero-bar">
      <div class="hero-inner">
        <el-button text @click="goBack" class="back-btn">
          <el-icon><ArrowLeft /></el-icon> 返回名医录
        </el-button>
        <div class="breadcrumb">
          名医录 / {{ doctor.hospital }} / {{ doctor.department }}
        </div>
      </div>
    </div>

    <div class="detail-content" v-if="doctor">
      <!-- 顶部档案区 -->
      <section class="profile">
        <div class="profile-bg"></div>
        <div class="profile-main">
          <el-avatar :size="120" :src="doctor.avatar" class="avatar">
            {{ doctor.name?.[0] }}
          </el-avatar>

          <div class="profile-info">
            <div class="name-row">
              <h1 class="name">{{ doctor.name }}</h1>
              <el-tag v-if="doctor.title" type="warning" effect="dark" size="large">
                {{ doctor.title.replace(/[、，,]/g, ' / ') }}
              </el-tag>
            </div>

            <div class="meta-grid">
              <div class="meta-item">
                <el-icon><FirstAidKit /></el-icon>
                <span class="label">科室</span>
                <span class="value">{{ doctor.department }}</span>
              </div>
              <div class="meta-item">
                <el-icon><OfficeBuilding /></el-icon>
                <span class="label">医院</span>
                <span class="value">{{ doctor.hospital }}</span>
              </div>
              <div class="meta-item" v-if="doctor.city">
                <el-icon><Location /></el-icon>
                <span class="label">城市</span>
                <span class="value">{{ doctor.city }}</span>
              </div>
            </div>
          </div>

          <div class="profile-actions">
            <el-button type="primary" size="large" plain>
              <el-icon><Phone /></el-icon> 咨询
            </el-button>
            <el-button size="large" plain>
              <el-icon><Star /></el-icon> 收藏
            </el-button>
          </div>
        </div>
      </section>

      <!-- 主体两栏布局 -->
      <div class="body-grid">
        <!-- 左:擅长 + 简介 -->
        <div class="main-col">
          <section v-if="doctor.diseases" class="card-section">
            <div class="section-header">
              <el-icon class="section-icon"><FirstAidKit /></el-icon>
              <h3>擅长疾病</h3>
            </div>
            <div class="diseases">
              <span v-for="d in doctor.diseases.split(',')" :key="d" class="disease-tag">
                {{ d.trim() }}
              </span>
            </div>
          </section>

          <section v-if="doctor.bio" class="card-section">
            <div class="section-header">
              <el-icon class="section-icon"><Reading /></el-icon>
              <h3>医生简介</h3>
            </div>
            <p class="bio">{{ doctor.bio }}</p>
          </section>
        </div>

        <!-- 右:扩展信息 -->
        <div class="side-col">
          <section class="card-section">
            <div class="section-header">
              <el-icon class="section-icon"><InfoFilled /></el-icon>
              <h3>详细信息</h3>
            </div>

            <div v-if="doctor.extra?.address" class="info-row">
              <div class="info-label">
                <el-icon><Location /></el-icon> 详细地址
              </div>
              <div class="info-value">{{ doctor.extra.address }}</div>
            </div>

            <div v-if="doctor.extra?.schedule" class="info-row">
              <div class="info-label">
                <el-icon><Clock /></el-icon> 出诊信息
              </div>
              <div class="info-value">{{ doctor.extra.schedule }}</div>
            </div>

            <div v-if="doctor.extra?.registration" class="info-row">
              <div class="info-label">
                <el-icon><Connection /></el-icon> 挂号方式
              </div>
              <div class="info-value">{{ doctor.extra.registration }}</div>
            </div>

            <div v-if="doctor.extra?.achievements" class="info-row">
              <div class="info-label">
                <el-icon><Medal /></el-icon> 学术成果
              </div>
              <div class="info-value">{{ doctor.extra.achievements }}</div>
            </div>

            <div v-if="!hasExtra" class="empty-tip">
              <el-icon><DocumentRemove /></el-icon>
              <span>暂无扩展信息</span>
            </div>
          </section>

          <section class="card-section tip-card">
            <div class="tip-icon">
              <el-icon :size="20"><WarningFilled /></el-icon>
            </div>
            <p>本平台展示的医生信息仅供参考,实际就诊请以医院官方信息为准。</p>
          </section>
        </div>
      </div>
    </div>

    <el-empty v-else-if="!loading" description="医生信息不存在" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { doctorApi } from '@/api/doctor'

const route = useRoute()
const router = useRouter()
const doctor = ref(null)
const loading = ref(false)

const hasExtra = computed(() => {
  if (!doctor.value?.extra) return false
  return Object.values(doctor.value.extra).some(v => v)
})

const load = async () => {
  loading.value = true
  doctor.value = null
  try {
    doctor.value = await doctorApi.detail(route.params.id)
  } catch (e) {
    // 找不到医生时直接跳回列表,避免空页 + 全局错误 toast 在列表页残留
    ElMessage.warning('该医生不存在或已下线,正在返回名医录')
    router.replace('/doctors')
  } finally {
    loading.value = false
  }
}

const goBack = () => router.push('/doctors')

onMounted(load)
</script>

<style lang="scss" scoped>
@use '@/styles/tokens.scss' as t;

.doctor-detail {
  width: 100%;
}

/* ============================================
   顶部导航条
   ============================================ */
.hero-bar {
  background: #fff;
  border-bottom: 1px solid t.c('border');
  margin: -16px -16px 0;
  padding: t.sp(4) t.sp(6);
  margin-bottom: t.sp(6);
}
.hero-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: t.sp(4);
}
.back-btn {
  font-size: 14px;
}
.breadcrumb {
  color: t.c('text-3');
  font-size: 13px;
}

/* ============================================
   主体内容容器
   ============================================ */
.detail-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 t.sp(6);
}

/* ============================================
   档案区
   ============================================ */
.profile {
  position: relative;
  background: #fff;
  border: 1px solid t.c('border');
  border-radius: t.r('xl');
  overflow: hidden;
  margin-bottom: t.sp(6);
  box-shadow: t.shadow('sm');
}
.profile-bg {
  height: 120px;
  background: linear-gradient(135deg, t.c('primary-700') 0%, t.c('primary-500') 60%, t.c('primary-300') 100%);
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
      radial-gradient(circle at 80% 30%, rgba(255,255,255,0.18) 0%, transparent 40%),
      radial-gradient(circle at 20% 80%, rgba(255,255,255,0.12) 0%, transparent 50%);
  }
}
.profile-main {
  padding: 0 t.sp(8) t.sp(6);
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: t.sp(6);
  align-items: end;

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
    padding: 0 t.sp(5) t.sp(5);
    text-align: center;
  }
}
.avatar {
  margin-top: -60px;
  border: 4px solid #fff;
  box-shadow: t.shadow('md');
  background: #fff;
}

.profile-info {
  padding-bottom: t.sp(4);
}
.name-row {
  display: flex;
  align-items: center;
  gap: t.sp(3);
  margin-bottom: t.sp(3);
  flex-wrap: wrap;

  @media (max-width: 768px) { justify-content: center; }
}
.name {
  margin: 0;
  font-family: t.font("serif");
  font-size: 32px;
  font-weight: 700;
  color: t.c('text-1');
  line-height: 1.2;
}

.meta-grid {
  display: flex;
  flex-wrap: wrap;
  gap: t.sp(5);

  @media (max-width: 768px) { justify-content: center; }
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;

  .el-icon { color: t.c('primary-500'); font-size: 16px; }
  .label { color: t.c('text-3'); }
  .value { color: t.c('text-1'); font-weight: 500; }
}

.profile-actions {
  padding-bottom: t.sp(4);
  display: flex;
  gap: t.sp(3);

  @media (max-width: 768px) { justify-content: center; }
}

/* ============================================
   主体两栏
   ============================================ */
.body-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr);
  gap: t.sp(6);

  @media (max-width: 960px) {
    grid-template-columns: 1fr;
  }
}

.main-col, .side-col {
  display: flex;
  flex-direction: column;
  gap: t.sp(5);
}

/* ============================================
   卡片 section
   ============================================ */
.card-section {
  background: #fff;
  border: 1px solid t.c('border');
  border-radius: t.r('xl');
  padding: t.sp(5) t.sp(6);
  box-shadow: t.shadow('sm');
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: t.sp(4);
  padding-bottom: t.sp(3);
  border-bottom: 1px solid t.c('border');

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: t.c('text-1');
  }
  .section-icon {
    color: t.c('primary-500');
    font-size: 18px;
  }
}

.diseases {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.disease-tag {
  display: inline-block;
  padding: 6px 14px;
  background: t.c('primary-50');
  color: t.c('primary-700');
  border-radius: t.r('full');
  font-size: 13px;
  font-weight: 500;
  border: 1px solid t.c('primary-100');
  transition: all t.dur("fast") t.ease("out");

  &:hover {
    background: t.c('primary-100');
    transform: translateY(-1px);
  }
}

.bio {
  color: t.c('text-2');
  line-height: 1.9;
  font-size: 14px;
  margin: 0;
  white-space: pre-wrap;
}

/* ============================================
   右侧信息行
   ============================================ */
.info-row {
  padding: t.sp(3) 0;
  border-bottom: 1px dashed t.c('border');

  &:last-child { border-bottom: none; padding-bottom: 0; }
  &:first-of-type { padding-top: 0; }
}
.info-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: t.c('text-3');
  font-size: 13px;
  margin-bottom: 6px;

  .el-icon { color: t.c('primary-500'); }
}
.info-value {
  color: t.c('text-1');
  font-size: 14px;
  line-height: 1.7;
}

.empty-tip {
  text-align: center;
  padding: t.sp(6) 0;
  color: t.c('text-3');
  font-size: 13px;

  .el-icon { font-size: 32px; margin-bottom: 8px; display: block; }
  span { display: block; }
}

/* ============================================
   提示卡
   ============================================ */
.tip-card {
  background: t.c('warn-50');
  border: 1px solid lighten(#E89B6C, 20%);
  display: flex;
  gap: t.sp(3);
  align-items: flex-start;

  .tip-icon {
    color: t.c('warn-700');
    flex-shrink: 0;
  }
  p {
    margin: 0;
    color: t.c('warn-700');
    font-size: 13px;
    line-height: 1.7;
  }
}
</style>
