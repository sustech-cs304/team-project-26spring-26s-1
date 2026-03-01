<template>
    <div class="d-flex flex-column h-100 pa-4">
        <div class="text-h6 mb-4">对话 #{{ conversationId }}</div>
        <!-- 对话内容区域 -->
    </div>
</template>

<script setup lang="ts">
    const route = useRoute()
    const conversationId = computed(() => route.params.conversationId)
</script>