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
                  class="f-item search" @input="debouncedLoad" @clear="reload" />
        <el-button type="primary" :icon="Search" @click="reload">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
      <div class="toolbar-right">
        <el-segmented v-model="mode" :options="modeOptions" size="default" @change="reload" />
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

    <div v-if="mode === 'page'" class="card pagination-card">
      <el-pagination v-model:current-page="page" :page-size="size" :total="total"
                     :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next"
                     @update:current-page="load(false)" @update:page-size="v => { size = v; reload() }" />
    </div>
    <!-- 懒加载模式提示 -->
    <div v-else-if="items.length" class="load-hint muted">
      {{ hasMore ? '下拉加载更多…' : `已全部加载（${items.length} 条）` }}
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
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
const loadingMore = ref(false)

/* 展示模式：懒加载 / 分页，本地记忆 */
const mode = ref(localStorage.getItem('dc-logs-mode') || 'lazy')
const modeOptions = [
  { label: '懒加载', value: 'lazy' },
  { label: '分页', value: 'page' }
]
watch(mode, v => localStorage.setItem('dc-logs-mode', v))
const LAZY_SIZE = 50
const hasMore = computed(() => items.value.length < total.value)

async function load(append = false) {
  if (append) loadingMore.value = true
  else loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: mode.value === 'page' ? size.value : LAZY_SIZE,
      level: q.level, module: q.module, search: q.search
    }
    if (range.value?.length === 2) {
      params.start = range.value[0]
      params.end = range.value[1]
    }
    const res = await http.get('/syslogs', { params })
    if (append) items.value.push(...res.items)
    else items.value = res.items
    total.value = res.total
    modules.value = res.modules
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function reload() {
  page.value = 1
  load(false)
}

/* 懒加载：表格滚动触底自动追加 */
let scrollEl = null
let scrollTimer = null
function onBodyScroll() {
  if (mode.value !== 'lazy' || !hasMore.value || loadingMore.value || loading.value) return
  clearTimeout(scrollTimer)
  scrollTimer = setTimeout(() => {
    if (!scrollEl) return
    if (scrollEl.scrollTop + scrollEl.clientHeight >= scrollEl.scrollHeight - 60) {
      page.value++
      load(true)
    }
  }, 80)
}

let t = null
function debouncedLoad() {
  clearTimeout(t)
  t = setTimeout(reload, 300)
}

function reset() {
  q.level = q.module = q.search = ''
  range.value = null
  reload()
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空全部系统日志吗？此操作不可恢复。', '清空确认',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' })
  } catch { return }
  await http.delete('/syslogs')
  ElMessage.success('系统日志已清空')
  reload()
}

onMounted(() => {
  reload()
  /* 在 el-table 渲染后挂载滚动监听 */
  setTimeout(() => {
    scrollEl = document.querySelector('.logs-page .table-card .el-scrollbar__wrap') ||
              document.querySelector('.logs-page .table-card .el-table__body-wrapper')
    scrollEl?.addEventListener('scroll', onBodyScroll, { passive: true })
  }, 500)
})

onBeforeUnmount(() => scrollEl?.removeEventListener('scroll', onBodyScroll))
</script>

<style scoped>
.logs-page { height: 100%; overflow: hidden; }
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; padding: 10px 12px; flex: none; flex-wrap: wrap;
}
.filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.f-item { width: 130px; }
.f-item.range { width: 240px; }
.f-item.search { width: 200px; }
.table-card { flex: 1; min-height: 0; padding: 0; overflow: hidden; }
.pagination-card { padding: 8px 12px; flex: none; display: flex; justify-content: flex-end; }
.load-hint { text-align: center; font-size: 12px; padding: 6px 0 2px; flex: none; }
.toolbar-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

@media (max-width: 768px) {
  .logs-page { overflow-y: auto; }
  .f-item, .f-item.range, .f-item.search { width: 100%; }
  .toolbar-right { width: 100%; justify-content: space-between; }
}
</style>
