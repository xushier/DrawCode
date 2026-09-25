import { defineStore } from 'pinia'
import { http } from './api'

export const THEMES = [
  { id: 'lan', name: '碧海听澜', color: '#3a7bd5' },
  { id: 'cui', name: '翠峦春晓', color: '#3e8e68' },
  { id: 'zi', name: '暮山凝紫', color: '#7b5fc9' },
  { id: 'jin', name: '落日熔金', color: '#d07e2d' },
  { id: 'tao', name: '桃夭灼灼', color: '#c9506e' },
  { id: 'yun', name: '云山雾隐', color: '#4c7e93' }
]

export const useApp = defineStore('app', {
  state: () => ({
    ready: false,
    authed: false,
    guestMode: false,
    user: null,
    site: {
      name: '智能图号系统', subtitle: '智能装备研究院图号系统', org: '智能装备研究院',
      version: '', changelog: [], github: '', author: ''
    },
    // 主题：本地记忆（非法值回退默认主题）
    theme: THEMES.some(t => t.id === localStorage.getItem('dc-theme'))
      ? localStorage.getItem('dc-theme') : 'lan',
    dark: localStorage.getItem('dc-dark') === '1'
  }),
  getters: {
    canManage: s => s.authed,
    themeInfo: s => THEMES.find(t => t.id === s.theme) || THEMES[0]
  },
  actions: {
    applyTheme() {
      document.documentElement.dataset.theme = this.theme
      document.documentElement.classList.toggle('dark', this.dark)
      localStorage.setItem('dc-theme', this.theme)
      localStorage.setItem('dc-dark', this.dark ? '1' : '0')
      // 防御外部环境（部分内嵌浏览器/插件）覆写 data-theme，导致主题变量失效
      if (!this._themeGuard) {
        this._themeGuard = new MutationObserver(() => {
          if (document.documentElement.dataset.theme !== this.theme)
            document.documentElement.dataset.theme = this.theme
        })
        this._themeGuard.observe(document.documentElement, {
          attributes: true, attributeFilter: ['data-theme']
        })
      }
    },
    setTheme(id) {
      this.theme = id
      this.applyTheme()
    },
    setDark(v) {
      this.dark = !!v
      this.applyTheme()
    },
    async init() {
      if (this.ready) return
      try {
        const res = await http.get('/auth/status', { headers: { 'X-Silent': 1 } })
        this.authed = res.authed
        this.guestMode = res.guest_mode
        this.user = res.user
        if (res.site) this.site = res.site
      } catch (e) {
        /* 后端未启动时保持默认 */
      }
      this.ready = true
      this.applyTheme()
      document.title = `${this.site.name} · DrawCode`
    },
    async login(username, password) {
      const res = await http.post('/auth/login', { username, password })
      localStorage.setItem('dc-token', res.token)
      this.authed = true
      this.user = res.user
      await this.init()
    },
    async logout() {
      try { await http.post('/auth/logout') } catch (e) { /* ignore */ }
      localStorage.removeItem('dc-token')
      this.authed = false
      this.user = null
    }
  }
})
