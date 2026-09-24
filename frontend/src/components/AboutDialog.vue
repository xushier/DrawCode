<template>
  <el-dialog v-model="show" title="关于系统" width="460px" append-to-body destroy-on-close>
    <div class="about">
      <div class="about-head">
        <Logo :size="54" />
        <div class="about-names">
          <div class="about-name">{{ store.site.name }}</div>
          <div class="about-sub">{{ store.site.subtitle }} · DrawCode</div>
        </div>
      </div>
      <div class="about-grid">
        <div class="about-item"><span class="muted">软件名称</span><b>DrawCode</b></div>
        <div class="about-item"><span class="muted">当前版本</span><b>v{{ store.site.version }}</b></div>
        <div class="about-item"><span class="muted">作者</span><b>{{ store.site.author }}</b></div>
        <div class="about-item">
          <span class="muted">GitHub</span>
          <el-link type="primary" :href="store.site.github" target="_blank" style="font-size: 13px">
            {{ store.site.github }}
          </el-link>
        </div>
      </div>
      <el-divider style="margin: 12px 0" />
      <div class="about-changelog muted">更新内容</div>
      <el-timeline style="padding: 8px 4px 0">
        <el-timeline-item
          v-for="log in store.site.changelog" :key="log.version"
          :timestamp="`v${log.version} · ${log.date}`" placement="top"
          :color="'var(--dc-primary)'">
          <ul class="about-log">
            <li v-for="item in log.items" :key="item">{{ item }}</li>
          </ul>
        </el-timeline-item>
      </el-timeline>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { useApp } from '@/store'
import Logo from './Logo.vue'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])
const store = useApp()
const show = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v)
})
</script>

<style scoped>
.about-head { display: flex; align-items: center; gap: 14px; }
.about-name { font-size: 17px; font-weight: 700; color: var(--dc-text); }
.about-sub { font-size: 13px; color: var(--dc-text-soft); margin-top: 3px; }
.about-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; margin-top: 16px; }
.about-item { display: flex; flex-direction: column; gap: 3px; font-size: 13px; }
.about-item b { color: var(--dc-text); font-weight: 600; }
.about-changelog { font-size: 13px; margin-bottom: 2px; }
.about-log { margin: 0; padding: 0 0 0 4px; list-style: none; }
.about-log li {
  font-size: 13px;
  color: var(--dc-text);
  line-height: 1.7;
  padding-left: 12px;
  position: relative;
}
.about-log li::before {
  content: "";
  position: absolute; left: 0; top: 9px;
  width: 4px; height: 4px; border-radius: 50%;
  background: var(--dc-primary);
}
</style>
