<template>
  <img src="/favicon.svg" :width="size" :height="size" alt="Logo" class="dc-logo" />
</template>

<script setup>
defineProps({ size: { type: [Number, String], default: 34 } })
</script>

<style scoped>
.dc-logo { flex: none; display: block; }
</style>
