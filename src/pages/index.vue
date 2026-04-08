<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">
        <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="860" class="px-6 py-8">
                <div class="d-flex flex-column ga-6">
                    <v-sheet rounded="xl" color="surface" elevation="1" class="pa-6">
                        <div class="d-flex flex-column flex-md-row align-md-center justify-space-between ga-6">
                            <div class="d-flex flex-column ga-3">
                                <div class="d-flex align-center ga-2">
                                    <v-chip size="small" variant="tonal" color="primary">Home</v-chip>
                                    <v-chip size="small" variant="tonal">
                                        {{ isDev ? '开发模式：手动进入引导' : onboardingCompleted ? '已完成首次引导' : '待完成首次引导' }}
                                    </v-chip>
                                </div>
                                <div>
                                    <div class="text-h5 font-weight-bold mb-2" style="line-height:1.2;">
                                        OpenCrab 已准备好，先用 2 分钟完成你的专属配置
                                    </div>
                                    <div class="text-body-2 text-medium-emphasis"
                                        style="max-width:560px;line-height:1.7;">
                                        我们会引导你补全用户画像、校园能力、模型配置和知识库准备。配置完成后，你在聊天页和设置页看到的是同一份数据。
                                    </div>
                                </div>
                            </div>

                            <v-sheet rounded="xl" color="primary" class="pa-4 text-primary" min-width="220">
                                <div class="text-overline">Ready</div>
                                <div class="text-h6 font-weight-bold mt-1">SUSTech-CS</div>
                                <div class="text-caption mt-1" style="opacity:0.88;">
                                    首版引导覆盖 SUSTech 计算机相关学生场景
                                </div>
                            </v-sheet>
                        </div>

                        <div class="d-flex flex-wrap align-center ga-3 mt-6">
                            <v-btn color="primary" size="small" rounded="lg" @click="openOnboarding">
                                {{ onboardingCompleted ? '重新打开引导' : '开始使用' }}
                            </v-btn>
                            <v-btn variant="tonal" size="small" rounded="lg" to="/c">
                                前往聊天
                            </v-btn>
                            <v-btn variant="text" size="small" rounded="lg" to="/settings">
                                查看设置
                            </v-btn>
                        </div>
                    </v-sheet>

                    <v-row dense>
                        <v-col cols="12" md="4">
                            <v-card rounded="xl" variant="tonal" class="pa-4 h-100">
                                <div class="d-flex align-center ga-2 mb-3">
                                    <v-icon size="18" color="primary">mdi-account-edit-outline</v-icon>
                                    <span class="text-subtitle-2 font-weight-bold">用户画像</span>
                                </div>
                                <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                    一句话介绍、年龄层和专业会帮助 agent 用更合适的上下文与你交流。
                                </div>
                            </v-card>
                        </v-col>
                        <v-col cols="12" md="4">
                            <v-card rounded="xl" variant="tonal" class="pa-4 h-100">
                                <div class="d-flex align-center ga-2 mb-3">
                                    <v-icon size="18" color="primary">mdi-brain</v-icon>
                                    <span class="text-subtitle-2 font-weight-bold">模型与校园能力</span>
                                </div>
                                <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                    引导会把模型配置和 SUSTech 账号配置一起准备好，后续可在其他页面直接复用。
                                </div>
                            </v-card>
                        </v-col>
                        <v-col cols="12" md="4">
                            <v-card rounded="xl" variant="tonal" class="pa-4 h-100">
                                <div class="d-flex align-center ga-2 mb-3">
                                    <v-icon size="18" color="primary">mdi-database-arrow-down-outline</v-icon>
                                    <span class="text-subtitle-2 font-weight-bold">知识库准备</span>
                                </div>
                                <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                    按学校和专业准备推荐知识包，首版默认支持 SUSTech-CS。
                                </div>
                            </v-card>
                        </v-col>
                    </v-row>

                    <v-card v-if="isDev" rounded="xl" variant="tonal" class="pa-4">
                        <div class="d-flex flex-wrap align-center ga-3">
                            <span class="text-caption text-medium-emphasis">开发调试：默认 BaseURL 使用云端</span>
                            <v-switch v-model="defaultBaseURLIsCloud" hide-details density="compact"
                                @update:model-value="onToggle" />
                            <code class="text-caption">{{ currentBaseURL }}</code>
                        </div>
                    </v-card>
                </div>
            </v-container>
        </v-sheet>
    </v-container>
</template>

<script setup lang="ts">
    import { ref } from 'vue'
    import { baseURL, getDefaultBaseURLIsCloud, setDefaultBaseURLIsCloud } from '@/utils/http'
    import { useOnboardingConfig } from '@/composables/useOnboardingConfig'

    const router = useRouter()
    const { onboardingCompleted } = useOnboardingConfig()

    // TODO: 上线前移除开发模式相关代码
    // const isDev = import.meta.env.DEV
    const isDev = true
    const defaultBaseURLIsCloud = ref(getDefaultBaseURLIsCloud())
    const currentBaseURL = ref(baseURL)

    function onToggle (value: boolean | null) {
        setDefaultBaseURLIsCloud(Boolean(value))
        currentBaseURL.value = baseURL
    }

    function openOnboarding () {
        router.push('/onboarding')
    }
</script>
