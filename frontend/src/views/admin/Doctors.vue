<template>
  <div class="doctors-admin">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3><el-icon><UserFilled /></el-icon> 名医录管理</h3>
          <div class="actions">
            <el-button @click="reindex" :loading="reindexing">
              <el-icon><Refresh /></el-icon>
              重建索引
              <el-tag v-if="reindexStatus === 'running'" type="warning" size="small" effect="dark" style="margin-left: 6px">
                重建中 {{ reindexProgress.current }}/{{ reindexProgress.total }}
              </el-tag>
              <el-tag v-else-if="reindexStatus === 'finished'" type="success" size="small" effect="dark" style="margin-left: 6px">
                已完成
              </el-tag>
            </el-button>
            <el-button type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon> 新增医生
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column label="ID" prop="id" width="60" />
        <el-table-column label="姓名" prop="name" width="100" />
        <el-table-column label="科室" prop="department" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="primary">{{ row.department }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="医院" prop="hospital" min-width="180" show-overflow-tooltip />
        <el-table-column label="职称" prop="title" width="100" />
        <el-table-column label="城市" prop="city" width="80" />
        <el-table-column label="擅长疾病" prop="diseases" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">查看</el-button>
            <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        class="pagination"
        @current-change="load"
        @size-change="load"
      />
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="showEdit" :title="form.id ? '编辑医生' : '新增医生'" width="780px">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="姓名" required>
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="职称">
              <el-select v-model="form.title" clearable allow-create filterable placeholder="例:主任医师" style="width: 100%">
                <el-option label="主任医师" value="主任医师" />
                <el-option label="副主任医师" value="副主任医师" />
                <el-option label="主治医师" value="主治医师" />
                <el-option label="教授" value="教授" />
                <el-option label="副教授" value="副教授" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="科室" required>
              <el-input v-model="form.department" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="城市">
              <el-input v-model="form.city" placeholder="例:北京" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="医院" required>
          <el-input v-model="form.hospital" />
        </el-form-item>

        <el-form-item label="擅长疾病">
          <el-input v-model="form.diseases" placeholder="逗号分隔,例:肝癌,肺癌,胃癌" />
        </el-form-item>

        <el-form-item label="头像 URL">
          <el-input v-model="form.avatar" placeholder="可选,留空则用首字" />
        </el-form-item>

        <el-form-item label="医生简介">
          <el-input v-model="form.bio" type="textarea" :rows="3" placeholder="用于 AI 语义检索,尽量详细" />
        </el-form-item>

        <el-divider content-position="left">扩展信息(可选,JSON 格式)</el-divider>

        <el-form-item label="详细地址">
          <el-input v-model="extra.address" placeholder="例:北京市朝阳区xxx路xx号" />
        </el-form-item>
        <el-form-item label="出诊信息">
          <el-input v-model="extra.schedule" placeholder="例:周一上午、周三下午" />
        </el-form-item>
        <el-form-item label="挂号方式">
          <el-input v-model="extra.registration" placeholder="例:医院公众号/微医app" />
        </el-form-item>
        <el-form-item label="学术成果">
          <el-input v-model="extra.achievements" type="textarea" :rows="2" placeholder="例:SCI 论文 30 篇,主持国自然 2 项" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ form.id ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetail" :title="detail?.name || '医生详情'" width="600px">
      <div v-if="detail" class="detail-body">
        <p><strong>科室:</strong> {{ detail.department }}</p>
        <p><strong>医院:</strong> {{ detail.hospital }}<span v-if="detail.city"> ({{ detail.city }})</span></p>
        <p v-if="detail.title"><strong>职称:</strong> {{ detail.title }}</p>
        <p v-if="detail.diseases"><strong>擅长疾病:</strong> {{ detail.diseases }}</p>
        <p v-if="detail.bio"><strong>简介:</strong> {{ detail.bio }}</p>
        <template v-if="detail.extra">
          <p v-if="detail.extra.address"><strong>地址:</strong> {{ detail.extra.address }}</p>
          <p v-if="detail.extra.schedule"><strong>出诊:</strong> {{ detail.extra.schedule }}</p>
          <p v-if="detail.extra.registration"><strong>挂号:</strong> {{ detail.extra.registration }}</p>
          <p v-if="detail.extra.achievements"><strong>成果:</strong> {{ detail.extra.achievements }}</p>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { doctorApi } from '@/api/doctor'
import { adminApi } from '@/api/admin'

const list = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const size = ref(20)

// ===== reindex 异步任务状态 =====
const reindexing = ref(false)
const reindexStatus = ref('idle')   // idle/queued/running/finished/error
const reindexProgress = reactive({ current: 0, total: 0 })
let pollTimer = null

const load = async () => {
  loading.value = true
  try {
    const res = await doctorApi.list({ page: page.value, size: size.value })
    list.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const showEdit = ref(false)
const saving = ref(false)
const form = reactive({ id: null, name: '', department: '', hospital: '', title: '', diseases: '', city: '', avatar: '', bio: '', extra: null })
const extra = reactive({ address: '', schedule: '', registration: '', achievements: '' })

const openCreate = () => {
  Object.assign(form, { id: null, name: '', department: '', hospital: '', title: '', diseases: '', city: '', avatar: '', bio: '', extra: null })
  Object.assign(extra, { address: '', schedule: '', registration: '', achievements: '' })
  showEdit.value = true
}

const openEdit = (row) => {
  Object.assign(form, row)
  // 展开 extra
  const e = row.extra || {}
  Object.assign(extra, { address: e.address || '', schedule: e.schedule || '', registration: e.registration || '', achievements: e.achievements || '' })
  showEdit.value = true
}

const buildPayload = () => {
  // 收集 extra 中非空字段
  const e = {}
  if (extra.address) e.address = extra.address
  if (extra.schedule) e.schedule = extra.schedule
  if (extra.registration) e.registration = extra.registration
  if (extra.achievements) e.achievements = extra.achievements
  return {
    name: form.name,
    department: form.department,
    hospital: form.hospital,
    title: form.title || null,
    diseases: form.diseases || null,
    city: form.city || null,
    avatar: form.avatar || null,
    bio: form.bio || null,
    extra: Object.keys(e).length ? e : null
  }
}

const save = async () => {
  if (!form.name.trim() || !form.department.trim() || !form.hospital.trim()) {
    ElMessage.warning('请填写姓名、科室、医院')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (form.id) {
      await adminApi.updateDoctor(form.id, payload)
      ElMessage.success('已更新(点击「重建索引」后即可被语义检索到)')
    } else {
      await adminApi.createDoctor(payload)
      ElMessage.success('已创建(点击「重建索引」后即可被语义检索到)')
    }
    showEdit.value = false
    load()
  } finally {
    saving.value = false
  }
}

const confirmDelete = async (row) => {
  await ElMessageBox.confirm(`确认删除「${row.name}」?`, '提示', { type: 'warning' })
  await adminApi.deleteDoctor(row.id)
  ElMessage.success('已删除(记得重建索引)')
  load()
}

// ===== reindex 异步任务 =====
const pollReindex = async () => {
  try {
    const res = await adminApi.reindexStatus()
    reindexStatus.value = res.status
    reindexProgress.current = res.progress.current || 0
    reindexProgress.total = res.progress.total || 0
    if (res.status === 'finished') {
      ElMessage.success(`索引重建完成: ${res.progress.current} 条`)
      reindexing.value = false
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    } else if (res.status === 'error') {
      ElMessage.error(`索引重建失败: ${res.progress.error || '未知错误'}`)
      reindexing.value = false
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    }
  } catch (e) {
    // 静默失败,不影响 UI
  }
}

const reindex = async () => {
  if (reindexing.value) {
    ElMessage.warning('正在重建中,请等待完成')
    return
  }
  reindexing.value = true
  try {
    await adminApi.reindexAsync()
    ElMessage.info('已加入后台队列,执行中...')
    // 启动轮询
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(pollReindex, 1500)
  } catch (e) {
    reindexing.value = false
    ElMessage.error('请求失败: ' + (e?.message || e))
  }
}

onMounted(() => {
  load()
  pollReindex()  // 进入页面时拉一次当前状态
})
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

const showDetail = ref(false)
const detail = ref(null)
const viewDetail = async (row) => {
  detail.value = await doctorApi.detail(row.id)
  showDetail.value = true
}

onMounted(load)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
  .actions { display: flex; gap: 8px; }
}
.pagination { margin-top: 16px; justify-content: flex-end; display: flex; }
.detail-body p { line-height: 1.8; color: #303133; }
</style>
