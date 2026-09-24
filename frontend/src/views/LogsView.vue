<template>
  <div class="page logs-page">
    <div class="card toolbar">
      <div class="filters">
        <el-select v-model="q.level" placeholder="级别" clearable class="f-item">
          <el-option label="INFO" value="INFO" />
          <el-option label="WARN" value="WARN" />
          <el-option label="ERROR" value="ERROR" />
        </el-select>
        <el-select v-model="q.module" placeholder="模块" clearable class="f-item">
          <el-option v-for="m in modules" :key="m" :label="m" :value="m" />
        </el-select>
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
                        start-placeholder="开始日期" end-placeholder="结束日期" class="f-item range" />
        <el-input v-model="q.search" placeholder="搜索日志…" clearable :prefix-icon="Search"
                  class="f-item search" @input="debouncedLoad" @clear="load" />
        <el-button type="primary" :icon="Search" @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
      <div class="toolbar-right">
        <span class="muted auto-hint">
          自动清理：{{ settings.log_auto_clear === '1' ? `保留最近 ${settings.log_retention_days} 天` : '已关闭' }}
        </span>
        <el-button type="danger" plain :icon="Delete" @click="clearAll">清空日志</el-button>
      </div>
    </div>

    <div class="card table-card" v-loading="loading">
      <el-table :data="items" stripe size="small" class="dc-table" height="100%">
        <template #empty><el-empty description="暂无日志" :image-size="72" /></template>
        <el-table-column prop="level" label="级别" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.level === 'ERROR' ? 'danger' : row.level === 'WARN' ? 'warning' : 'info'">
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="110" align="center">
          <template #default="{ row }">{{ row.module }}</template>
        </el-table-column>
        <el-table-column prop="message" label="内容" min-width="300" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="170" align="center" />
      </el-table>
    </div>

    <div class="card pagination-card">
      <el-pagination v-model:current-page="page" :page-size="size" :total="total"
                     :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next"
                     @update:current-page="load" @update:page-size="v => { size = v; load() }" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete } from '@element-plus/icons-vue'
import { http } from '@/api'

const q = reactive({ level: '', module: '', search: '' })
const range = ref(null)
const modules = ref([])
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(50)
const loading = ref(false)
const settings = reactive({ log_auto_clear: '0', log_retention_days: '30' })

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: size.value, level: q.level, module: q.module, search: q.search }
    if (range.value?.length === 2) {
      params.start = range.value[0]
      params.end = range.value[1]
    }
    const res = await http.get('/syslogs', { params })
    items.value = res.items
    total.value = res.total
    modules.value = res.modules
  } finally {
    loading.value = false
  }
}

let t = null
function debouncedLoad() {
  clearTimeout(t)
  t = setTimeout(load, 300)
}

function reset() {
  q.level = q.module = q.search = ''
  range.value = null
  page.value = 1
  load()
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空全部系统日志吗？此操作不可恢复。', '清空确认',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' })
  } catch { return }
  await http.delete('/syslogs')
  ElMessage.success('系统日志已清空')
  load()
}

onMounted(async () => {
  load()
  try {
    const res = await http.get('/settings')
    Object.assign(settings, res.settings)
  } catch { /* ignore */ }
})
</script>

<style scoped>
.logs-page { height: 100%; overflow: hidden; }
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; padding: 10px 12px; flex: none; flex-wrap: wrap;
}
.filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: 10px; }
.auto-hint { white-space: nowrap; font-size: 12px; }
.f-item { width: 130px; }
.f-item.range { width: 240px; }
.f-item.search { width: 200px; }
.table-card { flex: 1; min-height: 0; padding: 6px 6px 2px; overflow: hidden; }
.pagination-card { padding: 8px 12px; flex: none; display: flex; justify-content: flex-end; }

@media (max-width: 768px) {
  .logs-page { overflow-y: auto; }
  .f-item, .f-item.range, .f-item.search { width: 100%; }
  .toolbar-right { width: 100%; justify-content: space-between; }
}
</style>
