<template>
  <div class="card cal-card">
    <div class="cal-head">
      <div class="card-title">数据日历</div>
      <div class="muted cal-sub">颜色深浅表示当日新增数量，点击日期查看当天动态</div>
      <div class="cal-nav">
        <el-button size="small" text bg :icon="ArrowLeft" @click="shiftMonth(-1)" />
        <span class="cal-month tabular">{{ label }}</span>
        <el-button size="small" text bg :icon="ArrowRight" @click="shiftMonth(1)" />
        <el-button size="small" @click="goToday">今天</el-button>
      </div>
    </div>
    <div class="cal-grid cal-weeks">
      <div v-for="w in WEEKS" :key="w" class="cal-wd">{{ w }}</div>
    </div>
    <div class="cal-grid">
      <div v-for="(c, i) in cells" :key="i"
           class="cal-cell" :class="{ blank: !c, today: c?.date === todayStr, selected: c?.date === selected }"
           :style="c ? cellStyle(c) : null" @click="c && openDay(c)">
        <template v-if="c">
          <span class="cal-day tabular">{{ c.day }}</span>
          <span v-if="c.count" class="cal-count tabular">{{ c.count }}</span>
        </template>
      </div>
    </div>
  </div>

  <!-- 当日动态弹窗 -->
  <el-dialog v-model="dayOpen" width="600px" append-to-body destroy-on-close
             :title="`${selected} · 当日动态（${dayItems.length}）`">
    <div v-loading="dayLoading" class="day-body">
      <el-empty v-if="!dayItems.length && !dayLoading" description="当天无数据变更" :image-size="64" />
      <el-scrollbar v-else max-height="400px">
        <div class="day-list">
          <div v-for="r in dayItems" :key="r.id" class="day-item">
            <el-tag size="small" :type="r.kind === 'add' ? 'success' : 'warning'" effect="plain" class="day-kind">
              {{ r.kind === 'add' ? '新增' : '修改' }}
            </el-tag>
            <el-tag size="small" effect="plain" class="day-table">{{ r.table_name }}</el-tag>
            <span class="day-drawing">{{ r.data.drawing_no || r.data.name || '—' }}</span>
            <span class="day-name">{{ r.data.name || '' }}</span>
            <span class="muted day-time tabular">{{ timeOf(r) }}</span>
          </div>
        </div>
      </el-scrollbar>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { http } from '@/api'

const WEEKS = ['一', '二', '三', '四', '五', '六', '日']

function pad(n) { return String(n).padStart(2, '0') }
const today = new Date()
const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`

const month = ref(todayStr.slice(0, 7))
const days = reactive({})
const selected = ref(todayStr)
const dayOpen = ref(false)
const dayLoading = ref(false)
const dayItems = ref([])

const label = computed(() => {
  const [y, m] = month.value.split('-').map(Number)
  return `${y} 年 ${m} 月`
})

const cells = computed(() => {
  const [y, m] = month.value.split('-').map(Number)
  const daysInMonth = new Date(y, m, 0).getDate()
  let lead = new Date(y, m - 1, 1).getDay() - 1   // 周一开始
  if (lead < 0) lead = 6
  const arr = []
  for (let i = 0; i < lead; i++) arr.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const date = `${month.value}-${pad(d)}`
    arr.push({ date, day: d, count: days[date] || 0 })
  }
  return arr
})

const maxCount = computed(() => Math.max(1, ...Object.values(days)))

function cellStyle(c) {
  if (!c.count) return {}
  const pct = c.count / maxCount.value
  const alpha = Math.round(14 + pct * 44)   // 14% ~ 58%，颜色随数量加深
  return { background: `color-mix(in srgb, var(--dc-primary) ${alpha}%, var(--dc-card))` }
}

async function load() {
  const res = await http.get('/dashboard/calendar', { params: { month: month.value } })
  Object.keys(days).forEach(k => delete days[k])
  Object.assign(days, res.days || {})
}

function shiftMonth(n) {
  const [y, m] = month.value.split('-').map(Number)
  const d = new Date(y, m - 1 + n, 1)
  month.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}`
  load()
}

function goToday() {
  month.value = todayStr.slice(0, 7)
  load()
}

async function openDay(c) {
  selected.value = c.date
  dayOpen.value = true
  dayLoading.value = true
  try {
    const res = await http.get('/dashboard/day', { params: { date: c.date } })
    dayItems.value = res.items || []
  } finally {
    dayLoading.value = false
  }
}

function timeOf(r) {
  return (r.kind === 'add' ? r.created_at : r.updated_at) || ''
}

onMounted(load)
</script>

<style scoped>
.cal-card { padding: 14px 16px; }
.cal-head { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.card-title { font-size: 14px; font-weight: 600; }
.cal-sub { font-size: 12px; flex: 1; min-width: 120px; }
.cal-nav { display: flex; align-items: center; gap: 6px; margin-left: auto; }
.cal-month { font-size: 14px; font-weight: 600; min-width: 84px; text-align: center; }

.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; }
.cal-weeks { gap: 0; margin-bottom: 4px; }
.cal-wd { text-align: center; font-size: 12px; color: var(--dc-text-soft); font-weight: 500; padding: 3px 0; }

.cal-cell {
  position: relative; height: 50px; border-radius: 8px;
  border: 1px solid var(--dc-border); cursor: pointer;
  display: flex; align-items: flex-end; justify-content: space-between;
  padding: 6px 8px;
  transition: transform .15s, box-shadow .15s;
}
.cal-cell:hover { transform: translateY(-1px); box-shadow: var(--dc-shadow); }
.cal-cell.blank { border-color: transparent; cursor: default; background: transparent; }
.cal-cell.blank:hover { transform: none; box-shadow: none; }
.cal-cell.today { box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--dc-primary) 55%, transparent); }
.cal-cell.selected { outline: 2px solid var(--dc-primary); outline-offset: 1.5px; }
.cal-day { font-size: 13px; font-weight: 600; color: var(--dc-text); }
.cal-count {
  font-size: 11px; line-height: 17px; padding: 0 7px;
  color: var(--dc-primary); background: color-mix(in srgb, var(--dc-card) 72%, transparent);
  border-radius: 999px;
}

.day-body { min-height: 120px; }
.day-list { display: flex; flex-direction: column; }
.day-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 4px; border-bottom: 1px solid var(--dc-border); font-size: 13px;
}
.day-item:last-child { border-bottom: none; }
.day-table { flex: none; max-width: 170px; overflow: hidden; }
.day-drawing { font-weight: 600; color: var(--dc-primary); flex: none; }
.day-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.day-time { margin-left: auto; flex: none; font-size: 12px; }

@media (max-width: 768px) {
  .cal-cell { height: 42px; padding: 4px 5px; }
  .cal-day { font-size: 12px; }
  .cal-count { padding: 0 5px; }
  .cal-sub { display: none; }
}
</style>
