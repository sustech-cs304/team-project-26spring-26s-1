<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0 onboarding-shell" @click="handleScreenClick">
        <v-sheet color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="860" class="px-6 py-6">
                <div class="d-flex flex-column ga-4">
                    <v-sheet rounded="xl" color="surface" elevation="1" class="pa-6">
                        <div>
                            <div>
                                <div class="d-flex align-center ga-2 mb-3">
                                    <v-chip size="small" variant="tonal" color="primary">Onboarding</v-chip>
                                    <v-chip size="small" variant="tonal">{{ currentStep + 1 }}/{{ steps.length }}</v-chip>
                                </div>
                                <div class="text-h5 font-weight-bold mb-2" style="line-height:1.2;">
                                    {{ currentMeta.title }}
                                </div>
                                <div class="text-body-2 text-medium-emphasis" style="max-width:560px;line-height:1.7;">
                                    {{ currentMeta.description }}
                                </div>
                            </div>
                        </div>

                        <div class="d-flex flex-wrap ga-2 mt-5">
                            <v-chip v-for="(step, index) in steps" :key="step.key" size="small"
                                :color="index === currentStep ? 'primary' : undefined"
                                :variant="index === currentStep ? 'flat' : 'tonal'">
                                {{ index + 1 }}. {{ step.shortLabel }}
                            </v-chip>
                        </div>
                    </v-sheet>

                    <v-window v-model="currentStep" class="flex-grow-1" :touch="false">
                        <v-window-item v-for="(step, index) in steps" :key="step.key" :value="index">
                            <v-card rounded="xl" color="surface" elevation="1" class="pa-6">
                                <template v-if="step.key === 'welcome'">
                                    <div class="d-flex flex-column ga-4">
                                        <div class="text-subtitle-1 font-weight-bold">欢迎使用 OpenCrab</div>
                                        <v-row density="comfortable">
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">了解你</div>
                                                    <div class="text-body-2 text-medium-emphasis">一句话介绍、身份与专业会帮助 agent 更快进入合适的语境。</div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">准备能力</div>
                                                    <div class="text-body-2 text-medium-emphasis">配置 SUSTech 账号和模型连接，后续聊天和设置页都可直接复用。</div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">下载知识包</div>
                                                    <div class="text-body-2 text-medium-emphasis">首版会为 SUSTech-CS 推荐知识库，便于后续问答和课程支持。</div>
                                                </v-card>
                                            </v-col>
                                        </v-row>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'profile'">
                                    <div class="d-flex flex-column ga-4">
                                        <div>
                                            <div class="text-subtitle-1 font-weight-bold mb-2">用一句话介绍你自己</div>
                                            <div class="text-caption text-medium-emphasis">例如：我是南科大计科大二学生，最近在补操作系统和算法。</div>
                                        </div>
                                        <v-textarea v-model="userProfile.oneLineProfile" variant="outlined" density="compact" rounded="lg"
                                            rows="4" counter="120" maxlength="120" placeholder="输入一句能让 agent 快速了解你的描述" />
                                        <div v-if="userProfile.oneLineProfile.trim().length === 0" class="text-caption text-medium-emphasis">
                                            这一项是必填的，后续 agent 会参考这里的描述理解你的背景。
                                        </div>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'identity'">
                                    <div class="d-flex flex-column ga-5">
                                        <div>
                                            <div class="text-subtitle-1 font-weight-bold mb-2">学校、年龄层与专业</div>
                                        </div>
                                        <v-row density="comfortable">
                                            <v-col cols="12" md="4">
                                                <div class="text-caption text-medium-emphasis mb-2">身份</div>
                                                <v-select v-model="userProfile.identity" density="compact" variant="outlined" rounded="lg"
                                                    :items="identityOptions" item-title="label" item-value="value" hide-details />
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <div class="text-caption text-medium-emphasis mb-2">学校</div>
                                                <v-select v-model="userProfile.school" density="compact" variant="outlined" rounded="lg"
                                                    :items="schoolOptions" item-title="label" item-value="value" hide-details />
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <div class="text-caption text-medium-emphasis mb-2">年龄层</div>
                                                <v-select v-model="userProfile.ageBand" density="compact" variant="outlined" rounded="lg"
                                                    :items="ageBandOptions" item-title="label" item-value="value" hide-details />
                                            </v-col>
                                        </v-row>
                                        <div>
                                            <div class="text-caption text-medium-emphasis mb-2">专业</div>
                                            <v-select v-model="userProfile.major" density="compact" variant="outlined" rounded="lg"
                                                :items="majorOptions" item-title="label" item-value="value" hide-details />
                                        </div>
                                    </div>
                                </template>
                                <template v-else-if="step.key === 'campus'">
                                    <div class="d-flex flex-column ga-4">
                                        <div class="d-flex flex-wrap align-center justify-space-between ga-3">
                                            <div>
                                                <div class="text-subtitle-1 font-weight-bold mb-2">SUSTech 教务配置</div>
                                            </div>
                                            <v-switch v-model="campusAuth.enabled" color="primary" density="compact" hide-details inset>
                                                <template #label>
                                                    <span class="text-body-2">启用账号配置</span>
                                                </template>
                                            </v-switch>
                                        </div>

                                        <div v-if="campusAuth.enabled">
                                            <v-row density="comfortable">
                                                <v-col cols="12" md="6">
                                                    <div class="text-caption text-medium-emphasis mb-2">学号</div>
                                                    <v-text-field v-model="campusAuth.studentId" density="compact" variant="outlined" rounded="lg"
                                                        placeholder="例如 12110001" hide-details />
                                                </v-col>
                                                <v-col cols="12" md="6">
                                                    <div class="text-caption text-medium-emphasis mb-2">密码</div>
                                                    <v-text-field v-model="campusAuth.password" density="compact" variant="outlined" rounded="lg"
                                                        :type="showCampusPassword ? 'text' : 'password'" hide-details>
                                                        <template #append-inner>
                                                            <v-btn size="x-small" variant="text" icon @click="showCampusPassword = !showCampusPassword">
                                                                <v-icon size="16">{{ showCampusPassword ? 'mdi-eye-off' : 'mdi-eye' }}</v-icon>
                                                            </v-btn>
                                                        </template>
                                                    </v-text-field>
                                                </v-col>
                                            </v-row>
                                        </div>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'model'">
                                    <div class="d-flex flex-column ga-4">
                                        <div>
                                            <div class="text-subtitle-1 font-weight-bold mb-2">模型配置</div>
                                        </div>
                                        <v-row density="comfortable">
                                            <v-col cols="12" md="4">
                                                <div class="text-caption text-medium-emphasis mb-2">Provider</div>
                                                <v-select v-model="modelEndpoint.provider" density="compact" variant="outlined" rounded="lg"
                                                    :items="providerOptions" hide-details />
                                            </v-col>
                                            <v-col cols="12" md="8">
                                                <div class="text-caption text-medium-emphasis mb-2">Base URL</div>
                                                <v-text-field v-model="modelEndpoint.baseUrl" density="compact" variant="outlined" rounded="lg"
                                                    placeholder="https://api.openai.com/v1" hide-details />
                                            </v-col>
                                            <v-col cols="12" md="6">
                                                <div class="text-caption text-medium-emphasis mb-2">API Key</div>
                                                <v-text-field v-model="modelEndpoint.apiKey" density="compact" variant="outlined" rounded="lg"
                                                    :type="showApiKey ? 'text' : 'password'" hide-details>
                                                    <template #append-inner>
                                                        <v-btn size="x-small" variant="text" icon @click="showApiKey = !showApiKey">
                                                            <v-icon size="16">{{ showApiKey ? 'mdi-eye-off' : 'mdi-eye' }}</v-icon>
                                                        </v-btn>
                                                    </template>
                                                </v-text-field>
                                            </v-col>
                                            <v-col cols="12" md="6">
                                                <div class="text-caption text-medium-emphasis mb-2">Model Name</div>
                                                <v-text-field v-model="modelEndpoint.modelName" density="compact" variant="outlined" rounded="lg"
                                                    placeholder="gpt-4.1-mini / deepseek-chat / qwen" hide-details />
                                            </v-col>
                                        </v-row>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'knowledge'">
                                    <div class="d-flex flex-column ga-4">
                                        <div class="d-flex flex-wrap align-center justify-space-between ga-3">
                                            <div>
                                                <div class="text-subtitle-1 font-weight-bold mb-2">知识库下载</div>
                                            </div>
                                            <v-chip size="small" variant="tonal" color="primary">{{ knowledgePack.packId }}</v-chip>
                                        </div>

                                        <v-card rounded="lg" variant="tonal" class="pa-4">
                                            <div class="d-flex align-center justify-space-between ga-3 mb-3">
                                                <div>
                                                    <div class="text-subtitle-2 font-weight-bold">SUSTech-CS Starter Pack</div>
                                                    <div class="text-caption text-medium-emphasis">课程知识、院校上下文与计算机相关基础资料</div>
                                                </div>
                                                <v-btn color="primary" size="small" rounded="lg"
                                                    :loading="isKnowledgeSubmitting" :disabled="knowledgeSync.status === 'running'"
                                                    @click="triggerKnowledgeDownload">
                                                    {{ knowledgeButtonLabel }}
                                                </v-btn>
                                            </div>
                                            <v-progress-linear :model-value="knowledgeProgress" color="primary" rounded height="8" />
                                            <div class="d-flex align-center justify-space-between mt-3">
                                                <span class="text-caption text-medium-emphasis">{{ knowledgeStatusText }}</span>
                                                <span class="text-caption text-medium-emphasis">{{ Math.round(knowledgeProgress) }}%</span>
                                            </div>
                                            <div v-if="knowledgeMetaLine" class="text-caption text-medium-emphasis mt-2">
                                                {{ knowledgeMetaLine }}
                                            </div>
                                            <div v-if="knowledgeSummary" class="text-caption text-medium-emphasis mt-1">
                                                {{ knowledgeSummary }}
                                            </div>
                                            <div v-if="knowledgeSync.status === 'failed' && knowledgeSync.error" class="text-caption text-error mt-2">
                                                {{ knowledgeSync.error }}
                                            </div>
                                        </v-card>

                                    </div>
                                </template>
                                <template v-else-if="step.key === 'finish'">
                                    <div class="d-flex flex-column ga-5">
                                        <div class="d-flex flex-wrap align-start justify-space-between ga-3">
                                            <div>
                                                <div class="text-subtitle-1 font-weight-bold mb-2">准备完成，认识一下主要功能</div>
                                            </div>
                                            <v-chip size="small" variant="tonal" color="success">Ready to go</v-chip>
                                        </div>

                                        <v-row density="comfortable">
                                            <v-col cols="12" md="6">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="d-flex align-center ga-2 mb-3">
                                                        <v-icon size="18" color="primary">mdi-message-outline</v-icon>
                                                        <span class="text-subtitle-2 font-weight-bold">Chat</span>
                                                    </div>
                                                    <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                                        以对话为中心的主工作区，支持消息输入、文件上传和后续 agent 交互。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="6">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="d-flex align-center ga-2 mb-3">
                                                        <v-icon size="18" color="primary">mdi-calendar</v-icon>
                                                        <span class="text-subtitle-2 font-weight-bold">Calendar</span>
                                                    </div>
                                                    <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                                        统一查看课程和个人安排，后续也可以接入校园与任务相关事件。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="6">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="d-flex align-center ga-2 mb-3">
                                                        <v-icon size="18" color="primary">mdi-format-list-checkbox</v-icon>
                                                        <span class="text-subtitle-2 font-weight-bold">Tasks</span>
                                                    </div>
                                                    <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                                        把高频操作沉淀成任务流，后续可以复用环境变量、脚本与定时触发能力。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="6">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="d-flex align-center ga-2 mb-3">
                                                        <v-icon size="18" color="primary">mdi-connection</v-icon>
                                                        <span class="text-subtitle-2 font-weight-bold">Store / Capabilities</span>
                                                    </div>
                                                    <div class="text-body-2 text-medium-emphasis" style="line-height:1.7;">
                                                        管理扩展能力、插件和工具入口，后续可逐步扩展校园与学习场景。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                        </v-row>
                                    </div>
                                </template>
                            </v-card>
                        </v-window-item>
                    </v-window>
                </div>
            </v-container>
        </v-sheet>

        <v-sheet color="surface" class="px-6 py-4">
            <v-container max-width="860" class="pa-0 d-flex align-center justify-space-between ga-3 flex-wrap">
                <v-btn variant="text" size="small" rounded="lg" :disabled="currentStep === 0 || isCompleting" @click="goPrevious">
                    上一步
                </v-btn>
                <div class="d-flex align-center ga-3">
                    <span v-if="footerHint" class="text-caption text-medium-emphasis">{{ footerHint }}</span>
                    <v-btn v-if="currentStep < steps.length - 1" color="primary" size="small" rounded="lg"
                        :disabled="!canProceed || isCompleting" @click="goNext">
                        下一步
                    </v-btn>
                    <v-btn v-else color="primary" size="small" rounded="lg" :loading="isCompleting"
                        :disabled="isCompleting" @click="finishOnboarding">
                        完成引导
                    </v-btn>
                </div>
            </v-container>
        </v-sheet>

        <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="2800" location="top">
            {{ snackbar.text }}
        </v-snackbar>

        <canvas ref="celebrationCanvas" class="celebration-canvas" aria-hidden="true" />
    </v-container>
</template>

<script setup lang="ts">
    import confetti from 'canvas-confetti'
    import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
    import { defaultRagSyncState, getApiErrorMessage, getRagSyncStatus, triggerRagSync, type RagSyncState } from '@/api/rag'
    import { useOnboardingConfig } from '@/composables/useOnboardingConfig'

    type StepKey = 'welcome' | 'profile' | 'identity' | 'campus' | 'model' | 'knowledge' | 'finish'

    interface StepMeta {
        key: StepKey
        shortLabel: string
        title: string
        description: string
    }

    const steps: StepMeta[] = [
        { key: 'welcome', shortLabel: '欢迎', title: '欢迎来到 OpenCrab', description: '花一点时间完成初始化，我们就可以开始了。' },
        { key: 'profile', shortLabel: '画像', title: '先让 agent 认识你', description: '用一句话介绍自己，方便后续交流更贴近你的背景。' },
        { key: 'identity', shortLabel: '身份', title: '确认学校、年龄层与专业', description: '补充你的基本信息，帮助我们提供更合适的内容。' },
        { key: 'campus', shortLabel: '校园', title: '配置 SUSTech 教务账号', description: '如果你需要校园相关能力，可以在这里完成设置。' },
        { key: 'model', shortLabel: '模型', title: '配置你的模型连接', description: '填好模型信息后，就可以正常开始使用对话能力。' },
        { key: 'knowledge', shortLabel: '知识库', title: '准备知识包', description: '先把知识内容准备好，后续使用会更顺畅。' },
        { key: 'finish', shortLabel: '完成', title: '一切准备就绪', description: '看看 OpenCrab 会怎样帮你更轻松地学习、安排任务和获得支持。' },
    ]

    const identityOptions = [{ label: '大学生', value: 'student' }]
    const schoolOptions = [{ label: 'SUSTech', value: 'SUSTech' }]
    const ageBandOptions = [
        { label: '本科生', value: 'undergraduate' },
        { label: '研究生', value: 'graduate' },
    ]
    const majorOptions = [{ label: 'Computer Science', value: 'cs' }]
    const providerOptions = ['OpenAI', 'DeepSeek', 'Local Ollama']
    const router = useRouter()
    const route = useRoute()
    const {
        userProfile,
        campusAuth,
        modelEndpoint,
        knowledgePack,
        saveKnowledgePack,
        saveUserProfile,
        saveCampusAuth,
        saveModelEndpoint,
        markOnboardingCompleted,
    } = useOnboardingConfig()

    const currentStep = ref(0)
    const celebrationCanvas = ref<HTMLCanvasElement | null>(null)
    const showApiKey = ref(false)
    const showCampusPassword = ref(false)
    const isCompleting = ref(false)
    const snackbar = ref({ show: false, text: '', color: 'success' })
    const knowledgeSync = ref<RagSyncState>(defaultRagSyncState())
    const isKnowledgeSubmitting = ref(false)

    let knowledgePollTimer: ReturnType<typeof setInterval> | null = null
    let redirectTimer: ReturnType<typeof setTimeout> | null = null
    let celebrationTimers: ReturnType<typeof setTimeout>[] = []
    let confettiInstance: ReturnType<typeof confetti.create> | null = null

    const currentMeta = computed<StepMeta>(() => steps[currentStep.value] ?? steps[0]!)

    const canProceed = computed(() => {
        switch (steps[currentStep.value]?.key) {
            case 'profile':
                return userProfile.oneLineProfile.trim().length > 0
            case 'campus':
                return !campusAuth.enabled || (!!campusAuth.studentId.trim() && !!campusAuth.password.trim())
            case 'model':
                return !!modelEndpoint.baseUrl.trim() && !!modelEndpoint.apiKey.trim() && !!modelEndpoint.modelName.trim()
            case 'knowledge':
                return knowledgePack.status === 'ready'
            default:
                return true
        }
    })

    const knowledgeProgress = computed(() => {
        if (knowledgePack.status === 'ready') return 100
        return Math.max(0, Math.min(100, Math.round(knowledgeSync.value.progress || 0)))
    })

    const knowledgeButtonLabel = computed(() => {
        if (knowledgeSync.value.status === 'running') return '同步中'
        if (knowledgePack.status === 'ready') return '重新下载'
        return '开始下载'
    })

    const knowledgeStatusText = computed(() => {
        if (knowledgeSync.value.status === 'running') {
            return knowledgeSync.value.message || '正在同步知识库'
        }
        if (knowledgeSync.value.status === 'failed') {
            return '知识库同步失败，请检查配置后重试'
        }
        if (knowledgePack.status === 'ready') {
            const versionText = knowledgeSync.value.version ? `（版本 ${knowledgeSync.value.version}）` : ''
            return `知识库已准备完成${versionText}`
        }
        if (knowledgePack.status === 'failed') return '知识包准备失败，请重试'
        return '等待开始下载'
    })

    const footerHint = computed(() => currentMeta.value.key === 'knowledge' && knowledgePack.status !== 'ready'
        ? '需要先完成知识包准备'
        : '')

    const knowledgeSummary = computed(() => {
        if (knowledgeSync.value.status !== 'success' && knowledgePack.status !== 'ready') return ''

        const stats = [
            `新增 ${knowledgeSync.value.embedded_added}`,
            `覆盖 ${knowledgeSync.value.embedded_overwritten}`,
            `失败 ${knowledgeSync.value.embedded_failed}`,
        ]

        return stats.join(' · ')
    })

    const knowledgeMetaLine = computed(() => {
        if (knowledgeSync.value.status === 'failed') return ''

        const parts = [
            knowledgeSync.value.knowledge_base_id ? `知识库 ${knowledgeSync.value.knowledge_base_id}` : '',
            knowledgeSync.value.version ? `版本 ${knowledgeSync.value.version}` : '',
        ].filter(Boolean)

        return parts.join(' · ')
    })

    function showNotice (text: string, color: 'success' | 'warning' | 'error' = 'success') {
        snackbar.value = { show: true, text, color }
    }

    function goNext () {
        if (!canProceed.value) {
            showNotice('请先完成当前步骤', 'warning')
            return
        }
        persistCurrentStep()
        currentStep.value = Math.min(currentStep.value + 1, steps.length - 1)
    }

    function goPrevious () {
        currentStep.value = Math.max(currentStep.value - 1, 0)
    }

    function persistCurrentStep () {
        saveUserProfile({ ...userProfile })
        saveCampusAuth({ ...campusAuth })
        saveModelEndpoint({ ...modelEndpoint })
        saveKnowledgePack({ ...knowledgePack })
    }

    function stopKnowledgePolling () {
        if (knowledgePollTimer) {
            clearInterval(knowledgePollTimer)
            knowledgePollTimer = null
        }
    }

    function applyKnowledgeSyncState (state: RagSyncState) {
        knowledgeSync.value = state

        if (state.status === 'running') {
            saveKnowledgePack({
                packId: 'sustech-cs',
                status: 'downloading',
                lastTriggeredAt: knowledgePack.lastTriggeredAt ?? new Date().toISOString(),
            })
            return
        }

        if (state.status === 'success') {
            saveKnowledgePack({
                packId: 'sustech-cs',
                status: 'ready',
                lastTriggeredAt: knowledgePack.lastTriggeredAt ?? new Date().toISOString(),
            })
            return
        }

        if (state.status === 'failed') {
            saveKnowledgePack({
                packId: 'sustech-cs',
                status: 'failed',
                lastTriggeredAt: knowledgePack.lastTriggeredAt ?? new Date().toISOString(),
            })
            return
        }

        if (knowledgePack.status !== 'ready') {
            saveKnowledgePack({
                packId: 'sustech-cs',
                status: 'idle',
            })
        }
    }

    async function pollKnowledgeStatus (options?: { silent?: boolean }) {
        try {
            const state = await getRagSyncStatus()
            const previousStatus = knowledgeSync.value.status
            applyKnowledgeSyncState(state)

            if (state.status === 'running') {
                if (!knowledgePollTimer) {
                    knowledgePollTimer = setInterval(() => {
                        void pollKnowledgeStatus({ silent: true })
                    }, 1000)
                }
                return
            }

            stopKnowledgePolling()

            if (!options?.silent && state.status === 'success') {
                showNotice('知识库更新成功')
            }

            if (previousStatus === 'running' && state.status === 'success') {
                showNotice('知识库更新成功')
            }

            if (previousStatus === 'running' && state.status === 'failed') {
                showNotice(state.error || '知识库同步失败', 'error')
            }
        } catch (error) {
            stopKnowledgePolling()
            applyKnowledgeSyncState({
                ...knowledgeSync.value,
                status: 'failed',
                stage: 'failed',
                error: getApiErrorMessage(error, '知识库同步失败'),
            })
            if (!options?.silent) {
                showNotice(knowledgeSync.value.error || '知识库同步失败', 'error')
            }
        }
    }

    async function triggerKnowledgeDownload () {
        if (isKnowledgeSubmitting.value || knowledgeSync.value.status === 'running') return

        isKnowledgeSubmitting.value = true
        saveKnowledgePack({
            packId: 'sustech-cs',
            status: 'downloading',
            lastTriggeredAt: new Date().toISOString(),
        })

        try {
            const state = await triggerRagSync()
            applyKnowledgeSyncState(state)

            if (state.status === 'running') {
                stopKnowledgePolling()
                knowledgePollTimer = setInterval(() => {
                    void pollKnowledgeStatus({ silent: true })
                }, 1000)
            } else if (state.status === 'success') {
                showNotice('知识库更新成功')
            } else if (state.status === 'failed') {
                showNotice(state.error || '知识库同步失败', 'error')
            }
        } catch (error) {
            const message = getApiErrorMessage(error, '知识库同步失败')
            applyKnowledgeSyncState({
                ...knowledgeSync.value,
                status: 'failed',
                stage: 'failed',
                error: message,
            })
            showNotice(message, 'error')
        } finally {
            isKnowledgeSubmitting.value = false
        }
    }

    function getConfettiInstance () {
        if (!celebrationCanvas.value) return null
        confettiInstance ??= confetti.create(celebrationCanvas.value, {
            resize: true,
            useWorker: true,
        })
        return confettiInstance
    }

    function replayCelebration () {
        if (currentMeta.value.key !== 'finish') return

        const shoot = getConfettiInstance()
        if (!shoot) return

        if (celebrationTimers.length > 0) {
            celebrationTimers.forEach(clearTimeout)
            celebrationTimers = []
        }

        const colors = ['#66b3ff', '#8ce99a', '#ffd166', '#ff8c69', '#c299ff', '#59e3c0', '#ffb347', '#ff6cab']
        const defaults = {
            colors,
            origin: { y: 0.9 },
            zIndex: 4000,
            disableForReducedMotion: true,
        }

        const fire = (particleRatio: number, options: Record<string, unknown>) => {
            shoot({
                ...defaults,
                ...options,
                particleCount: Math.floor(140 * particleRatio),
            })
        }

        const realisticBurst = (originX: number) => {
            fire(0.25, { spread: 26, startVelocity: 55, origin: { x: originX, y: 0.9 } })
            fire(0.2, { spread: 60, origin: { x: originX, y: 0.9 } })
            fire(0.2, { spread: 100, decay: 0.91, scalar: 0.8, origin: { x: originX, y: 0.9 } })
            fire(0.15, { spread: 120, startVelocity: 25, decay: 0.92, scalar: 1.15, origin: { x: originX, y: 0.9 } })
            fire(0.1, { spread: 120, startVelocity: 45, origin: { x: originX, y: 0.9 } })
        }

        realisticBurst(0.24)
        realisticBurst(0.76)

        celebrationTimers = [
            setTimeout(() => realisticBurst(0.34), 220),
            setTimeout(() => realisticBurst(0.66), 360),
            setTimeout(() => {
                fire(0.18, { spread: 90, startVelocity: 30, decay: 0.92, scalar: 0.95, origin: { x: 0.5, y: 0.86 } })
            }, 520),
        ]
    }

    function handleScreenClick () {
        if (currentMeta.value.key === 'finish') {
            replayCelebration()
        }
    }

    function finishOnboarding () {
        if (isCompleting.value) return
        persistCurrentStep()
        isCompleting.value = true
        markOnboardingCompleted()
        showNotice('引导完成，正在进入首页')

        const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
        redirectTimer = setTimeout(() => {
            router.push(redirect)
        }, 1400)
    }

    watch(currentStep, (step) => {
        if (steps[step]?.key === 'finish') {
            replayCelebration()
        }

        if (steps[step]?.key === 'knowledge' && knowledgeSync.value.status === 'idle') {
            void pollKnowledgeStatus({ silent: true })
        }
    })

    onMounted(() => {
        void pollKnowledgeStatus({ silent: true })
    })

    onBeforeUnmount(() => {
        stopKnowledgePolling()
        if (redirectTimer) clearTimeout(redirectTimer)
        if (celebrationTimers.length > 0) {
            celebrationTimers.forEach(clearTimeout)
        }
        confetti.reset()
    })
</script>

<style scoped>
    .celebration-canvas {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 4000;
    }

    .onboarding-shell {
        position: relative;
        overflow: hidden;
    }
</style>
