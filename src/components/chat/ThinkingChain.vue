<template>
    <v-sheet color="transparent">
        <!-- 推理开关按钮 -->
        <v-btn class="text-body-medium opacity-70 pa-1" height="32" @click="expanded = !expanded" variant="text">
            <Transition name="tc-ripple" mode="out-in">
                <span v-if="isActive" :key="latestTitle" class="tc-title d-flex align-center" style="gap: 6px;">
                    <v-progress-circular indeterminate color="primary" size="16" width="2" />
                    {{ latestTitle }}
                </span>
                <span v-else :key="'done'" class="tc-title">
                    <v-icon>mdi-chevron-down</v-icon>
                    已完成推理 · {{ steps.length }} 个步骤
                </span>
            </Transition>
        </v-btn>

        <!-- 推理步骤列表（展开时才显示） -->
        <v-expand-transition>
            <v-sheet v-if="expanded" color="transparent">
                <div class="steps-timeline">
                    <v-list density="compact" class="pa-0 bg-transparent" nav>
                        <v-list-item v-for="step in steps" :key="step.id" class="step-row px-1" density="compact"
                            prepend-gap="6" min-height="24" :ripple="false" style="align-items: flex-start;">
                            <template #prepend>
                                <v-icon size="13" :color="stepIconColor(step.status)" style="margin-top: 3px;">{{
                                    stepIcon(step.type)
                                    }}</v-icon>
                            </template>

                            <div class="step-content font-weight-light text-body-2"
                                :class="step.status === 'running' ? 'text-primary font-weight-medium' : 'text-medium-emphasis'">
                                {{ step.title }}{{ step.content ? `: ${step.content}` : '' }}
                                <span class="text-caption text-medium-emphasis" style="margin-left: 6px;">{{ step.created_at
                                    }}</span>
                            </div>
                        </v-list-item>
                    </v-list>
                </div>
            </v-sheet>
        </v-expand-transition>
    </v-sheet>
</template>

<script setup lang="ts">
    import type { ThoughtStep, StepStatus, StepType } from '@/types/conversation.ts'

    const props = defineProps<{
        steps: ThoughtStep[]
        isActive?: boolean
    }>()

    const expanded = ref(false)

    // 当前最新步骤标题（用于触发行轮播）
    const latestTitle = computed(() => props.steps[props.steps.length - 1]?.title ?? '')

    const stepIcon = (type: StepType) => ({
        search: 'mdi-magnify',
        code: 'mdi-code-braces',
        tool: 'mdi-wrench-outline',
        read: 'mdi-file-eye-outline',
        think: 'mdi-thought-bubble-outline',
        api: 'mdi-api',
        tool_call: 'mdi-wrench-outline',
        tool_response: 'mdi-wrench-outline',
        thought_step: 'mdi-thought-bubble-outline',
    }[type] ?? 'mdi-circle-small')

    const stepIconColor = (status: StepStatus) =>
        status === 'running' ? 'primary' : status === 'error' ? 'error' : 'medium-emphasis'
</script>

<style scoped>

    .step-content {
        white-space: pre-wrap;
        word-break: break-word;
        line-height: 1.5;
    }

    /* 推理步骤左侧竖线 */
    .steps-timeline {
        border-left: 2px solid rgba(var(--v-theme-on-surface), 0.12);
        margin-left: 12px;
        padding-left: 6px;
    }

    .tc-ripple-enter-active {
        animation: tc-wave-in 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    .tc-ripple-leave-active {
        animation: tc-wave-out 0.25s cubic-bezier(0.55, 0, 0.45, 1) both;
    }

    @keyframes tc-wave-in {
        0% {
            opacity: 0;
            transform: translateY(8px) scaleY(0.82);
            filter: blur(3px);
        }

        60% {
            opacity: 1;
            transform: translateY(-2px) scaleY(1.04);
            filter: blur(0);
        }

        100% {
            opacity: 1;
            transform: translateY(0) scaleY(1);
            filter: blur(0);
        }
    }

    @keyframes tc-wave-out {
        0% {
            opacity: 1;
            transform: translateY(0) scaleY(1);
            filter: blur(0);
        }

        100% {
            opacity: 0;
            transform: translateY(-6px) scaleY(0.86);
            filter: blur(2px);
        }
    }
</style>
