<template>
  <v-app>
    <router-view />
  </v-app>
</template>

<script lang="ts" setup>
</script>

<style>

  html,
  body,
  #app {
    overscroll-behavior: none;
    overflow: hidden;
    height: 100%;
  }

  .theme-active-list-item {
    background: rgba(var(--v-theme-primary), 0.12) !important;
    color: rgb(var(--v-theme-primary)) !important;
  }

  .theme-active-list-item .v-icon {
    color: rgb(var(--v-theme-primary)) !important;
  }

  .theme-active-list-item .v-list-item-subtitle {
    color: rgba(var(--v-theme-primary), 0.72) !important;
    opacity: 1;
  }
</style>
