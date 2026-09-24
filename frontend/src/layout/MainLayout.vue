<template>
  <el-container class="layout">
    <!-- 侧边栏（桌面） -->
    <el-aside width="224px" class="aside">
      <div class="brand" @click="aboutOpen = true" title="点击查看系统信息">
        <Logo :size="36" />
        <div class="brand-text">
          <div class="brand-name">DrawCode</div>
          <div class="brand-sub">{{ store.site.subtitle }}</div>
        </div>
      </div>
      <el-menu :default-active="route.path" router class="menu" :collapse="false">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
      <div class="aside-foot muted" v-if="!store.authed">访客模式浏览中</div>
    </el-aside>

    <el-container class="main-wrap">
      <!-- 顶栏 -->
      <el-header class="header" height="56px">
        <div class="header-left">
          <el-icon class="menu-btn" @click="drawer = true"><Expand /></el-icon>
          <span class="header-title">{{ route.meta.title }}</span>
          <el-tag v-if="!store.authed" size="small" type="info" effect="plain">访客</el-tag>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click" @command="store.setTheme">
            <span class="icon-btn" title="切换主题">
              <el-icon><Brush /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="t in THEMES" :key="t.id" :command="t.id">
                  <span class="theme-dot" :style="{ background: t.color }" />
                  {{ t.name }}
                  <el-icon v-if="store.theme === t.id" class="theme-check"><Check /></el-icon>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <span class="icon-btn" :title="store.dark ? '浅色模式' : '暗色模式'" @click="store.setDark(!store.dark)">
            <el-icon><Moon v-if="!store.dark" /><Sunny v-else /></el-icon>
          </span>
          <template v-if="store.authed">
            <el-dropdown trigger="click" @command="onUserCommand">
              <span class="user-btn">
                <el-avatar :size="30" :src="avatarUrl" class="user-avatar">A</el-avatar>
                <span class="user-name">{{ store.user?.username }}</span>
                <el-icon class="user-caret"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="settings"><el-icon><Setting /></el-icon>系统设置</el-dropdown-item>
                  <el-dropdown-item command="password"><el-icon><Lock /></el-icon>修改密码</el-dropdown-item>
                  <el-dropdown-item divided command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-else>
            <el-button size="small" round @click="$router.push('/login')">管理员登录</el-button>
          </template>
        </div>
      </el-header>

      <el-main class="main">
        <router-view v-slot="{ Component }">
          <component :is="Component" ref="pageRef" />
        </router-view>
      </el-main>
    </el-container>

    <!-- 移动端抽屉菜单 -->
    <el-drawer v-model="drawer" direction="ltr" size="240px" :with-header="false" :z-index="2100">
      <div class="drawer-brand" @click="aboutOpen = true">
        <Logo :size="34" />
        <div class="brand-text">
          <div class="brand-name">DrawCode</div>
          <div class="brand-sub">{{ store.site.subtitle }}</div>
        </div>
      </div>
      <el-menu :default-active="route.path" router @select="drawer = false">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <AboutDialog v-model="aboutOpen" />
  </el-container>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useApp, THEMES } from '@/store'
import Logo from '@/components/Logo.vue'
import AboutDialog from '@/components/AboutDialog.vue'

const store = useApp()
const route = useRoute()
const router = useRouter()
const drawer = ref(false)
const aboutOpen = ref(false)
const pageRef = ref(null)

const menus = computed(() =>
  [
    { path: '/', title: '仪表盘', icon: 'Odometer' },
    { path: '/data', title: '图号数据', icon: 'Collection' },
    { path: '/records', title: '操作记录', icon: 'List', admin: true },
    { path: '/logs', title: '系统日志', icon: 'Document', admin: true },
    { path: '/settings', title: '系统设置', icon: 'Setting', admin: true }
  ].filter(m => !m.admin || store.authed)
)

const avatarUrl = computed(() =>
  store.user?.avatar ? `${store.user.avatar}?t=${avatarStamp}` : '')

const avatarStamp = ref(0)
function refreshAvatar() { avatarStamp.value = Date.now() }

async function onUserCommand(cmd) {
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
    await store.logout()
    router.push('/login')
  } else if (cmd === 'settings') {
    router.push('/settings')
  } else if (cmd === 'password') {
    router.push({ path: '/settings', query: { tab: 'security' } })
  }
}

defineExpose({ refreshAvatar })
</script>

<style scoped>
.layout { height: 100vh; }

.aside {
  background: var(--dc-sidebar);
  border-right: 1px solid var(--dc-border);
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}
.brand {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px; cursor: pointer;
  border-bottom: 1px solid var(--dc-border);
  flex: none;
}
.brand-text { min-width: 0; }
.brand-name {
  font-size: 17px; font-weight: 700; line-height: 1.2;
  color: var(--dc-text); letter-spacing: .4px;
}
.brand-sub {
  font-size: 12px; color: var(--dc-text-soft);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-top: 2px;
}
.menu {
  border-right: none; background: transparent;
  padding: 8px;
  flex: 1;
  overflow-y: auto;
}
.menu :deep(.el-menu-item) {
  border-radius: 8px; height: 44px; margin: 2px 0;
  color: var(--dc-text-soft);
}
.menu :deep(.el-menu-item:hover) { background: var(--dc-primary-soft); }
.menu :deep(.el-menu-item.is-active) {
  background: var(--dc-primary); color: #fff;
}
.menu :deep(.el-menu-item.is-active .el-icon) { color: #fff; }
.aside-foot {
  padding: 10px 16px; border-top: 1px solid var(--dc-border);
  font-size: 12px; flex: none;
}

.main-wrap { height: 100vh; overflow: hidden; }
.header {
  background: var(--dc-header);
  border-bottom: 1px solid var(--dc-border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; gap: 10px;
  flex: none;
}
.header-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.header-title { font-size: 15px; font-weight: 600; white-space: nowrap; }
.header-right { display: flex; align-items: center; gap: 8px; }
.icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 34px; height: 34px; border-radius: 8px; cursor: pointer;
  color: var(--dc-text-soft); font-size: 17px;
  transition: background .15s;
}
.icon-btn:hover { background: var(--dc-primary-soft); color: var(--dc-primary); }
.menu-btn { display: none; font-size: 19px; cursor: pointer; color: var(--dc-text); }

.user-btn {
  display: flex; align-items: center; gap: 7px; cursor: pointer;
  padding: 4px 8px; border-radius: 8px; outline: none;
}
.user-btn:hover { background: var(--dc-primary-soft); }
.user-avatar { background: var(--dc-primary); font-weight: 600; }
.user-name { font-size: 13px; color: var(--dc-text); }
.user-caret { font-size: 12px; color: var(--dc-text-soft); }

.main {
  background: var(--dc-bg);
  padding: 0; overflow: hidden;
  display: flex; flex-direction: column;
}
.main :deep(> *) { width: 100%; }

.drawer-brand {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px; cursor: pointer;
  border-bottom: 1px solid var(--dc-border); margin-bottom: 8px;
}

.theme-dot {
  width: 12px; height: 12px; border-radius: 4px;
  display: inline-block; margin-right: 8px;
}
.theme-check { margin-left: 18px; color: var(--dc-primary); }

@media (max-width: 768px) {
  .aside { display: none; }
  .menu-btn { display: inline-flex; }
  .user-name { display: none; }
}
</style>
