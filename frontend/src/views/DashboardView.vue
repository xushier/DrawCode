<template>
  <div class="page dash">
    <!-- 统计卡 -->
    <el-row :gutter="12" class="stat-row">
      <el-col :xs="12" :sm="6">
        <div class="card stat-card">
          <div class="stat-icon" style="background: var(--dc-primary-soft); color: var(--dc-primary)">
            <el-icon :size="22"><DataAnalysis /></el-icon>
          </div>
          <div>
            <div class="stat-num tabular">{{ stat.total }}</div>
            <div class="muted">图号总量</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="card stat-card">
          <div class="stat-icon" style="background: #e8f7ef; color: #2f9e6e">
            <el-icon :size="22"><CirclePlus /></el-icon>
          </div>
          <div>
            <div class="stat-num tabular">{{ stat.today }}</div>
            <div class="muted">今日新增</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="card stat-card">
          <div class="stat-icon" style="background: #fff6e5; color: #d07e2d">
            <el-icon :size="22"><TrendCharts /></el-icon>
          </div>
          <div>
            <div class="stat-num tabular">{{ stat.week }}</div>
            <div class="muted">本周新增</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="card stat-card">
          <div class="stat-icon" style="background: #eef0fd; color: #7b5fc9">
            <el-icon :size="22"><Tickets /></el-icon>
          </div>
          <div>
            <div class="stat-num tabular">{{ stat.ops_total }}</div>
            <div class="muted">操作总数</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表 -->
    <el-row :gutter="12">
      <el-col :xs="24" :lg="16">
        <div class="card chart-card">
          <div class="card-title">近 30 天增长曲线</div>
          <div ref="growthEl" class="chart" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="card chart-card">
          <div class="card-title">各表数据分布</div>
          <div ref="pieEl" class="chart" />
        </div>
      </el-col>
    </el-row>

    <!-- 日历热力图 + 最近数据 -->
    <el-row :gutter="12">
      <el-col :xs="24" :lg="10">
        <CalendarCard />
      </el-col>
      <el-col :xs="24" :lg="14">
        <div class="card recent-card">
          <div class="card-title">最近添加的数据</div>
          <el-empty v-if="!recent.length" description="暂无数据" :image-size="60" />
          <el-scrollbar v-else max-height="300px">
            <div class="recent-list">
              <div v-for="r in recent" :key="r.id" class="recent-item">
                <el-tag size="small" effect="plain" class="recent-table">{{ r.table_name }}</el-tag>
                <span class="recent-drawing">{{ r.data.drawing_no || '—' }}</span>
                <span class="recent-name">{{ r.data.name || '' }}</span>
                <span class="muted recent-meta">
                  {{ r.data.applicant || '未知' }} · {{ r.created_at }}
                </span>
              </div>
            </div>
          </el-scrollbar>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="12">
      <!-- 申请人排行 -->
      <el-col :xs="24" :lg="12">
        <div class="card rank-card">
          <div class="card-title">申请人排行榜</div>
          <el-empty v-if="!ranking.length" description="暂无数据" :image-size="60" />
          <div v-else class="rank-list">
            <div v-for="(r, i) in ranking" :key="r.name" class="rank-item">
              <span class="rank-no tabular" :class="`rank-${i + 1}`">{{ i + 1 }}</span>
              <span class="rank-name">{{ r.name }}</span>
              <div class="rank-bar-wrap">
                <div class="rank-bar" :style="{ width: pct(r.count, maxApplicant) }" />
              </div>
              <span class="rank-count tabular">{{ r.count }}</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 工程项目排行 -->
      <el-col :xs="24" :lg="12">
        <div class="card rank-card">
          <div class="card-title">工程项目排行榜</div>
          <el-empty v-if="!projectRanking.length" description="暂无数据" :image-size="60" />
          <div v-else class="rank-list">
            <div v-for="(r, i) in projectRanking" :key="r.name" class="rank-item">
              <span class="rank-no tabular" :class="`rank-${i + 1}`">{{ i + 1 }}</span>
              <span class="rank-name rank-name-w">{{ r.name }}</span>
              <div class="rank-bar-wrap">
                <div class="rank-bar" :style="{ width: pct(r.count, maxProject) }" />
              </div>
              <span class="rank-count tabular">{{ r.count }}</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { http } from '@/api'
import { useApp } from '@/store'
import CalendarCard from '@/components/CalendarCard.vue'

const store = useApp()
const stat = reactive({ total: 0, today: 0, week: 0, ops_total: 0 })
const byTable = ref([])
const growth = ref([])
const ranking = ref([])
const projectRanking = ref([])
const recent = ref([])

const growthEl = ref()
const pieEl = ref()
let growthChart = null
let pieChart = null

const palette = computed(() => {
  const p = getComputedStyle(document.documentElement).getPropertyValue('--dc-primary').trim()
  return [p || '#3a7bd5', '#50c2a0', '#f2b544', '#e8735a', '#7b5fc9', '#4c7e93', '#8fb339', '#c9506e']
})

function axisStyle() {
  const dark = store.dark
  return {
    axisLabel: { color: dark ? '#8b95a1' : '#5a6470' },
    axisLine: { lineStyle: { color: dark ? '#2a2f36' : '#dfe4e9' } },
    splitLine: { lineStyle: { color: dark ? '#22272e' : '#edf0f3' } }
  }
}

function renderCharts() {
  const axis = axisStyle()
  if (growthEl.value) {
    growthChart = growthChart || echarts.init(growthEl.value)
    growthChart.setOption({
      grid: { left: 36, right: 14, top: 20, bottom: 24 },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: growth.value.map(g => g.date.slice(5)), ...axis },
      yAxis: { type: 'value', minInterval: 1, ...axis },
      series: [{
        type: 'line', smooth: true, symbolSize: 5,
        data: growth.value.map(g => g.count),
        lineStyle: { width: 2.5, color: palette.value[0] },
        itemStyle: { color: palette.value[0] },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: palette.value[0] + '55' },
            { offset: 1, color: palette.value[0] + '05' }
          ])
        }
      }]
    }, true)
  }
  if (pieEl.value) {
    pieChart = pieChart || echarts.init(pieEl.value)
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      legend: {
        bottom: 0, icon: 'circle',
        textStyle: { color: axisStyle().axisLabel.color, fontSize: 12 },
        type: 'scroll'
      },
      series: [{
        type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
        itemStyle: { borderRadius: 6, borderWidth: 2, borderColor: store.dark ? '#13161a' : '#fff' },
        label: { show: false },
        data: byTable.value.map(t => ({ name: t.name, value: t.count }))
      }],
      color: palette.value
    }, true)
  }
}

function onResize() {
  growthChart?.resize()
  pieChart?.resize()
}

async function load() {
  const res = await http.get('/dashboard')
  Object.assign(stat, { total: res.total, today: res.today, week: res.week, ops_total: res.ops_total })
  byTable.value = res.by_table
  growth.value = res.growth
  ranking.value = res.ranking || []
  projectRanking.value = res.project_ranking || []
  recent.value = res.recent
  renderCharts()
}

const maxApplicant = computed(() => ranking.value[0]?.count || 1)
const maxProject = computed(() => projectRanking.value[0]?.count || 1)
function pct(n, max) { return Math.max(6, Math.round((n / max) * 100)) + '%' }

let ro = null

onMounted(async () => {
  await load()
  window.addEventListener('resize', onResize)
  /* 监听图表容器尺寸变化：sidebar 折叠/展开时也能触发 resize */
  ro = new ResizeObserver(onResize)
  if (growthEl.value) ro.observe(growthEl.value)
  if (pieEl.value) ro.observe(pieEl.value)
})

watch(() => [store.theme, store.dark], async () => {
  await new Promise(r => setTimeout(r, 60))
  growthChart?.dispose(); growthChart = null
  pieChart?.dispose(); pieChart = null
  renderCharts()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  ro?.disconnect()
  growthChart?.dispose()
  pieChart?.dispose()
})
</script>

<style scoped>
.dash { overflow-y: auto; }
.stat-row { row-gap: 12px; }
.stat-card {
  display: flex; align-items: center; gap: 12px; padding: 16px;
  height: 100%;
}
.stat-icon {
  width: 46px; height: 46px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center; flex: none;
}
.stat-num { font-size: 26px; font-weight: 700; line-height: 1.1; color: var(--dc-text); }

.el-row { margin-bottom: 12px; }
.el-row:last-child { margin-bottom: 0; }
.chart-card { padding: 14px 16px; }
.card-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.chart { height: 280px; width: 100%; }

.rank-card { padding: 14px 16px; }
.rank-list { display: flex; flex-direction: column; gap: 4px; }
.rank-item { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
.rank-no {
  width: 22px; height: 22px; border-radius: 7px; flex: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
  background: var(--dc-bg-soft); color: var(--dc-text-soft);
}
.rank-1 { background: #f2b544; color: #fff; }
.rank-2 { background: #9aa8b5; color: #fff; }
.rank-3 { background: #c98a5b; color: #fff; }
.rank-name { width: 70px; flex: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rank-name-w { width: 110px; }
.rank-bar-wrap { flex: 1; height: 8px; background: var(--dc-bg-soft); border-radius: 4px; overflow: hidden; }
.rank-bar { height: 100%; background: var(--dc-primary); border-radius: 4px; transition: width .4s; }
.rank-count { width: 36px; text-align: right; color: var(--dc-text-soft); font-size: 12px; }

.recent-card { padding: 14px 16px; }
.recent-list { display: flex; flex-direction: column; }
.recent-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 6px; border-bottom: 1px solid var(--dc-border);
  font-size: 13px;
}
.recent-item:last-child { border-bottom: none; }
.recent-table { flex: none; max-width: 150px; overflow: hidden; }
.recent-drawing { font-weight: 600; color: var(--dc-primary); flex: none; }
.recent-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-meta { margin-left: auto; flex: none; font-size: 12px; }

/* <1200px（lg 断点前）：同行多卡在窄屏改为全宽堆叠，需列间垂直间距防粘连 */
@media (max-width: 1199px) {
  .dash .el-col { margin-bottom: 12px; }
  .dash .el-row { margin-bottom: 0; }
  .dash .el-row:last-child .el-col:last-child { margin-bottom: 0; }
  .stat-row { row-gap: 0; }
}

@media (max-width: 768px) {
  .recent-meta { display: none; }
  .chart { height: 220px; }
}
</style>
