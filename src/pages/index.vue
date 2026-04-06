<template>
    This is home page.
    <v-btn to="/auth">Route to Auth</v-btn>
    <v-btn to="/quiz-playground" class="ml-2">Quiz Playground</v-btn>

    <div class="mt-4 d-flex align-center ga-3">
        <span>defaultBaseURL 使用云端</span>
        <v-switch v-model="defaultBaseURLIsCloud" hide-details @update:model-value="onToggle" />
        当前 API BaseURL：{{ currentBaseURL }}
    </div>

</template>

<script setup lang="ts">
    import { ref } from 'vue'
    import { baseURL, getDefaultBaseURLIsCloud, setDefaultBaseURLIsCloud } from '@/utils/http'

    const defaultBaseURLIsCloud = ref(getDefaultBaseURLIsCloud())
    const currentBaseURL = ref(baseURL)

    function onToggle (value: boolean | null) {
        setDefaultBaseURLIsCloud(Boolean(value))
        currentBaseURL.value = baseURL
    }
</script>