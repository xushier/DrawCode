<template>
  <div class="card cal-card">
    <div class="cal-head">
      <div class="card-title">数据日历</div>
      <div class="cal-nav">
        <el-button size="small" text bg :icon="ArrowLeft" @click="shiftMonth(-1)" />
        <span class="cal-month tabular">{{ label }}</span>
        <el-button size="small" text bg :icon="ArrowRight" @click="shiftMonth(1)" />
        <el-button size="small" @click="goToday">今天</el-button>
      </div>
    </div>
    <div class="cal-table">
      <div class="cal-grid cal-weeks">
        <div v-for="w in WEEKS" :key="w" class="cal-wd">{{ w }}</div>
      </div>
      <div class="cal-grid">
        <div v-for="(c, i) in cells" :key="i"
             class="cal-cell" :class="{ blank: !c, today: c?.date === todayStr, selected: c?.date === selected }"
             :style="c ? cellStyle(c) : null" @click="c && openDay(c)">
          <template v-if="c">
            <div class="cal-top">
              <span class="cal-day tabular" :class="{ 'is-fest': c.fest }">{{ c.day }}</span>
              <span v-if="c.count" class="cal-count tabular">{{ c.count }}</span>
            </div>
            <span class="cal-lunar" :class="{ 'is-fest': c.fest, 'is-month': c.monthStart }">{{ c.lunar }}</span>
          </template>
        </div>
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
import solarLunar from 'solarlunar'

const WEEKS = ['一', '二', '三', '四', '五', '六', '日']

/* 公历节日（公历月-日） */
const SOLAR_FEST = { '1-1': '元旦', '5-1': '劳动节', '10-1': '国庆节' }
/* 农历节日（农历月-日） */
const LUNAR_FEST = { '1-1': '春节', '1-15': '元宵节', '5-5': '端午节', '8-15': '中秋节' }

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

/* 农历 / 节假日信息：节日名红色，初一显示月名 */
function lunarInfo(y, m, d) {
  try {
    const sl = solarLunar.solar2lunar(y, m, d)
    const sf = SOLAR_FEST[`${m}-${d}`]
    const lf = LUNAR_FEST[`${sl.lMonth}-${sl.lDay}`]
    if (sf) return { lunar: sf, fest: true }
    if (lf) return { lunar: lf, fest: true }
    if (sl.isTerm) {
      const qm = sl.term === '清明'
      return { lunar: qm ? '清明节' : sl.term, fest: qm }
    }
    if (sl.lDay === 1) return { lunar: sl.monthCn, fest: false, monthStart: true }
    return { lunar: sl.dayCn, fest: false }
  } catch { return { lunar: '', fest: false } }
}

const cells = computed(() => {
  const [y, m] = month.value.split('-').map(Number)
  const daysInMonth = new Date(y, m, 0).getDate()
  let lead = new Date(y, m - 1, 1).getDay() - 1   // 周一开始
  if (lead < 0) lead = 6
  const arr = []
  for (let i = 0; i < lead; i++) arr.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const date = `${month.value}-${pad(d)}`
    arr.push({ date, day: d, count: days[date] || 0, ...lunarInfo(y, m, d) })
  }
  while (arr.length % 7) arr.push(null)   // 补齐最后一周，保证表格完整
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
.cal-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.card-title { font-size: 14px; font-weight: 600; }
.cal-nav { display: flex; align-items: center; gap: 6px; margin-left: auto; }
.cal-month { font-size: 14px; font-weight: 600; min-width: 84px; text-align: center; }

/* 直角无间距表格风格 */
.cal-table { border: 1px solid var(--dc-border); overflow: hidden; }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); }
.cal-wd {
  text-align: center; font-size: 12px; font-weight: 500;
  color: var(--dc-text-soft); background: var(--dc-bg-soft);
  padding: 6px 0; border-right: 1px solid var(--dc-border);
  border-bottom: 1px solid var(--dc-border);
}
.cal-wd:nth-child(7n) { border-right: none; }

.cal-cell {
  min-height: 60px; padding: 6px 8px 5px; cursor: pointer;
  border-right: 1px solid var(--dc-border); border-bottom: 1px solid var(--dc-border);
  display: flex; flex-direction: column; justify-content: space-between;
}
.cal-cell:nth-child(7n) { border-right: none; }
.cal-cell:nth-last-child(-n+7) { border-bottom: none; }
.cal-cell.blank { cursor: default; background: color-mix(in srgb, var(--dc-bg-soft) 45%, transparent); }
.cal-cell:not(.blank):hover { box-shadow: inset 0 0 0 1.5px var(--dc-primary); }
.cal-cell.today { box-shadow: inset 0 0 0 2px color-mix(in srgb, var(--dc-primary) 65%, transparent); }
.cal-cell.selected { box-shadow: inset 0 0 0 2.5px var(--dc-primary); }

.cal-top { display: flex; align-items: flex-start; justify-content: space-between; }
.cal-day { font-size: 15px; font-weight: 600; color: var(--dc-text); line-height: 1.2; }
.cal-day.is-fest { color: #d05650; }
.cal-count {
  font-size: 12px; font-weight: 600; line-height: 18px; padding: 0 7px;
  color: var(--dc-primary); background: color-mix(in srgb, var(--dc-card) 72%, transparent);
  border-radius: 999px;
}
.cal-lunar { font-size: 11px; color: var(--dc-text-soft); line-height: 1.3; }
.cal-lunar.is-fest { color: #d05650; font-weight: 500; }
.cal-lunar.is-month { color: var(--dc-text); font-weight: 500; }

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
  .cal-cell { min-height: 48px; padding: 4px 5px 3px; }
  .cal-day { font-size: 13px; }
  .cal-count { font-size: 10.5px; line-height: 15px; padding: 0 5px; }
  .cal-lunar { font-size: 10px; }
}
</style>
