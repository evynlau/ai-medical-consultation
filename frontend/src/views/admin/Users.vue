<template>
  <div class="users">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3><el-icon><User /></el-icon> 用户管理</h3>
          <div class="filters">
            <el-input v-model="filters.keyword" placeholder="搜索用户名/邮箱/姓名" clearable style="width: 240px" @keydown.enter="load" />
            <el-select v-model="filters.role" placeholder="角色" clearable style="width: 110px" @change="load">
              <el-option label="全部" :value="null" />
              <el-option label="管理员" value="admin" />
              <el-option label="医生" value="doctor" />
              <el-option label="普通用户" value="user" />
            </el-select>
            <el-button type="primary" @click="load">查询</el-button>
          </div>
        </div>
      </template>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column label="ID" prop="id" width="60" />
        <el-table-column label="用户名" prop="username" width="130" />
        <el-table-column label="邮箱" prop="email" width="220" show-overflow-tooltip />
        <el-table-column label="姓名" prop="full_name" width="100" />
        <el-table-column label="年龄/性别" width="100">
          <template #default="{ row }">
            {{ row.age || '-' }} / {{ row.gender || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="角色" width="180">
          <template #default="{ row }">
            <el-tag v-if="row.is_admin" type="danger" size="small" effect="dark" style="margin-right: 4px">管理员</el-tag>
            <el-tag v-if="row.is_doctor" type="success" size="small" effect="dark" style="margin-right: 4px">医生</el-tag>
            <el-tag v-if="row.specialty" size="small">{{ row.specialty }}</el-tag>
            <span v-if="!row.is_admin && !row.is_doctor" style="color: #909399">普通用户</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '正常' : '封禁' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-dropdown @command="(c) => handleCmd(c, row)">
              <el-button size="small">
                操作 <el-icon><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="toggle_admin" :disabled="row.id === userStore.profile?.id">
                    {{ row.is_admin ? '取消管理员' : '设为管理员' }}
                  </el-dropdown-item>
                  <el-dropdown-item command="toggle_doctor">
                    {{ row.is_doctor ? '取消医生' : '设为医生' }}
                  </el-dropdown-item>
                  <el-dropdown-item command="set_specialty" v-if="row.is_doctor">
                    设置科室
                  </el-dropdown-item>
                  <el-dropdown-item divided command="toggle_active">
                    {{ row.is_active ? '封禁账号' : '解封账号' }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 设置科室对话框 -->
    <el-dialog v-model="showSpecialty" title="设置医生科室" width="400px">
      <el-form>
        <el-form-item label="科室">
          <el-select v-model="specialtyForm.specialty" filterable allow-create style="width: 100%">
            <el-option label="心血管内科" value="心血管内科" />
            <el-option label="神经内科" value="神经内科" />
            <el-option label="呼吸内科" value="呼吸内科" />
            <el-option label="消化内科" value="消化内科" />
            <el-option label="皮肤科" value="皮肤科" />
            <el-option label="急诊科" value="急诊科" />
            <el-option label="全科医学科" value="全科医学科" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSpecialty = false">取消</el-button>
        <el-button type="primary" @click="saveSpecialty">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '@/api/admin'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const list = ref([])
const loading = ref(false)
const filters = reactive({ keyword: '', role: null })
const formatTime = (iso) => iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-'

const load = async () => {
  loading.value = true
  try {
    list.value = await adminApi.users({
      keyword: filters.keyword || undefined,
      role: filters.role || undefined
    })
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const handleCmd = async (cmd, row) => {
  let payload = {}
  let action = ''
  if (cmd === 'toggle_admin') {
    payload = { is_admin: !row.is_admin }
    action = row.is_admin ? '取消管理员' : '设为管理员'
  } else if (cmd === 'toggle_doctor') {
    payload = { is_doctor: !row.is_doctor }
    action = row.is_doctor ? '取消医生' : '设为医生'
  } else if (cmd === 'toggle_active') {
    await ElMessageBox.confirm(`确认${row.is_active ? '封禁' : '解封'}该用户?`, '提示', { type: 'warning' })
    payload = { is_active: !row.is_active }
    action = row.is_active ? '封禁' : '解封'
  } else if (cmd === 'set_specialty') {
    specialtyForm.userId = row.id
    specialtyForm.specialty = row.specialty || ''
    showSpecialty.value = true
    return
  }
  if (cmd !== 'set_specialty') {
    await ElMessageBox.confirm(`确认「${action}」?`, '提示', { type: 'warning' })
    await adminApi.updateUser(row.id, payload)
    ElMessage.success('已更新')
    load()
  }
}

const showSpecialty = ref(false)
const specialtyForm = reactive({ userId: null, specialty: '' })
const saveSpecialty = async () => {
  await adminApi.updateUser(specialtyForm.userId, { specialty: specialtyForm.specialty })
  ElMessage.success('已更新')
  showSpecialty.value = false
  load()
}

onMounted(load)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
  .filters { display: flex; gap: 8px; }
}
</style>
