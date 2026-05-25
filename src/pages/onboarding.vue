<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0 onboarding-shell" @click="handleScreenClick">
        <v-sheet color="transparent" class="flex-grow-1 overflow-hidden min-height-0">
            <v-container max-width="860" class="px-6 py-3 h-100">
                <div class="d-flex flex-column ga-2 h-100 min-height-0">
                    <v-sheet rounded="lg" color="surface" elevation="1" class="pa-3">
                        <div>
                            <div>
                                <div class="d-flex align-center ga-2 mb-2">
                                    <v-chip size="x-small" variant="tonal" color="primary">初次设置</v-chip>
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
                                        <div class="text-body-2 text-medium-emphasis">
                                            接下来只需要完成几项必要设置。你可以先填最常用的配置，其他内容之后都能在设置页修改。
                                        </div>
                                        <v-row density="comfortable">
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">让助手了解你</div>
                                                    <div class="text-body-2 text-medium-emphasis">
                                                        简单说说你的学校、专业和最近关注的内容，OpenCrab 会用更贴近你的方式回答。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">连接常用服务</div>
                                                    <div class="text-body-2 text-medium-emphasis">
                                                        填入模型和校园账号后，就能开始聊天、查看日程和处理课程资料。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                            <v-col cols="12" md="4">
                                                <v-card rounded="lg" variant="tonal" class="pa-4 h-100">
                                                    <div class="text-subtitle-2 font-weight-bold mb-2">准备课程知识</div>
                                                    <div class="text-body-2 text-medium-emphasis">
                                                        下载推荐知识包后，OpenCrab 可以更好地回答和 SUSTech-CS 相关的问题。
                                                    </div>
                                                </v-card>
                                            </v-col>
                                        </v-row>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'profile'">
                                    <div class="d-flex flex-column ga-4">
                                        <div>
                                            <div class="text-subtitle-1 font-weight-bold mb-2">先简单介绍一下你</div>
                                            <div class="text-caption text-medium-emphasis">不用正式，像和同学自我介绍一样就好。例如：我是南科大计科大二学生，最近在补操作系统和算法。
                                            </div>
                                        </div>
                                        <v-textarea v-model="userProfile.oneLineProfile" variant="solo-filled" flat
                                            density="compact" rounded="lg" rows="3" counter="120" maxlength="120"
                                            placeholder="例如：我是南科大计科大二学生，最近在补操作系统和算法。" hide-details="auto" />
                                        <div v-if="userProfile.oneLineProfile.trim().length === 0"
                                            class="text-caption text-medium-emphasis">
                                            这一项会帮助 OpenCrab 理解你的学习背景。
                                        </div>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'identity'">
                                    <div class="d-flex flex-column ga-3">
                                        <div>
                                            <div class="text-subtitle-1 font-weight-bold mb-2">确认你的学习身份</div>
                                            <div class="text-caption text-medium-emphasis">
                                                这些信息会用于默认推荐和校园场景判断，不需要填写复杂资料。
                                            </div>
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
                                                <div class="text-subtitle-1 font-weight-bold mb-2">连接校园账号</div>
                                                <div class="text-caption text-medium-emphasis">
                                                    如果你希望 OpenCrab 读取课程和日程，请填写 SUSTech 账号。暂时不需要也可以留空，之后在设置页再补。
                                                </div>
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
                                            <div>
                                                <div class="text-subtitle-1 font-weight-bold">连接 AI 模型</div>
                                                <div class="text-caption text-medium-emphasis">
                                                    这里决定 OpenCrab 用哪个模型回答问题。通常填入你常用模型服务的地址、密钥和模型名即可。
                                                </div>
                                            </div>
                                            <v-btn size="x-small" variant="tonal" rounded="lg"
                                                :prepend-icon="showSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                                @click="showSecrets = !showSecrets">
                                                {{ showSecrets ? '隐藏密钥' : '显示密钥' }}
                                            </v-btn>
                                        </div>

                                        <v-sheet color="transparent" class="d-flex flex-column ga-2">
                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">日常聊天模型</div>
                                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.agent.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="服务地址" placeholder="例如 https://api.example.com"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.agent.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="访问密钥" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="4" class="py-1">
                                                        <v-combobox v-model="serviceConfig.agent.model"
                                                            :items="modelOptions.agent" density="compact"
                                                            variant="solo-filled" flat rounded="lg" label="模型名称"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="3" class="py-1">
                                                        <v-text-field v-model.number="serviceConfig.agent.maxTokenCount"
                                                            type="number" density="compact" variant="solo-filled" flat
                                                            rounded="lg" label="回复长度上限" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="5" class="py-1">
                                                        <div class="d-flex align-center justify-end ga-2 h-100">
                                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                                prepend-icon="mdi-format-list-bulleted"
                                                                :loading="modelLoading.agentList"
                                                                :disabled="modelLoading.agentTest"
                                                                @click="fetchProviderModels('agent')">
                                                                查看可用模型
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
                                                    <div class="text-subtitle-2 font-weight-bold">轻量任务模型</div>
                                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.utility.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="服务地址" placeholder="例如 https://api.example.com"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.utility.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="访问密钥" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="4" class="py-1">
                                                        <v-combobox v-model="serviceConfig.utility.model"
                                                            :items="modelOptions.utility" density="compact"
                                                            variant="solo-filled" flat rounded="lg" label="模型名称"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="3" class="py-1">
                                                        <v-text-field
                                                            v-model.number="serviceConfig.utility.maxTokenCount"
                                                            type="number" density="compact" variant="solo-filled" flat
                                                            rounded="lg" label="回复长度上限" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="5" class="py-1">
                                                        <div class="d-flex align-center justify-end ga-2 h-100">
                                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                                prepend-icon="mdi-format-list-bulleted"
                                                                :loading="modelLoading.utilityList"
                                                                :disabled="modelLoading.utilityTest"
                                                                @click="fetchProviderModels('utility')">
                                                                查看可用模型
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
                                            <div>
                                                <div class="text-subtitle-1 font-weight-bold">连接知识检索</div>
                                                <div class="text-caption text-medium-emphasis">
                                                    这一步让 OpenCrab 能从课程资料和知识库里找答案。云端知识库需要使用指定的检索模型，默认值请不要随意修改。
                                                </div>
                                            </div>
                                            <v-btn size="x-small" variant="tonal" rounded="lg"
                                                :prepend-icon="showSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                                @click="showSecrets = !showSecrets">
                                                {{ showSecrets ? '隐藏密钥' : '显示密钥' }}
                                            </v-btn>
                                        </div>

                                        <v-sheet color="transparent" class="d-flex flex-column ga-2">
                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">资料理解模型</div>
                                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.embed.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="服务地址" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.embed.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="访问密钥" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" md="7" class="py-1">
                                                        <v-text-field v-model="serviceConfig.embed.model"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="模型名称" hint="云端知识库请使用 BAAI/bge-m3" persistent-hint />
                                                    </v-col>
                                                    <v-col cols="12" md="5" class="py-1">
                                                        <v-text-field v-model.number="serviceConfig.embed.dims"
                                                            type="number" density="compact" variant="solo-filled" flat
                                                            rounded="lg" label="向量维度" hide-details="auto" />
                                                    </v-col>
                                                </v-row>
                                            </div>

                                            <v-divider class="my-1" />

                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">结果排序模型</div>
                                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.rerank.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="服务地址" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.rerank.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="访问密钥" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.rerank.model"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="模型名称" hint="云端知识库请使用 BAAI/bge-reranker-v2-m3" persistent-hint />
                                                    </v-col>
                                                </v-row>
                                            </div>
                                        </v-sheet>
                                    </div>
                                </template>

                                <template v-else-if="step.key === 'services'">
                                    <div class="d-flex flex-column ga-2">
                                        <div class="d-flex align-center justify-space-between ga-3">
                                            <div>
                                                <div class="text-subtitle-1 font-weight-bold">语音和文档辅助功能</div>
                                                <div class="text-caption text-medium-emphasis">
                                                    如果你需要语音输入或上传复杂文档，请填写这些服务。它们会帮助 OpenCrab 识别语音、解析 PDF 和课件。
                                                </div>
                                            </div>
                                            <v-btn size="x-small" variant="tonal" rounded="lg"
                                                :prepend-icon="showSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                                @click="showSecrets = !showSecrets">
                                                {{ showSecrets ? '隐藏密钥' : '显示密钥' }}
                                            </v-btn>
                                        </div>

                                        <v-sheet color="transparent" class="d-flex flex-column ga-2">
                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">语音识别</div>
                                                    <v-chip size="x-small" variant="tonal">Qwen</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.asr.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="服务地址" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.asr.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="访问密钥" :type="showSecrets ? 'text' : 'password'"
                                                            hide-details="auto" />
                                                    </v-col>
                                                </v-row>
                                            </div>

                                            <v-divider class="my-1" />

                                            <div>
                                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                                    <div class="text-subtitle-2 font-weight-bold">文档解析</div>
                                                    <v-chip size="x-small" variant="tonal">File</v-chip>
                                                </div>
                                                <v-row density="compact" class="my-n1">
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.mineru.baseUrl"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="服务地址" hide-details="auto" />
                                                    </v-col>
                                                    <v-col cols="12" class="py-1">
                                                        <v-text-field v-model="serviceConfig.mineru.apiKey"
                                                            density="compact" variant="solo-filled" flat rounded="lg"
                                                            label="访问密钥" :type="showSecrets ? 'text' : 'password'"
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
                                                <div class="text-subtitle-1 font-weight-bold mb-2">准备推荐知识包</div>
                                                <div class="text-caption text-medium-emphasis">
                                                    下载后，OpenCrab 可以在回答时参考课程和校园相关资料。这个过程可能需要一点时间。
                                                </div>
                                            </div>
                                            <v-chip size="small" variant="tonal" color="primary">{{ knowledgePack.packId
                                            }}</v-chip>
                                        </div>

                                        <v-card rounded="lg" variant="tonal" class="pa-4">
                                            <div class="d-flex align-center justify-space-between ga-3 mb-3">
                                                <div>
                                                    <div class="text-subtitle-2 font-weight-bold">SUSTech-CS 入门知识包</div>
                                                    <div class="text-caption text-medium-emphasis">包含课程知识、校园上下文和计算机相关基础资料
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
                                                <div class="text-subtitle-1 font-weight-bold mb-2">准备完成，可以开始使用了</div>
                                                <div class="text-caption text-medium-emphasis">
                                                    下面是你最常用的几个入口。之后也可以随时回到设置页调整模型、校园账号和知识库。
                                                </div>
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
                                                        主要的学习和提问入口。你可以直接提问，也可以上传文件后让 OpenCrab 帮你整理、解释和总结。
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
                                                        集中查看课程、提醒和个人安排，减少在多个日历和消息之间来回确认。
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
                                                        把每天或每周重复做的事情变成自动任务，比如定时总结日程或提醒待办。
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
                                                        管理可以复用的技能，让 OpenCrab 学会更多和课程、资料处理相关的能力。
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
    import { updateProfile as updateUserProfileBackend, writeProfile as writeUserProfileBackend } from '@/api/profile'
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
        { key: 'welcome', shortLabel: '欢迎', title: '欢迎来到 OpenCrab', description: '我们会用几步完成最小设置，让你尽快开始使用。' },
        { key: 'profile', shortLabel: '你是谁', title: '先让 OpenCrab 认识你', description: '一句简单介绍就够了，它会帮助助手理解你的学习背景。' },
        { key: 'identity', shortLabel: '学习背景', title: '确认你的学习身份', description: '选择学校、阶段和专业，OpenCrab 会据此给出更贴近校园场景的建议。' },
        { key: 'campus', shortLabel: '校园账号', title: '连接校园账号', description: '需要课程和日程能力时再填写；不确定的话可以先留空。' },
        { key: 'model', shortLabel: 'AI 模型', title: '连接 AI 模型', description: '填入模型服务信息后，OpenCrab 才能开始回答问题。' },
        { key: 'retrieval', shortLabel: '知识检索', title: '连接知识检索', description: '这会让 OpenCrab 能从课程资料和知识库里找到相关内容。' },
        { key: 'services', shortLabel: '辅助服务', title: '连接语音和文档服务', description: '语音输入、PDF 和课件解析会用到这些服务。' },
        { key: 'knowledge', shortLabel: '知识包', title: '准备推荐知识包', description: '下载推荐资料后，课程相关问答会更有上下文。' },
        { key: 'finish', shortLabel: '完成', title: '一切准备就绪', description: '你可以开始聊天、上传文件、查看日历或创建自动任务了。' },
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
            return '请先填好两个模型的服务地址、密钥和模型名称'
        }
        if (currentMeta.value.key === 'retrieval' && !hasCompleteRetrievalConfig.value) {
            return '请先填好知识检索所需的服务地址、密钥和模型名称'
        }
        if (currentMeta.value.key === 'services' && !hasCompleteServiceToolsConfig.value) {
            return '请先填好语音识别和文档解析服务'
        }
        if (currentMeta.value.key === 'knowledge' && !hasCompleteServiceConfig.value) {
            return '请先完成前面的服务配置'
        }
        if (currentMeta.value.key === 'knowledge' && knowledgePack.status !== 'ready') {
            return '请先下载推荐知识包'
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
        return role === 'agent' ? '日常聊天模型' : '轻量任务模型'
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
                showNotice(`${getModelEndpointLabel(role)}连接成功，但没有找到可选模型`, 'warning')
                return
            }
            showNotice(`找到 ${models.length} 个可用模型`)
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

    function syncUserProfileWriteToBackend () {
        void writeUserProfileBackend(userProfile.oneLineProfile).catch(() => undefined)
    }

    function syncUserProfileUpdateToBackend () {
        void updateUserProfileBackend().catch(() => undefined)
    }

    function goNext () {
        if (!canProceed.value) {
            showNotice('请先完成当前步骤', 'warning')
            return
        }
        persistCurrentStep()
        if (steps[currentStep.value]?.key === 'profile') {
            syncUserProfileWriteToBackend()
        }
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
            showNotice('请先完成前面的服务设置，再下载知识包', 'warning')
            return
        }

        isKnowledgeSubmitting.value = true

        try {
            const synced = await syncServiceConfigToBackend({ silent: true })
            if (!synced) {
                showNotice('服务设置还没有保存成功，暂时不能下载知识包', 'warning')
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
        syncUserProfileUpdateToBackend()
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
