<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" class="dc-logo">
    <defs>
      <linearGradient id="dc-logo-g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#3a7bd5" />
        <stop offset="1" stop-color="#50c2a0" />
      </linearGradient>
    </defs>
    <rect x="2" y="2" width="44" height="44" rx="11" fill="url(#dc-logo-g)" />
    <path d="M9 10h8M9 10v8M39 38h-8M39 38v-8" stroke="rgba(255,255,255,.75)"
          stroke-width="2.4" stroke-linecap="round" fill="none" />
    <text x="24" y="32.5" font-size="21" font-weight="700" fill="#fff"
          text-anchor="middle" class="dc-logo-text">图</text>
  </svg>
</template>

<script setup>
defineProps({ size: { type: [Number, String], default: 34 } })
</script>

<style scoped>
.dc-logo { flex: none; }
.dc-logo-text {
  font-family: "PingFang SC", "HarmonyOS Sans SC", "MiSans", "Microsoft YaHei", sans-serif;
}
</style>
