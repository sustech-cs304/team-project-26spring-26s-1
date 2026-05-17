<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">
        <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="860" class="px-6 py-8">
                <div class="d-flex flex-column ga-6">
                    <v-sheet rounded="lg" color="surface" elevation="1" class="pa-6">
                        <div class="d-flex flex-column flex-md-row align-md-center justify-space-between ga-6">
                            <div class="d-flex flex-column ga-3">
                                <div class="d-flex align-center ga-2">
                                    <v-chip size="small" variant="tonal" color="primary">Home</v-chip>
                                    <v-chip size="small" variant="tonal">
                                        {{ onboardingCompleted ? '已完成首次引导' : '待完成首次引导' }}
                                    </v-chip>
                                </div>
                                <div>
                                    <div class="text-h5 font-weight-bold mb-2" style="line-height:1.2;">
                                        OpenCrab，把课程学习和校园任务放进同一个工作区
                                    </div>
                                    <div class="text-body-2 text-medium-emphasis"
                                        style="max-width:560px;line-height:1.7;">
                                        从课程问答、测验练习到日程安排，OpenCrab 会把常用学习场景整理成可以直接对话和执行的能力。
                                    </div>
                                </div>
                            </div>

                            <v-sheet rounded="lg" color="primary" class="pa-4 text-white" min-width="220">
                                <div class="text-overline">OpenCrab</div>
                                <div class="text-h6 font-weight-bold mt-1">Study Copilot</div>
                                <div class="text-caption mt-1" style="opacity:0.88;">
                                    为课程学习、任务管理和校园信息查询而设计
                                </div>
                            </v-sheet>
                        </div>

                        <div class="d-flex flex-wrap align-center ga-3 mt-6">
                            <v-btn v-if="!onboardingCompleted" color="primary" size="small" rounded="lg"
                                @click="openOnboarding">
                                开始使用
                            </v-btn>
                            <v-btn v-else color="primary" size="small" rounded="lg" to="/c">
                                前往聊天
                            </v-btn>
                            <v-btn v-if="!onboardingCompleted" variant="tonal" size="small" rounded="lg" to="/c">
                                前往聊天
                            </v-btn>
                            <v-btn variant="text" size="small" rounded="lg" to="/settings">
                                查看设置
                            </v-btn>
                        </div>
                    </v-sheet>

                    <v-row density="comfortable">
                        <v-col cols="12" md="4">
                            <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                <div class="d-flex align-center ga-2 mb-3">
                                    <v-icon size="18" color="primary">mdi-school-outline</v-icon>
                                    <span class="text-subtitle-2 font-weight-bold">课程问答</span>
                                </div>
                                <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                    围绕课件、知识库和日常疑问，把复杂问题拆成更容易理解的学习步骤。
                                </div>
                            </v-card>
                        </v-col>
                        <v-col cols="12" md="4">
                            <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                <div class="d-flex align-center ga-2 mb-3">
                                    <v-icon size="18" color="primary">mdi-checkbox-marked-circle-outline</v-icon>
                                    <span class="text-subtitle-2 font-weight-bold">练习生成</span>
                                </div>
                                <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                    快速生成数学、操作系统、内存管理等测验卡片，适合复习前自测和查漏补缺。
                                </div>
                            </v-card>
                        </v-col>
                        <v-col cols="12" md="4">
                            <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                <div class="d-flex align-center ga-2 mb-3">
                                    <v-icon size="18" color="primary">mdi-calendar-check-outline</v-icon>
                                    <span class="text-subtitle-2 font-weight-bold">任务安排</span>
                                </div>
                                <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                    查询今日安排、整理待办事项，让课程、提醒和对话记录保持在同一个节奏里。
                                </div>
                            </v-card>
                        </v-col>
                    </v-row>
                </div>
            </v-container>
        </v-sheet>
    </v-container>
</template>

<script setup lang="ts">
    import { useOnboardingConfig } from '@/composables/useOnboardingConfig'

    const router = useRouter()
    const { onboardingCompleted } = useOnboardingConfig()

    function openOnboarding () {
        router.push('/onboarding')
    }
</script>
