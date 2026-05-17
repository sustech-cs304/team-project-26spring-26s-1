<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0 onboarding-shell" @click="handleScreenClick">
        <v-sheet color="transparent" class="flex-grow-1 overflow-hidden min-height-0">
            <v-container max-width="860" class="px-6 py-3 h-100">
                <div class="d-flex flex-column ga-2 h-100 min-height-0">
                    <v-sheet rounded="lg" color="surface" elevation="1" class="pa-3">
                        <div>
                            <div>
                                <div class="d-flex align-center ga-2 mb-2">
                                    <v-chip size="x-small" variant="tonal" color="primary">Onboarding</v-chip>
                                    <v-chip size="x-small" variant="tonal">{{ currentStep + 1 }}/{{ steps.length
                                    }}</v-chip>
                                </div>
                                <div class="text-subtitle-1 font-weight-bold mb-1">
                                    {{ currentMeta.title }}
                                </div>
                                <div class="text-caption text-medium-emphasis" style="max-width:560px;">
                                    {{ currentMeta.description }}
                                </div>
                            </div>
                        </div>

                        <div class="d-flex flex-wrap ga-2 mt-2">
                            <v-chip v-for="(step, index) in steps" :key="step.key" size="x-small"
                                :color="index === currentStep ? 'primary' : undefined"
                                :variant="index === currentStep ? 'flat' : 'tonal'">
                                {{ index + 1 }}. {{ step.shortLabel }}
                            </v-chip>
                        </div>
                    </v-sheet>

                    <v-window v-model="currentStep" class="flex-grow-1 min-height-0 onboarding-step-window"
                        :touch="false">
                        <v-window-item v-for="(step, index) in steps" :key="step.key" :value="index"
                            class="h-100 min-height-0">
                            <v-card rounded="lg" color="surface" elevation="1" class="pa-3 h-100 overflow-y-auto">
                                <template v-if="step.key === 'welcome'">
                                    <div class="d-flex flex-column ga-3">
                                        <div class="text-subtitle-1 font-weight-bold">欢迎使用 OpenCrab</div>
                                        <v-row density="comfortable">
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">了解你</div>
                                                    <div class="text-body-2 text-medium-emphasis">一句话介绍、身份与专业会帮助 agent
                                                        更快进入合适的语境。</div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">准备能力</div>
                                                    <div class="text-body-2 text-medium-emphasis">配置 SUSTech
                                                        账号和模型连接，后续聊天和设置页都可直接复用。</div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">下载知识包</div>
                                                    <div class="text-body-2 text-medium-emphasis">首版会为 SUSTech-CS
                                                        推荐知识库，便于后续问答和课程支持。</div>
                                                </v-card>
                                            </v-col>
                                        </v-row>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'profile'">
                                    <div class="d-flex flex-column ga-4">
                                        <div>
                                            <div class="text-subtitle-1 font-weight-bold mb-2">用一句话介绍你自己</div>
                                            <div class="text-caption text-medium-emphasis">例如：我是南科大计科大二学生，最近在补操作系统和算法。
                                            </div>
                                        </div>
                                        <v-textarea v-model="userProfile.oneLineProfile" variant="solo-filled" flat
                                            density="compact" rounded="lg" rows="3" counter="120" maxlength="120"
                                            placeholder="输入一句能让 agent 快速了解你的描述" hide-details="auto" />
                                        <div v-if="userProfile.oneLineProfile.trim().length === 0"
                                            class="text-caption text-medium-emphasis">
                                            这一项是必填的，后续 agent 会参考这里的描述理解你的背景。
                                        </div>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'identity'">
                                    <div class="d-flex flex-column ga-3">
                                        <div>
                                            <div class="text-subtitle-1 font-weight-bold mb-2">学校、年龄层与专业</div>
                                        </div>
                                        <v-row density="compact">
                                            <v-col cols="12" md="4">
                                                <div class="text-caption text-medium-emphasis mb-1">身份</div>
                                                <v-select v-model="userProfile.identity" density="compact"
                                                    variant="solo-filled" flat rounded="lg" :items="identityOptions"
                                                    item-title="label" item-value="value" hide-details />
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <div class="text-caption text-medium-emphasis mb-1">学校</div>
                                                <v-select v-model="userProfile.school" density="compact"
                                                    variant="solo-filled" flat rounded="lg" :items="schoolOptions"
                                                    item-title="label" item-value="value" hide-details />
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <div class="text-caption text-medium-emphasis mb-1">年龄层</div>
                                                <v-select v-model="userProfile.ageBand" density="compact"
                                                    variant="solo-filled" flat rounded="lg" :items="ageBandOptions"
                                                    item-title="label" item-value="value" hide-details />
                                            </v-col>
                                        </v-row>
                                        <div>
                                            <div class="text-caption text-medium-emphasis mb-1">专业</div>
                                            <v-select v-model="userProfile.major" density="compact"
                                                variant="solo-filled" flat rounded="lg" :items="majorOptions"
                                                item-title="label" item-value="value" hide-details />
                                        </div>
                                    </div>
                                </template>
                                <template v-else-if="step.key === 'campus'">
                                    <div class="d-flex flex-column ga-3">
                                        <div>
                                            <div>
                                                <div class="text-subtitle-1 font-weight-bold mb-2">SUSTech 教务配置</div>
                                                <div class="text-caption text-medium-emphasis">可跳过，后续可在设置页继续配置。</div>
                                            </div>
                                        </div>

                                        <v-row density="compact">
                                            <v-col cols="12" md="6">
                                                <div class="text-caption text-medium-emphasis mb-1">学号</div>
                                                <v-text-field v-model="campusAuth.studentId" density="compact"
                                                    variant="solo-filled" flat rounded="lg" placeholder="例如 12110001"
                                                    hide-details />
                                            </v-col>
                                            <v-col cols="12" md="6">
                                                <div class="text-caption text-medium-emphasis mb-1">密码</div>
                                                <v-text-field v-model="campusAuth.password" density="compact"
                                                    variant="solo-filled" flat rounded="lg"
                                                    :type="showCampusPassword ? 'text' : 'password'" hide-details>
                                                    <template #append-inner>
                                                        <v-btn size="x-small" variant="text" icon
                                                            @click="showCampusPassword = !showCampusPassword">
                                                            <v-icon size="16">{{ showCampusPassword ? 'mdi-eye-off' :
                                                                'mdi-eye' }}</v-icon>
                                                        </v-btn>
                                                    </template>
                                                </v-text-field>
                                            </v-col>
                                        </v-row>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'model'">
                                    <div class="d-flex flex-column ga-2">
                                        <div class="d-flex align-center justify-space-between ga-3">
                                            <div class="text-subtitle-1 font-weight-bold">模型连接</div>
                                            <v-btn size="x-small" variant="tonal" rounded="lg"
                                                :prepend-icon="showSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                                @click="showSecrets = !showSecrets">
                                                {{ showSecrets ? '隐藏密钥' : '显示密钥' }}
                                            </v-btn>
                                        </div>

                                        <v-sheet color="transparent" class="d-flex flex-column ga-2">
                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">主模型</div>
                                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.agent.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="Base URL" placeholder="Base url (不需要写/v1)"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.agent.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="API Key" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="4" class="py-1">
                                                        <v-combobox v-model="serviceConfig.agent.model"
                                                            :items="modelOptions.agent" density="compact"
                                                            variant="solo-filled" flat rounded="lg" label="Model"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="3" class="py-1">
                                                        <v-text-field v-model.number="serviceConfig.agent.maxTokenCount"
                                                            type="number" density="compact" variant="solo-filled" flat
                                                            rounded="lg" label="Max Tokens" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="5" class="py-1">
                                                        <div class="d-flex align-center justify-end ga-2 h-100">
                                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                                prepend-icon="mdi-format-list-bulleted"
                                                                :loading="modelLoading.agentList"
                                                                :disabled="modelLoading.agentTest"
                                                                @click="fetchProviderModels('agent')">
                                                                拉取模型
                                                            </v-btn>
                                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                                prepend-icon="mdi-connection"
                                                                :loading="modelLoading.agentTest"
                                                                :disabled="modelLoading.agentList"
                                                                @click="testProviderConnection('agent')">
                                                                测试连接
                                                            </v-btn>
                                                        </div>
                                                    </v-col>
                                                </v-row>
                                            </div>

                                            <v-divider class="my-1" />

                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">副模型</div>
                                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.utility.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="Base URL" placeholder="Base url (不需要写/v1)"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.utility.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="API Key" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="4" class="py-1">
                                                        <v-combobox v-model="serviceConfig.utility.model"
                                                            :items="modelOptions.utility" density="compact"
                                                            variant="solo-filled" flat rounded="lg" label="Model"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="3" class="py-1">
                                                        <v-text-field
                                                            v-model.number="serviceConfig.utility.maxTokenCount"
                                                            type="number" density="compact" variant="solo-filled" flat
                                                            rounded="lg" label="Max Tokens" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="5" class="py-1">
                                                        <div class="d-flex align-center justify-end ga-2 h-100">
                                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                                prepend-icon="mdi-format-list-bulleted"
                                                                :loading="modelLoading.utilityList"
                                                                :disabled="modelLoading.utilityTest"
                                                                @click="fetchProviderModels('utility')">
                                                                拉取模型
                                                            </v-btn>
                                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                                prepend-icon="mdi-connection"
                                                                :loading="modelLoading.utilityTest"
                                                                :disabled="modelLoading.utilityList"
                                                                @click="testProviderConnection('utility')">
                                                                测试连接
                                                            </v-btn>
                                                        </div>
                                                    </v-col>
                                                </v-row>
                                            </div>
                                        </v-sheet>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'retrieval'">
                                    <div class="d-flex flex-column ga-2">
                                        <div class="d-flex align-center justify-space-between ga-3">
                                            <div class="text-subtitle-1 font-weight-bold">知识检索</div>
                                            <v-btn size="x-small" variant="tonal" rounded="lg"
                                                :prepend-icon="showSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                                @click="showSecrets = !showSecrets">
                                                {{ showSecrets ? '隐藏密钥' : '显示密钥' }}
                                            </v-btn>
                                        </div>

                                        <v-sheet color="transparent" class="d-flex flex-column ga-2">
                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">Embed</div>
                                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.embed.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="Base URL" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.embed.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="API Key" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="7" class="py-1">
                                                        <v-text-field v-model="serviceConfig.embed.model"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="Model" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="5" class="py-1">
                                                        <v-text-field v-model.number="serviceConfig.embed.dims"
                                                            type="number" density="compact" variant="solo-filled" flat
                                                            rounded="lg" label="Dims" hide-details="auto" />
                                                    </v-col>
                                                </v-row>
                                            </div>

                                            <v-divider class="my-1" />

                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">Rerank</div>
                                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.rerank.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="Base URL" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.rerank.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="API Key" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.rerank.model"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="Model" hide-details="auto" />
                                                    </v-col>
                                                </v-row>
                                            </div>
                                        </v-sheet>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'services'">
                                    <div class="d-flex flex-column ga-2">
                                        <div class="d-flex align-center justify-space-between ga-3">
                                            <div class="text-subtitle-1 font-weight-bold">语音与文档解析</div>
                                            <v-btn size="x-small" variant="tonal" rounded="lg"
                                                :prepend-icon="showSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                                @click="showSecrets = !showSecrets">
                                                {{ showSecrets ? '隐藏密钥' : '显示密钥' }}
                                            </v-btn>
                                        </div>

                                        <v-sheet color="transparent" class="d-flex flex-column ga-2">
                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">ASR</div>
                                                    <v-chip size="x-small" variant="tonal">Qwen</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.asr.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="Base URL" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.asr.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="API Key" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                </v-row>
                                            </div>

                                            <v-divider class="my-1" />

                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">MinerU</div>
                                                    <v-chip size="x-small" variant="tonal">File</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.mineru.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="Base URL" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.mineru.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="API Key" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                </v-row>
                                            </div>
                                        </v-sheet>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'knowledge'">
                                    <div class="d-flex flex-column ga-4">
                                        <div class="d-flex flex-wrap align-center justify-space-between ga-3">
                                            <div>
                                                <div class="text-subtitle-1 font-weight-bold mb-2">知识库下载</div>
                                            </div>
                                            <v-chip size="small" variant="tonal" color="primary">{{ knowledgePack.packId
                                            }}</v-chip>
                                        </div>

                                        <v-card rounded="lg" variant="tonal" class="pa-4">
                                            <div class="d-flex align-center justify-space-between ga-3 mb-3">
                                                <div>
                                                    <div class="text-subtitle-2 font-weight-bold">SUSTech-CS Starter
                                                        Pack</div>
                                                    <div class="text-caption text-medium-emphasis">课程知识、院校上下文与计算机相关基础资料
                                                    </div>
                                                </div>
                                                <v-btn color="primary" size="small" rounded="lg"
                                                    :loading="isKnowledgeSubmitting"
                                                    :disabled="knowledgeSync.status === 'running' || !hasCompleteServiceConfig"
                                                    @click="triggerKnowledgeDownload">
                                                    {{ knowledgeButtonLabel }}
                                                </v-btn>
                                            </div>
                                            <v-progress-linear :model-value="knowledgeProgress" color="primary" rounded
                                                height="8" />
                                            <div class="d-flex align-center justify-space-between mt-3">
                                                <span class="text-caption text-medium-emphasis">{{ knowledgeStatusText
                                                }}</span>
                                                <span class="text-caption text-medium-emphasis">{{
                                                    Math.round(knowledgeProgress) }}%</span>
                                            </div>
                                            <div v-if="knowledgeMetaLine"
                                                class="text-caption text-medium-emphasis mt-2">
                                                {{ knowledgeMetaLine }}
                                            </div>
                                            <div v-if="knowledgeSummary" class="text-caption text-medium-emphasis mt-1">
                                                {{ knowledgeSummary }}
                                            </div>
                                            <div v-if="knowledgeSync.status === 'failed' && knowledgeSync.error"
                                                class="text-caption text-error mt-2">
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
                                                    <div class="text-body-2 text-medium-emphasis"
                                                        style="line-height:1.7;">
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
                                                    <div class="text-body-2 text-medium-emphasis"
                                                        style="line-height:1.7;">
                                                        统一查看课程和个人安排，后续也可以接入校园与任务相关事件。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="6">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="d-flex align-center ga-2 mb-3">
                                                        <v-icon size="18"
                                                            color="primary">mdi-format-list-checkbox</v-icon>
                                                        <span class="text-subtitle-2 font-weight-bold">Tasks</span>
                                                    </div>
                                                    <div class="text-body-2 text-medium-emphasis"
                                                        style="line-height:1.7;">
                                                        把高频操作沉淀成任务流，后续可以复用环境变量、脚本与定时触发能力。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="6">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="d-flex align-center ga-2 mb-3">
                                                        <v-icon size="18" color="primary">mdi-connection</v-icon>
                                                        <span class="text-subtitle-2 font-weight-bold">Store /
                                                            Capabilities</span>
                                                    </div>
                                                    <div class="text-body-2 text-medium-emphasis"
                                                        style="line-height:1.7;">
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

        <v-sheet color="surface" class="px-6 py-3">
            <v-container max-width="860" class="pa-0 d-flex align-center justify-space-between ga-3 flex-wrap">
                <v-btn variant="text" size="small" rounded="lg" :disabled="currentStep === 0 || isCompleting"
                    @click="goPrevious">
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
    import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
    import { patchCas } from '@/api/cas'
    import { patchConfig, type AppConfig, type DeepPartial } from '@/api/config'
    import { defaultRagSyncState, getApiErrorMessage, getRagSyncStatus, triggerRagSync, type RagSyncState } from '@/api/rag'
    import { useOnboardingConfig } from '@/composables/useOnboardingConfig'
    import { requestOpenAIModels } from '@/composables/useOpenAIModelTools'

    type StepKey = 'welcome' | 'profile' | 'identity' | 'campus' | 'model' | 'retrieval' | 'services' | 'knowledge' | 'finish'
    type ModelEndpointRole = 'agent' | 'utility'

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
        { key: 'model', shortLabel: '模型', title: '配置模型连接', description: '主模型和副模型会支撑对话与轻量任务。' },
        { key: 'retrieval', shortLabel: '检索', title: '配置知识检索', description: 'Embed 和 Rerank 会用于知识库更新与资料召回。' },
        { key: 'services', shortLabel: '服务', title: '配置语音与文档解析', description: 'ASR 和 MinerU 会用于语音输入、文件解析和后续工作流。' },
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
    const router = useRouter()
    const route = useRoute()
    const {
        userProfile,
        campusAuth,
        serviceConfig,
        knowledgePack,
        saveKnowledgePack,
        saveUserProfile,
        saveCampusAuth,
        saveServiceConfig,
        markOnboardingCompleted,
    } = useOnboardingConfig()

    const currentStep = ref(0)
    const celebrationCanvas = ref<HTMLCanvasElement | null>(null)
    const showSecrets = ref(false)
    const showCampusPassword = ref(false)
    const isCompleting = ref(false)
    const snackbar = ref({ show: false, text: '', color: 'success' })
    const knowledgeSync = ref<RagSyncState>(defaultRagSyncState())
    const isKnowledgeSubmitting = ref(false)
    const modelOptions = reactive<Record<ModelEndpointRole, string[]>>({
        agent: [],
        utility: [],
    })
    const modelLoading = reactive({
        agentList: false,
        agentTest: false,
        utilityList: false,
        utilityTest: false,
    })

    let knowledgePollTimer: ReturnType<typeof setInterval> | null = null
    let redirectTimer: ReturnType<typeof setTimeout> | null = null
    let celebrationTimers: ReturnType<typeof setTimeout>[] = []
    let confettiInstance: ReturnType<typeof confetti.create> | null = null

    const currentMeta = computed<StepMeta>(() => steps[currentStep.value] ?? steps[0]!)
    const hasAnyCampusAuthValue = computed(() =>
        !!campusAuth.studentId.trim() || !!campusAuth.password.trim()
    )
    const hasCompleteCampusAuth = computed(() =>
        !!campusAuth.studentId.trim() && !!campusAuth.password.trim()
    )
    const positiveNumber = (value: number) => Number.isFinite(value) && value > 0
    const hasCompleteModelConfig = computed(() =>
        !!serviceConfig.agent.baseUrl.trim()
        && !!serviceConfig.agent.apiKey.trim()
        && !!serviceConfig.agent.model.trim()
        && positiveNumber(serviceConfig.agent.maxTokenCount)
        && !!serviceConfig.utility.baseUrl.trim()
        && !!serviceConfig.utility.apiKey.trim()
        && !!serviceConfig.utility.model.trim()
        && positiveNumber(serviceConfig.utility.maxTokenCount)
    )
    const hasCompleteRetrievalConfig = computed(() =>
        !!serviceConfig.embed.baseUrl.trim()
        && !!serviceConfig.embed.apiKey.trim()
        && !!serviceConfig.embed.model.trim()
        && positiveNumber(serviceConfig.embed.dims)
        && !!serviceConfig.rerank.baseUrl.trim()
        && !!serviceConfig.rerank.apiKey.trim()
        && !!serviceConfig.rerank.model.trim()
    )
    const hasCompleteServiceToolsConfig = computed(() =>
        !!serviceConfig.asr.baseUrl.trim()
        && !!serviceConfig.asr.apiKey.trim()
        && !!serviceConfig.mineru.baseUrl.trim()
        && !!serviceConfig.mineru.apiKey.trim()
    )
    const hasCompleteServiceConfig = computed(() =>
        hasCompleteModelConfig.value
        && hasCompleteRetrievalConfig.value
        && hasCompleteServiceToolsConfig.value
    )

    const canProceed = computed(() => {
        switch (steps[currentStep.value]?.key) {
            case 'profile':
                return userProfile.oneLineProfile.trim().length > 0
            case 'campus':
                return !hasAnyCampusAuthValue.value || hasCompleteCampusAuth.value
            case 'model':
                return hasCompleteModelConfig.value
            case 'retrieval':
                return hasCompleteRetrievalConfig.value
            case 'services':
                return hasCompleteServiceToolsConfig.value
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

    const footerHint = computed(() => {
        if (currentMeta.value.key === 'model' && !hasCompleteModelConfig.value) {
            return '需要填完整主模型和副模型'
        }
        if (currentMeta.value.key === 'retrieval' && !hasCompleteRetrievalConfig.value) {
            return '需要填完整 Embed 和 Rerank'
        }
        if (currentMeta.value.key === 'services' && !hasCompleteServiceToolsConfig.value) {
            return '需要填完整 ASR 和 MinerU'
        }
        if (currentMeta.value.key === 'knowledge' && !hasCompleteServiceConfig.value) {
            return '需要先完成配置'
        }
        if (currentMeta.value.key === 'knowledge' && knowledgePack.status !== 'ready') {
            return '需要先完成知识库更新'
        }
        return ''
    })

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

    function getModelEndpointLabel (role: ModelEndpointRole) {
        return role === 'agent' ? '主模型' : '副模型'
    }

    async function requestProviderModels (role: ModelEndpointRole) {
        const target = serviceConfig[role]
        return requestOpenAIModels(target, getModelEndpointLabel(role))
    }

    async function fetchProviderModels (role: ModelEndpointRole) {
        const loadingKey = role === 'agent' ? 'agentList' : 'utilityList'
        modelLoading[loadingKey] = true

        try {
            const models = await requestProviderModels(role)
            modelOptions[role] = models
            if (!models.length) {
                showNotice(`${getModelEndpointLabel(role)}连接成功，但没有返回模型列表`, 'warning')
                return
            }
            showNotice(`已拉取 ${models.length} 个模型`)
        } catch (error) {
            showNotice(error instanceof Error ? error.message : '拉取模型失败', 'error')
        } finally {
            modelLoading[loadingKey] = false
        }
    }

    async function testProviderConnection (role: ModelEndpointRole) {
        const loadingKey = role === 'agent' ? 'agentTest' : 'utilityTest'
        modelLoading[loadingKey] = true

        try {
            await requestProviderModels(role)
            showNotice(`${getModelEndpointLabel(role)}连接正常`)
        } catch (error) {
            showNotice(error instanceof Error ? error.message : '连接测试失败', 'error')
        } finally {
            modelLoading[loadingKey] = false
        }
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
        saveCampusAuth({
            ...campusAuth,
            enabled: hasCompleteCampusAuth.value,
        })
        saveServiceConfig({ ...serviceConfig })
        saveKnowledgePack({ ...knowledgePack })
        void syncCurrentStepToBackend(steps[currentStep.value]?.key)
    }

    async function syncCurrentStepToBackend (stepKey?: StepKey) {
        if (!stepKey) return

        const syncJobs: Promise<unknown>[] = []

        if ((stepKey === 'campus' || stepKey === 'finish') && hasCompleteCampusAuth.value) {
            syncJobs.push(syncCampusAuthToBackend())
        }

        if (
            ['model', 'retrieval', 'services', 'knowledge', 'finish'].includes(stepKey)
            && hasCompleteServiceConfig.value
        ) {
            syncJobs.push(syncServiceConfigToBackend())
        }

        if (!syncJobs.length) return

        await Promise.all(syncJobs)
    }

    async function syncCampusAuthToBackend () {
        try {
            await patchCas({
                id: campusAuth.studentId.trim(),
                password: campusAuth.password,
            })
        } catch (error) {
            showNotice(getApiErrorMessage(error, 'CAS 配置同步失败，本地草稿已保留'), 'warning')
        }
    }

    function buildServiceConfigPatch (): DeepPartial<AppConfig> {
        return {
            api: {
                agent: {
                    type: 'OpenAI',
                    base_url: serviceConfig.agent.baseUrl.trim(),
                    api_key: serviceConfig.agent.apiKey.trim(),
                    model: serviceConfig.agent.model.trim(),
                    max_token_count: serviceConfig.agent.maxTokenCount,
                },
                utility: {
                    type: 'OpenAI',
                    base_url: serviceConfig.utility.baseUrl.trim(),
                    api_key: serviceConfig.utility.apiKey.trim(),
                    model: serviceConfig.utility.model.trim(),
                    max_token_count: serviceConfig.utility.maxTokenCount,
                },
                embed: {
                    type: 'OpenAI',
                    base_url: serviceConfig.embed.baseUrl.trim(),
                    api_key: serviceConfig.embed.apiKey.trim(),
                    model: serviceConfig.embed.model.trim(),
                    dims: serviceConfig.embed.dims,
                },
                rerank: {
                    type: 'OpenAI',
                    base_url: serviceConfig.rerank.baseUrl.trim(),
                    api_key: serviceConfig.rerank.apiKey.trim(),
                    model: serviceConfig.rerank.model.trim(),
                },
                asr: {
                    type: 'Qwen',
                    base_url: serviceConfig.asr.baseUrl.trim(),
                    api_key: serviceConfig.asr.apiKey.trim(),
                },
            },
            file: {
                upload_path: './uploads',
                rag_path: './rag',
                mineru: {
                    base_url: serviceConfig.mineru.baseUrl.trim(),
                    api_key: serviceConfig.mineru.apiKey.trim(),
                },
            },
        }
    }

    async function syncServiceConfigToBackend (options?: { silent?: boolean }) {
        try {
            await patchConfig(buildServiceConfigPatch())
            return true
        } catch (error) {
            if (!options?.silent) {
                showNotice(getApiErrorMessage(error, '配置同步失败，本地草稿已保留'), 'warning')
            }
            return false
        }
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
        if (!hasCompleteServiceConfig.value) {
            showNotice('请先填完整配置，再更新知识库', 'warning')
            return
        }

        isKnowledgeSubmitting.value = true

        try {
            const synced = await syncServiceConfigToBackend({ silent: true })
            if (!synced) {
                showNotice('配置还没有同步成功，暂时不能更新知识库', 'warning')
                return
            }

            saveKnowledgePack({
                packId: 'sustech-cs',
                status: 'downloading',
                lastTriggeredAt: new Date().toISOString(),
            })

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

    .onboarding-step-window :deep(.v-window__container),
    .onboarding-step-window :deep(.v-window-item) {
        height: 100%;
        min-height: 0;
    }

    .onboarding-shell :deep(.v-field) {
        font-size: 0.875rem;
    }
</style>
