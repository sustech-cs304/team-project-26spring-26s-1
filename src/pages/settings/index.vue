<template>
    <v-layout class="h-100 overflow-hidden min-height-0 bg-surface">
        <v-navigation-drawer permanent width="250" color="surface" floating class="min-height-0">
            <v-list density="compact" class="pa-2" nav>
                <v-list-item v-for="tab in tabs" :key="tab.id" :prepend-icon="tab.icon" :title="tab.label"
                    :active="activeTab === tab.id" rounded="lg" slim prepend-gap="8" :ripple="false"
                    @click="activeTab = tab.id" />
            </v-list>
        </v-navigation-drawer>

        <v-app-bar flat height="48" color="background" rounded="ts-lg">
            <template #prepend>
                <v-icon size="18" class="ml-3">{{ activeTabMeta.icon }}</v-icon>
            </template>

            <v-app-bar-title class="text-center text-body-2 font-weight-bold">
                {{ activeTabMeta.label }}
            </v-app-bar-title>
        </v-app-bar>

        <v-main class="h-100 overflow-hidden min-height-0 bg-background rounded-bs-lg">
            <v-sheet color="background" height="100%" class="overflow-y-auto">
                <v-sheet color="transparent" max-width="720" width="100%" class="mx-auto pa-4 pb-8">
                    <template v-if="isConfigTab(activeTab)">

                        <div v-if="loadingConfig" class="d-flex justify-center py-16">
                            <v-progress-circular indeterminate />
                        </div>

                        <div v-else-if="loadError">
                            <v-alert rounded="lg" variant="tonal" type="error" class="mb-5">
                                {{ loadError }}
                            </v-alert>

                            <v-btn size="small" rounded="lg" variant="tonal" @click="loadConfigData">
                                Retry Loading Config
                            </v-btn>
                        </div>

                        <div v-else-if="activeTab === 'llm'">
                            <div class="text-body-1 font-weight-bold">Model Configuration</div>
                            <div class="text-body-2 text-medium-emphasis mb-4">
                                Configure the primary model for conversation and the utility model for lightweight work.
                            </div>

                            <div class="d-flex justify-end mb-2">
                                <v-btn size="x-small" variant="tonal" rounded="lg"
                                    :prepend-icon="visibility.modelSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click="visibility.modelSecrets = !visibility.modelSecrets">
                                    {{ visibility.modelSecrets ? 'Hide keys' : 'Show keys' }}
                                </v-btn>
                            </div>

                            <div class="mb-2">
                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                    <div class="text-body-1 font-weight-bold">Primary Model</div>
                                    <v-chip size="x-small" variant="tonal">{{ modelConfig.agent.provider }}</v-chip>
                                </div>
                                <v-row density="compact" class="my-n1">
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="modelConfig.agent.baseUrl" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="Base URL"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="modelConfig.agent.apiKey" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="API Key"
                                            :type="visibility.modelSecrets ? 'text' : 'password'" hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="4" class="py-1">
                                        <v-combobox v-model="modelConfig.agent.model" :items="modelOptions.agent"
                                            density="compact" variant="solo-filled" flat rounded="lg" label="Model"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="3" class="py-1">
                                        <v-text-field v-model.number="modelConfig.agent.maxTokenCount" type="number"
                                            density="compact" variant="solo-filled" flat rounded="lg" label="Max Tokens"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="5" class="py-1">
                                        <div class="d-flex align-center justify-end ga-2 h-100">
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-format-list-bulleted"
                                                :loading="modelToolLoading.agentList"
                                                :disabled="modelToolLoading.agentTest"
                                                @click="fetchProviderModels('agent')">
                                                Pull models
                                            </v-btn>
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-connection" :loading="modelToolLoading.agentTest"
                                                :disabled="modelToolLoading.agentList"
                                                @click="testProviderConnection('agent')">
                                                Test
                                            </v-btn>
                                        </div>
                                    </v-col>
                                </v-row>
                            </div>

                            <v-divider class="my-3" />

                            <div class="mb-2">
                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                    <div class="text-body-1 font-weight-bold">Utility Model</div>
                                    <v-chip size="x-small" variant="tonal">{{ modelConfig.utility.provider }}</v-chip>
                                </div>
                                <v-row density="compact" class="my-n1">
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="modelConfig.utility.baseUrl" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="Base URL"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="modelConfig.utility.apiKey" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="API Key"
                                            :type="visibility.modelSecrets ? 'text' : 'password'" hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="4" class="py-1">
                                        <v-combobox v-model="modelConfig.utility.model" :items="modelOptions.utility"
                                            density="compact" variant="solo-filled" flat rounded="lg" label="Model"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="3" class="py-1">
                                        <v-text-field v-model.number="modelConfig.utility.maxTokenCount" type="number"
                                            density="compact" variant="solo-filled" flat rounded="lg" label="Max Tokens"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="5" class="py-1">
                                        <div class="d-flex align-center justify-end ga-2 h-100">
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-format-list-bulleted"
                                                :loading="modelToolLoading.utilityList"
                                                :disabled="modelToolLoading.utilityTest"
                                                @click="fetchProviderModels('utility')">
                                                Pull models
                                            </v-btn>
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-connection" :loading="modelToolLoading.utilityTest"
                                                :disabled="modelToolLoading.utilityList"
                                                @click="testProviderConnection('utility')">
                                                Test
                                            </v-btn>
                                        </div>
                                    </v-col>
                                </v-row>
                            </div>

                            <div class="d-flex justify-end mt-4">
                                <v-btn size="small" rounded="lg" variant="tonal" :loading="saving.models"
                                    @click="saveModelConfiguration">
                                    Save Models
                                </v-btn>
                            </div>
                        </div>

                        <div v-else-if="activeTab === 'retrieval'">
                            <div class="text-body-1 font-weight-bold">Retrieval Configuration</div>
                            <div class="text-body-2 text-medium-emphasis mb-4">
                                Configure embedding and reranking endpoints used by knowledge updates.
                            </div>

                            <div class="d-flex justify-end mb-2">
                                <v-btn size="x-small" variant="tonal" rounded="lg"
                                    :prepend-icon="visibility.retrievalSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click="visibility.retrievalSecrets = !visibility.retrievalSecrets">
                                    {{ visibility.retrievalSecrets ? 'Hide keys' : 'Show keys' }}
                                </v-btn>
                            </div>

                            <div class="mb-2">
                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                    <div class="text-body-1 font-weight-bold">Embed</div>
                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                </div>
                                <v-row density="compact" class="my-n1">
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="retrievalConfig.embed.baseUrl" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="Base URL"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="retrievalConfig.embed.apiKey" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="API Key"
                                            :type="visibility.retrievalSecrets ? 'text' : 'password'"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="4" class="py-1">
                                        <v-combobox v-model="retrievalConfig.embed.model" :items="modelOptions.embed"
                                            density="compact" variant="solo-filled" flat rounded="lg" label="Model"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="3" class="py-1">
                                        <v-text-field v-model.number="retrievalConfig.embed.dims" type="number"
                                            density="compact" variant="solo-filled" flat rounded="lg" label="Dims"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="5" class="py-1">
                                        <div class="d-flex align-center justify-end ga-2 h-100">
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-format-list-bulleted"
                                                :loading="modelToolLoading.embedList"
                                                :disabled="modelToolLoading.embedTest"
                                                @click="fetchProviderModels('embed')">
                                                Pull models
                                            </v-btn>
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-connection" :loading="modelToolLoading.embedTest"
                                                :disabled="modelToolLoading.embedList"
                                                @click="testProviderConnection('embed')">
                                                Test
                                            </v-btn>
                                        </div>
                                    </v-col>
                                </v-row>
                            </div>

                            <v-divider class="my-3" />

                            <div class="mb-2">
                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                    <div class="text-body-1 font-weight-bold">Rerank</div>
                                    <v-chip size="x-small" variant="tonal">OpenAI</v-chip>
                                </div>
                                <v-row density="compact" class="my-n1">
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="retrievalConfig.rerank.baseUrl" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="Base URL"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="retrievalConfig.rerank.apiKey" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="API Key"
                                            :type="visibility.retrievalSecrets ? 'text' : 'password'"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="7" class="py-1">
                                        <v-combobox v-model="retrievalConfig.rerank.model" :items="modelOptions.rerank"
                                            density="compact" variant="solo-filled" flat rounded="lg" label="Model"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="5" class="py-1">
                                        <div class="d-flex align-center justify-end ga-2 h-100">
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-format-list-bulleted"
                                                :loading="modelToolLoading.rerankList"
                                                :disabled="modelToolLoading.rerankTest"
                                                @click="fetchProviderModels('rerank')">
                                                Pull models
                                            </v-btn>
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-connection" :loading="modelToolLoading.rerankTest"
                                                :disabled="modelToolLoading.rerankList"
                                                @click="testProviderConnection('rerank')">
                                                Test
                                            </v-btn>
                                        </div>
                                    </v-col>
                                </v-row>
                            </div>

                            <div class="d-flex justify-end mt-4">
                                <v-btn size="small" rounded="lg" variant="tonal" :loading="saving.retrieval"
                                    @click="saveRetrievalConfiguration">
                                    Save Retrieval
                                </v-btn>
                            </div>
                        </div>

                        <div v-else-if="activeTab === 'services'">
                            <div class="text-body-1 font-weight-bold">Service Configuration</div>
                            <div class="text-body-2 text-medium-emphasis mb-4">
                                Configure speech recognition and document parsing services.
                            </div>

                            <div class="d-flex justify-end mb-2">
                                <v-btn size="x-small" variant="tonal" rounded="lg"
                                    :prepend-icon="visibility.serviceSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click="visibility.serviceSecrets = !visibility.serviceSecrets">
                                    {{ visibility.serviceSecrets ? 'Hide keys' : 'Show keys' }}
                                </v-btn>
                            </div>

                            <div class="mb-2">
                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                    <div class="text-body-1 font-weight-bold">ASR</div>
                                    <v-chip size="x-small" variant="tonal">Qwen</v-chip>
                                </div>
                                <v-row density="compact" class="my-n1">
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="serviceTools.asr.baseUrl" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="Base URL"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="7" class="py-1">
                                        <v-text-field v-model="serviceTools.asr.apiKey" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="API Key"
                                            :type="visibility.serviceSecrets ? 'text' : 'password'"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="5" class="py-1">
                                        <div class="d-flex align-center justify-end h-100">
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-connection" :loading="serviceToolLoading.asr"
                                                @click="testServiceConnection('asr')">
                                                Test
                                            </v-btn>
                                        </div>
                                    </v-col>
                                </v-row>
                            </div>

                            <v-divider class="my-3" />

                            <div class="mb-2">
                                <div class="d-flex align-center justify-space-between ga-2 mb-1">
                                    <div class="text-body-1 font-weight-bold">MinerU</div>
                                    <v-chip size="x-small" variant="tonal">File</v-chip>
                                </div>
                                <v-row density="compact" class="my-n1">
                                    <v-col cols="12" class="py-1">
                                        <v-text-field v-model="serviceTools.mineru.baseUrl" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="Base URL"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="7" class="py-1">
                                        <v-text-field v-model="serviceTools.mineru.apiKey" density="compact"
                                            variant="solo-filled" flat rounded="lg" label="API Key"
                                            :type="visibility.serviceSecrets ? 'text' : 'password'"
                                            hide-details="auto" />
                                    </v-col>
                                    <v-col cols="12" md="5" class="py-1">
                                        <div class="d-flex align-center justify-end h-100">
                                            <v-btn size="small" variant="tonal" rounded="lg"
                                                prepend-icon="mdi-connection" :loading="serviceToolLoading.mineru"
                                                @click="testServiceConnection('mineru')">
                                                Test
                                            </v-btn>
                                        </div>
                                    </v-col>
                                </v-row>
                            </div>

                            <div class="d-flex justify-end mt-4">
                                <v-btn size="small" rounded="lg" variant="tonal" :loading="saving.services"
                                    @click="saveServicesConfiguration">
                                    Save Services
                                </v-btn>
                            </div>
                        </div>

                        <div v-else-if="activeTab === 'mcp'">
                            <div class="d-flex align-start justify-space-between ga-3 mb-4">
                                <div>
                                    <div class="text-body-1 font-weight-bold">MCP Configuration</div>
                                    <div class="text-body-2 text-medium-emphasis">
                                        Configure HTTP and stdio MCP tool servers.
                                    </div>
                                </div>

                                <div class="d-flex align-center ga-2">
                                    <v-btn size="x-small" variant="tonal" rounded="lg"
                                        :prepend-icon="visibility.mcpSecrets ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                        @click="visibility.mcpSecrets = !visibility.mcpSecrets">
                                        {{ visibility.mcpSecrets ? 'Hide tokens' : 'Show tokens' }}
                                    </v-btn>
                                    <v-btn size="x-small" variant="tonal" rounded="lg" prepend-icon="mdi-plus"
                                        @click="addMcpDraft">
                                        Add MCP
                                    </v-btn>
                                </div>
                            </div>

                            <v-alert v-if="mcpDrafts.length === 0" rounded="lg" variant="tonal" type="info"
                                class="mb-3">
                                No MCP servers configured yet.
                            </v-alert>

                            <v-sheet v-for="(draft, index) in mcpDrafts" :key="draft.originalName || draft.name || index"
                                border rounded="lg" color="transparent" class="pa-3 mb-3">
                                <div class="d-flex align-center ga-2 mb-3">
                                    <v-text-field v-model="draft.name" density="compact" variant="solo-filled" flat
                                        rounded="lg" label="Name" hide-details="auto" class="flex-grow-1" />
                                    <v-btn icon="mdi-delete-outline" size="small" variant="text" :ripple="false"
                                        color="error" @click="removeMcpDraft(index)" />
                                </div>

                                <div class="d-flex align-center justify-space-between ga-2 mb-3">
                                    <div>
                                        <div class="text-caption font-weight-medium text-medium-emphasis">
                                            Enabled
                                        </div>
                                        <div class="text-caption text-medium-emphasis">
                                            Disabled servers stay saved but do not start.
                                        </div>
                                    </div>
                                    <v-switch v-model="draft.enabled" density="compact" hide-details />
                                </div>

                                <div class="mb-3">
                                    <div class="text-caption font-weight-medium text-medium-emphasis mb-1">
                                        Transport
                                    </div>
                                    <v-btn-toggle v-model="draft.transport" mandatory divided class="w-100"
                                        color="primary" variant="tonal">
                                        <v-btn value="http" class="flex-grow-1" prepend-icon="mdi-web" size="small">
                                            HTTP
                                        </v-btn>
                                        <v-btn value="stdio" class="flex-grow-1" prepend-icon="mdi-terminal"
                                            size="small">
                                            stdio
                                        </v-btn>
                                    </v-btn-toggle>
                                </div>

                                <template v-if="draft.transport === 'http'">
                                    <v-row density="compact" class="my-n1">
                                        <v-col cols="12" class="py-1">
                                            <v-text-field v-model="draft.url" density="compact" variant="solo-filled"
                                                flat rounded="lg" label="URL" hide-details="auto" />
                                        </v-col>
                                        <v-col cols="12" class="py-1">
                                            <v-text-field v-model="draft.token" density="compact" variant="solo-filled"
                                                flat rounded="lg" label="Token"
                                                :type="visibility.mcpSecrets ? 'text' : 'password'"
                                                hide-details="auto" />
                                        </v-col>
                                    </v-row>
                                </template>

                                <template v-else>
                                    <v-row density="compact" class="my-n1">
                                        <v-col cols="12" class="py-1">
                                            <v-text-field v-model="draft.command" density="compact"
                                                variant="solo-filled" flat rounded="lg" label="Command"
                                                hide-details="auto" />
                                        </v-col>
                                        <v-col cols="12" md="6" class="py-1">
                                            <v-text-field v-model="draft.cwd" density="compact" variant="solo-filled"
                                                flat rounded="lg" label="Working Dir" hide-details="auto" />
                                        </v-col>
                                        <v-col cols="12" md="6" class="py-1">
                                            <v-textarea v-model="draft.argsText" density="compact"
                                                variant="solo-filled" flat rounded="lg" label="Args" hide-details="auto"
                                                rows="4" auto-grow placeholder="--flag&#10;--another-flag" />
                                        </v-col>
                                        <v-col cols="12" class="py-1">
                                            <v-textarea v-model="draft.envText" density="compact"
                                                variant="solo-filled" flat rounded="lg" label="Env" hide-details="auto"
                                                rows="4" auto-grow placeholder="KEY=value&#10;OTHER=value" />
                                        </v-col>
                                    </v-row>
                                </template>
                            </v-sheet>

                            <div class="d-flex justify-end mt-4">
                                <v-btn size="small" rounded="lg" variant="tonal" :loading="saving.mcp"
                                    @click="saveMcpConfiguration">
                                    Save MCP
                                </v-btn>
                            </div>
                        </div>

                        <div v-else-if="activeTab === 'onebot'">
                            <div class="text-body-1 font-weight-bold">OneBot</div>
                            <div class="text-body-2 text-medium-emphasis mb-6">
                                Edit the backend-managed OneBot token and superuser list.
                            </div>

                            <div class="mb-4">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Bot Token</div>
                                <v-text-field v-model="onebot.token" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto"
                                    :type="visibility.onebotToken ? 'text' : 'password'"
                                    :append-inner-icon="visibility.onebotToken ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.onebotToken = !visibility.onebotToken" />
                            </div>

                            <div class="mb-4">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Superuser IDs
                                </div>
                                <v-textarea v-model="onebot.superuserIdsText" density="compact" variant="solo-filled"
                                    flat rounded="lg" hide-details="auto" rows="4" auto-grow
                                    placeholder="123456&#10;789012" />
                                <div class="text-caption text-medium-emphasis mt-1">
                                    Enter one OneBot superuser ID per line. Commas are also supported.
                                </div>
                            </div>

                            <div class="d-flex justify-end">
                                <v-btn size="small" rounded="lg" variant="tonal" :loading="saving.onebot"
                                    @click="saveOnebotConfiguration">
                                    Save OneBot Settings
                                </v-btn>
                            </div>
                        </div>

                        <div v-else-if="activeTab === 'telegram'">
                            <div class="text-body-1 font-weight-bold">Telegram</div>
                            <div class="text-body-2 text-medium-emphasis mb-6">
                                Edit the backend-managed Telegram bot token and superuser list.
                            </div>

                            <div class="mb-4">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Bot Token</div>
                                <v-text-field v-model="telegram.token" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto"
                                    :type="visibility.telegramToken ? 'text' : 'password'"
                                    :append-inner-icon="visibility.telegramToken ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                    @click:append-inner="visibility.telegramToken = !visibility.telegramToken" />
                            </div>

                            <div class="mb-4">
                                <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Superuser IDs
                                </div>
                                <v-textarea v-model="telegram.superuserIdsText" density="compact" variant="solo-filled"
                                    flat rounded="lg" hide-details="auto" rows="4" auto-grow
                                    placeholder="123456&#10;789012" />
                                <div class="text-caption text-medium-emphasis mt-1">
                                    Enter one Telegram user ID per line. Commas are also supported.
                                </div>
                            </div>

                            <div class="d-flex justify-end">
                                <v-btn size="small" rounded="lg" variant="tonal" :loading="saving.telegram"
                                    @click="saveTelegramConfiguration">
                                    Save Telegram Settings
                                </v-btn>
                            </div>
                        </div>
                    </template>

                    <div v-else-if="activeTab === 'credentials'">
                        <div class="text-body-1 font-weight-bold">Credential Vault</div>
                        <div class="text-body-2 text-medium-emphasis mb-4">
                            Securely store and manage your SUSTech authentication credentials.
                        </div>

                        <div class="mb-4">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Student ID</div>
                            <v-text-field v-model="creds.studentId" density="compact" variant="solo-filled" flat
                                rounded="lg" placeholder="e.g. 12110001" hide-details="auto" />
                        </div>

                        <div class="mb-4">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Password</div>
                            <v-text-field v-model="creds.password" density="compact" variant="solo-filled" flat
                                rounded="lg" hide-details="auto" :type="showPassword ? 'text' : 'password'"
                                :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                @click:append-inner="showPassword = !showPassword" />
                        </div>

                        <div class="d-flex justify-end">
                            <v-btn size="small" rounded="lg" variant="tonal" :loading="saving.credentials"
                                @click="saveCredentialVault">
                                Save Credentials
                            </v-btn>
                        </div>
                    </div>

                    <div v-else-if="activeTab === 'appearance'">
                        <div class="text-body-1 font-weight-bold">Appearance</div>
                        <div class="text-body-2 text-medium-emphasis mb-6">
                            Customize the look and feel of the application.
                        </div>

                        <div class="mb-4">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Theme</div>
                            <v-item-group v-model="appearance.theme" mandatory>
                                <v-row density="compact">
                                    <v-col v-for="option in themeOptions" :key="option.value" cols="12" sm="4">
                                        <v-item v-slot="{ isSelected, toggle }" :value="option.value">
                                            <v-card rounded="lg" elevation="0" border
                                                :variant="isSelected ? 'tonal' : 'flat'" @click="toggle">
                                                <v-card-text class="pa-3">
                                                    <div class="d-flex align-center ga-2">
                                                        <v-icon size="18">{{ option.icon }}</v-icon>
                                                        <div class="text-body-2 font-weight-medium">
                                                            {{ option.label }}
                                                        </div>
                                                        <v-spacer />
                                                        <v-icon v-if="isSelected" size="15">mdi-check</v-icon>
                                                    </div>
                                                </v-card-text>
                                            </v-card>
                                        </v-item>
                                    </v-col>
                                </v-row>
                            </v-item-group>
                            <div class="text-caption text-medium-emphasis mt-1">
                                System mode follows your OS appearance settings.
                            </div>
                        </div>

                    </div>

                    <div v-else-if="activeTab === 'notifications'">
                        <div class="text-body-1 font-weight-bold">Notifications</div>
                        <div class="text-body-2 text-medium-emphasis mb-4">
                            Control when and how you receive notifications.
                        </div>

                        <v-list bg-color="transparent" density="compact" class="pa-0 mb-4">
                            <v-list-item rounded="lg" slim variant="tonal" class="mb-1">
                                <template #prepend>
                                    <v-icon size="18">mdi-bell-outline</v-icon>
                                </template>
                                <v-list-item-title>Enable Notifications</v-list-item-title>
                                <v-list-item-subtitle>Master toggle for all notification types.</v-list-item-subtitle>
                                <template #append>
                                    <v-switch v-model="notif.enabled" density="compact" hide-details />
                                </template>
                            </v-list-item>

                            <template v-for="item in notifItems" :key="item.key">
                                <v-list-item rounded="lg" slim variant="tonal" class="mb-1" :disabled="!notif.enabled">
                                    <template #prepend>
                                        <v-icon size="18">{{ item.icon }}</v-icon>
                                    </template>
                                    <v-list-item-title>{{ item.label }}</v-list-item-title>
                                    <v-list-item-subtitle>{{ item.description }}</v-list-item-subtitle>
                                    <template #append>
                                        <v-switch v-model="notif[item.key]" density="compact" hide-details
                                            :disabled="!notif.enabled" />
                                    </template>
                                </v-list-item>
                            </template>
                        </v-list>

                        <div class="d-flex justify-end">
                            <v-btn size="small" rounded="lg" variant="tonal" @click="saveNotificationSettings">
                                Save Notification Settings
                            </v-btn>
                        </div>
                    </div>

                    <div v-else-if="activeTab === 'preferences'">
                        <div class="text-body-1 font-weight-bold">System Preferences</div>
                        <div class="text-body-2 text-medium-emphasis mb-4">
                            Configure system-level behavior of the agent.
                        </div>

                        <div class="mb-4">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Wake Shortcut</div>
                            <div class="d-flex align-center ga-2">
                                <v-text-field
                                    :model-value="prefs.recording ? 'Listening for a shortcut...' : prefs.shortcut"
                                    density="compact" variant="solo-filled" flat rounded="lg" hide-details readonly
                                    prepend-inner-icon="mdi-keyboard-outline" :focused="prefs.recording" />
                                <v-btn variant="tonal" rounded="lg" size="small" :disabled="prefs.recording"
                                    @click="startRecording">
                                    {{ prefs.recording ? 'Recording...' : 'Record' }}
                                </v-btn>
                            </div>
                            <div v-if="prefs.recording" class="text-caption text-medium-emphasis mt-1">
                                Press a key combination...
                            </div>
                        </div>

                        <v-list bg-color="transparent" density="compact" class="pa-0 mb-4">
                            <v-list-item rounded="lg" slim variant="tonal">
                                <template #prepend>
                                    <v-icon size="18">mdi-power</v-icon>
                                </template>
                                <v-list-item-title>Launch on Startup</v-list-item-title>
                                <v-list-item-subtitle>Automatically start OpenCrab when system
                                    boots.</v-list-item-subtitle>
                                <template #append>
                                    <v-switch v-model="prefs.startup" density="compact" hide-details />
                                </template>
                            </v-list-item>
                        </v-list>

                        <div class="mb-4">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Default Workspace
                                Path</div>
                            <div class="d-flex align-center ga-2">
                                <v-text-field v-model="prefs.workspacePath" density="compact" variant="solo-filled" flat
                                    rounded="lg" hide-details="auto" class="flex-grow-1" />
                                <v-btn variant="tonal" rounded="lg" size="small" prepend-icon="mdi-folder-outline"
                                    @click="browseWorkspace">
                                    Browse
                                </v-btn>
                            </div>
                            <div class="text-caption text-medium-emphasis mt-1">
                                Agent will organize files, download courseware, and store data in this directory.
                            </div>
                        </div>

                        <div class="d-flex justify-end">
                            <v-btn size="small" rounded="lg" variant="tonal" @click="savePreferences">
                                Save Preferences
                            </v-btn>
                        </div>
                    </div>

                    <div v-else-if="activeTab === 'developer'">
                        <div class="text-body-1 font-weight-bold">Developer</div>
                        <div class="text-body-2 text-medium-emphasis mb-4">
                            Development-only controls for API routing and onboarding.
                        </div>

                        <v-list bg-color="transparent" density="compact" class="pa-0 mb-4">
                            <v-list-item rounded="lg" slim variant="tonal">
                                <template #prepend>
                                    <v-icon size="18">mdi-cloud-sync-outline</v-icon>
                                </template>
                                <v-list-item-title>Use Cloud API by Default</v-list-item-title>
                                <v-list-item-subtitle>{{ developer.currentBaseURL }}</v-list-item-subtitle>
                                <template #append>
                                    <v-switch v-model="developer.defaultBaseURLIsCloud" density="compact" hide-details
                                        @update:model-value="onDeveloperApiToggle" />
                                </template>
                            </v-list-item>
                        </v-list>

                        <div class="mb-4">
                            <div class="text-caption font-weight-medium text-medium-emphasis mb-1">Onboarding</div>
                            <div class="d-flex align-center justify-space-between ga-3">
                                <div class="text-caption text-medium-emphasis">
                                    The onboarding flow appears automatically on first setup. Open it here when you need
                                    to
                                    rerun it.
                                </div>
                                <v-btn size="small" rounded="lg" variant="tonal" prepend-icon="mdi-map-outline"
                                    @click="openOnboardingFromDeveloper">
                                    Open Onboarding
                                </v-btn>
                            </div>
                        </div>
                    </div>
                </v-sheet>
            </v-sheet>
        </v-main>

        <v-snackbar v-model="notice.show" :color="notice.color" timeout="2600" location="top">
            {{ notice.text }}
        </v-snackbar>
    </v-layout>
</template>

<script setup lang="ts">
    import { patchCas } from '@/api/cas'
    import { getConfig, patchConfig, type AppConfig, type ASREndpointConfig, type DeepPartial, type EmbedEndpointConfig, type FileConfig, type LLMEndpointConfig, type LLMProviderType, type MCPConfig, type RerankerEndpointConfig } from '@/api/config'
    import { useOnboardingConfig } from '@/composables/useOnboardingConfig'
    import { requestOpenAIModels } from '@/composables/useOpenAIModelTools'
    import { baseURL, getDefaultBaseURLIsCloud, setDefaultBaseURLIsCloud } from '@/utils/http'
    import { useRoute } from 'vue-router'
    import { useTheme } from 'vuetify'
    import { getStoredThemePreference, setStoredThemePreference, type ThemePreference } from '@/utils/theme'

    type SettingsTabId =
        | 'llm'
        | 'retrieval'
        | 'services'
        | 'mcp'
        | 'onebot'
        | 'telegram'
        | 'credentials'
        | 'appearance'
        | 'notifications'
        | 'preferences'
        | 'developer'

    type NoticeColor = 'success' | 'error' | 'warning'
    type NotificationKey = 'taskComplete' | 'taskFailed' | 'calendarReminder'
    type OpenAIProviderKey = 'agent' | 'utility' | 'embed' | 'rerank'
    type ServiceToolKey = 'asr' | 'mineru'
    type McpTransport = 'http' | 'stdio'

    interface McpDraft {
        originalName: string
        name: string
        transport: McpTransport
        enabled: boolean
        url: string
        token: string
        command: string
        argsText: string
        envText: string
        cwd: string
    }

    interface NotificationItem {
        key: NotificationKey
        icon: string
        label: string
        description: string
    }

    const route = useRoute()
    const router = useRouter()
    const theme = useTheme()
    const activeTab = ref<SettingsTabId>('llm')
    const { campusAuth, saveCampusAuth, saveServiceConfig } = useOnboardingConfig()

    const tabs: { id: SettingsTabId, icon: string, label: string }[] = [
        { id: 'llm', icon: 'mdi-brain', label: 'Models' },
        { id: 'retrieval', icon: 'mdi-database-search-outline', label: 'Retrieval' },
        { id: 'services', icon: 'mdi-tools', label: 'Services' },
        { id: 'mcp', icon: 'mdi-connection', label: 'MCP' },
        { id: 'onebot', icon: 'mdi-robot-outline', label: 'OneBot' },
        { id: 'telegram', icon: 'mdi-send-outline', label: 'Telegram' },
        { id: 'credentials', icon: 'mdi-shield-check', label: 'Credential Vault' },
        { id: 'appearance', icon: 'mdi-palette-outline', label: 'Appearance' },
        { id: 'notifications', icon: 'mdi-bell-outline', label: 'Notifications' },
        { id: 'preferences', icon: 'mdi-wrench-outline', label: 'System Preferences' },
        { id: 'developer', icon: 'mdi-code-braces', label: 'Developer' },
    ]

    const activeTabMeta = computed(() =>
        tabs.find(tab => tab.id === activeTab.value) ?? tabs[0]!
    )

    watch(
        () => route.query.tab,
        (value) => {
            if (typeof value !== 'string') return
            if (tabs.some(tab => tab.id === value)) {
                activeTab.value = value as SettingsTabId
            }
        },
        { immediate: true }
    )

    const notice = reactive({
        show: false,
        text: '',
        color: 'success' as NoticeColor,
    })

    const loadingConfig = ref(true)
    const loadError = ref('')
    const loadedConfig = shallowRef<AppConfig | null>(null)
    const saving = reactive({
        models: false,
        retrieval: false,
        services: false,
        mcp: false,
        onebot: false,
        telegram: false,
        credentials: false,
    })

    const visibility = reactive({
        modelSecrets: false,
        retrievalSecrets: false,
        serviceSecrets: false,
        mcpSecrets: false,
        onebotToken: false,
        telegramToken: false,
    })

    const modelConfig = reactive({
        agent: {
            provider: 'OpenAI' as LLMProviderType,
            baseUrl: '',
            apiKey: '',
            model: '',
            maxTokenCount: 128000,
        },
        utility: {
            provider: 'OpenAI' as LLMProviderType,
            baseUrl: '',
            apiKey: '',
            model: '',
            maxTokenCount: 128000,
        },
    })

    const retrievalConfig = reactive({
        embed: {
            baseUrl: '',
            apiKey: '',
            model: '',
            dims: 1536,
        },
        rerank: {
            baseUrl: '',
            apiKey: '',
            model: '',
        },
    })

    const serviceTools = reactive({
        asr: {
            baseUrl: '',
            apiKey: '',
        },
        mineru: {
            baseUrl: '',
            apiKey: '',
        },
    })

    const modelOptions = reactive<Record<OpenAIProviderKey, string[]>>({
        agent: [],
        utility: [],
        embed: [],
        rerank: [],
    })

    const modelToolLoading = reactive<Record<`${OpenAIProviderKey}List` | `${OpenAIProviderKey}Test`, boolean>>({
        agentList: false,
        agentTest: false,
        utilityList: false,
        utilityTest: false,
        embedList: false,
        embedTest: false,
        rerankList: false,
        rerankTest: false,
    })

    const serviceToolLoading = reactive<Record<ServiceToolKey, boolean>>({
        asr: false,
        mineru: false,
    })

    const developer = reactive({
        defaultBaseURLIsCloud: getDefaultBaseURLIsCloud(),
        currentBaseURL: baseURL,
    })

    const onebot = reactive({
        token: '',
        superuserIdsText: '',
    })

    const telegram = reactive({
        token: '',
        superuserIdsText: '',
    })

    const mcpDrafts = ref<McpDraft[]>([])

    const showPassword = ref(false)
    const creds = reactive({
        studentId: campusAuth.studentId,
        password: campusAuth.password,
    })

    const themeOptions = [
        {
            value: 'system' as ThemePreference,
            label: 'System',
            icon: 'mdi-monitor',
            description: 'Follow your operating system setting.',
        },
        {
            value: 'light' as ThemePreference,
            label: 'Light',
            icon: 'mdi-white-balance-sunny',
            description: 'Use a brighter interface for daytime work.',
        },
        {
            value: 'dark' as ThemePreference,
            label: 'Dark',
            icon: 'mdi-weather-night',
            description: 'Use a darker interface for lower-glare viewing.',
        },
    ]

    const appearance = reactive({
        theme: getStoredThemePreference(),
    })

    const notif = reactive({
        enabled: true,
        taskComplete: true,
        taskFailed: true,
        calendarReminder: true,
    })

    const notifItems: NotificationItem[] = [
        {
            key: 'taskComplete',
            icon: 'mdi-check-circle-outline',
            label: 'Task Completed',
            description: 'Notify when a scheduled task finishes successfully.',
        },
        {
            key: 'taskFailed',
            icon: 'mdi-alert-circle-outline',
            label: 'Task Failed',
            description: 'Notify when a task encounters an error or failure.',
        },
        {
            key: 'calendarReminder',
            icon: 'mdi-calendar-clock-outline',
            label: 'Calendar Reminders',
            description: 'Remind you before upcoming events.',
        },
    ]

    const prefs = reactive({
        shortcut: 'Alt + Space',
        recording: false,
        startup: true,
        workspacePath: '~/Documents/OpenCrab',
    })

    let shortcutHandler: ((event: KeyboardEvent) => void) | null = null
    let recordTimer: ReturnType<typeof setTimeout> | null = null

    function isConfigTab (tab: SettingsTabId) {
        return tab === 'llm' || tab === 'retrieval' || tab === 'services' || tab === 'mcp' || tab === 'onebot' || tab === 'telegram'
    }

    function showNotice (text: string, color: NoticeColor = 'success') {
        notice.show = true
        notice.text = text
        notice.color = color
    }

    function getErrorMessage (error: unknown, fallback: string) {
        const responseMessage = (error as any)?.response?.data?.message || (error as any)?.response?.data?.detail
        return responseMessage || (error as any)?.message || fallback
    }

    function createMcpDraft (name = '', config?: MCPConfig): McpDraft {
        return {
            originalName: name,
            name,
            transport: config?.transport ?? 'http',
            enabled: config?.enabled ?? false,
            url: config?.url ?? '',
            token: config?.token ?? '',
            command: config?.command ?? '',
            argsText: (config?.args ?? []).join('\n'),
            envText: Object.entries(config?.env ?? {})
                .map(([key, value]) => `${key}=${value}`)
                .join('\n'),
            cwd: config?.cwd ?? '',
        }
    }

    function normalizeMcpArgs (text: string): string[] {
        return text
            .split(/\r?\n/)
            .map(line => line.trim())
            .filter(Boolean)
    }

    function normalizeMcpEnv (text: string): Record<string, string> {
        const result: Record<string, string> = {}

        for (const [index, line] of text.split(/\r?\n/).entries()) {
            const trimmed = line.trim()
            if (!trimmed) continue

            const separatorIndex = trimmed.indexOf('=')
            if (separatorIndex < 1) {
                throw new Error(`MCP env line ${index + 1} must use KEY=VALUE format.`)
            }

            const key = trimmed.slice(0, separatorIndex).trim()
            const value = trimmed.slice(separatorIndex + 1).trim()
            if (!key) {
                throw new Error(`MCP env line ${index + 1} is missing a key.`)
            }

            result[key] = value
        }

        return result
    }

    function hydrateMcpDrafts (mcpConfig: Record<string, MCPConfig>) {
        mcpDrafts.value = Object.entries(mcpConfig).map(([name, config]) => createMcpDraft(name, config))
    }

    function addMcpDraft () {
        const existingNames = new Set(
            mcpDrafts.value
                .map(draft => draft.name.trim())
                .filter(Boolean)
        )

        let index = mcpDrafts.value.length + 1
        let candidate = `mcp-${index}`
        while (existingNames.has(candidate)) {
            index += 1
            candidate = `mcp-${index}`
        }

        mcpDrafts.value.push(createMcpDraft(candidate))
    }

    function removeMcpDraft (index: number) {
        mcpDrafts.value.splice(index, 1)
    }

    function buildMcpConfig (draft: McpDraft): MCPConfig {
        return {
            transport: draft.transport,
            enabled: draft.enabled,
            url: draft.url.trim() || null,
            token: draft.token.trim() || null,
            command: draft.command.trim() || null,
            args: normalizeMcpArgs(draft.argsText),
            env: normalizeMcpEnv(draft.envText),
            cwd: draft.cwd.trim() || null,
        }
    }

    function buildMcpPatch (): Record<string, MCPConfig | null> | null {
        const snapshot = loadedConfig.value?.mcp || {}
        const patch: Record<string, MCPConfig | null> = {}
        const currentNames = new Set<string>()

        for (const draft of mcpDrafts.value) {
            const nextName = draft.name.trim()
            if (!nextName) {
                throw new Error('Each MCP server needs a name.')
            }
            if (currentNames.has(nextName)) {
                throw new Error(`Duplicate MCP name: ${nextName}`)
            }

            currentNames.add(nextName)
            if (draft.originalName && draft.originalName !== nextName) {
                patch[draft.originalName] = null
            }
            patch[nextName] = buildMcpConfig(draft)
        }

        for (const name of Object.keys(snapshot)) {
            if (!currentNames.has(name)) {
                patch[name] = null
            }
        }

        return Object.keys(patch).length ? patch : null
    }

    function validateMcpDrafts () {
        for (const draft of mcpDrafts.value) {
            const name = draft.name.trim()
            if (!name) {
                throw new Error('Each MCP server needs a name.')
            }
            if (!draft.enabled) continue

            if (draft.transport === 'http' && !draft.url.trim()) {
                throw new Error(`MCP "${name}" needs a URL when HTTP is enabled.`)
            }
            if (draft.transport === 'stdio' && !draft.command.trim()) {
                throw new Error(`MCP "${name}" needs a command when stdio is enabled.`)
            }
        }
    }

    function getOpenAIProviderLabel (key: OpenAIProviderKey) {
        const labels: Record<OpenAIProviderKey, string> = {
            agent: 'Primary model',
            utility: 'Utility model',
            embed: 'Embed',
            rerank: 'Rerank',
        }
        return labels[key]
    }

    function getOpenAIProviderDraft (key: OpenAIProviderKey) {
        if (key === 'agent' || key === 'utility') {
            return modelConfig[key]
        }
        return retrievalConfig[key]
    }

    async function fetchProviderModels (key: OpenAIProviderKey) {
        const loadingKey = `${key}List` as const
        modelToolLoading[loadingKey] = true

        try {
            const models = await requestOpenAIModels(getOpenAIProviderDraft(key), getOpenAIProviderLabel(key))
            modelOptions[key] = models
            if (!models.length) {
                showNotice(`${getOpenAIProviderLabel(key)} connected, but no model list was returned.`, 'warning')
                return
            }
            showNotice(`Pulled ${models.length} models.`)
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to pull model list.'), 'error')
        } finally {
            modelToolLoading[loadingKey] = false
        }
    }

    async function testProviderConnection (key: OpenAIProviderKey) {
        const loadingKey = `${key}Test` as const
        modelToolLoading[loadingKey] = true

        try {
            await requestOpenAIModels(getOpenAIProviderDraft(key), getOpenAIProviderLabel(key))
            showNotice(`${getOpenAIProviderLabel(key)} connection looks good.`)
        } catch (error) {
            showNotice(getErrorMessage(error, 'Connection test failed.'), 'error')
        } finally {
            modelToolLoading[loadingKey] = false
        }
    }

    function assertServiceDraft (key: ServiceToolKey) {
        const draft = serviceTools[key]
        if (!draft.baseUrl.trim() || !draft.apiKey.trim()) {
            throw new Error(`Please fill ${key === 'asr' ? 'ASR' : 'MinerU'} Base URL and API Key first.`)
        }
        return draft
    }

    function testWebSocketConnection (url: string) {
        return new Promise<void>((resolve, reject) => {
            const socket = new WebSocket(url)
            const timer = window.setTimeout(() => {
                socket.close()
                reject(new Error('Connection timed out.'))
            }, 6000)

            socket.addEventListener('open', () => {
                clearTimeout(timer)
                socket.close()
                resolve()
            }, { once: true })

            socket.addEventListener('error', () => {
                clearTimeout(timer)
                reject(new Error('WebSocket connection failed.'))
            }, { once: true })
        })
    }

    async function testServiceConnection (key: ServiceToolKey) {
        serviceToolLoading[key] = true

        try {
            const draft = assertServiceDraft(key)
            const trimmedUrl = draft.baseUrl.trim()
            if (/^wss?:\/\//i.test(trimmedUrl)) {
                await testWebSocketConnection(trimmedUrl)
            } else {
                const response = await fetch(trimmedUrl, {
                    method: 'GET',
                    headers: {
                        Accept: 'application/json',
                        Authorization: `Bearer ${draft.apiKey.trim()}`,
                    },
                })
                if (!response.ok) {
                    throw new Error(`Connection failed (${response.status}).`)
                }
            }
            showNotice(`${key === 'asr' ? 'ASR' : 'MinerU'} connection looks good.`)
        } catch (error) {
            showNotice(getErrorMessage(error, 'Connection test failed.'), 'error')
        } finally {
            serviceToolLoading[key] = false
        }
    }

    function onDeveloperApiToggle (value: boolean | null) {
        setDefaultBaseURLIsCloud(Boolean(value))
        developer.currentBaseURL = baseURL
    }

    function openOnboardingFromDeveloper () {
        router.push('/onboarding')
    }

    function applyConfig (config: AppConfig) {
        loadedConfig.value = config

        modelConfig.agent.provider = config.api.agent.type
        modelConfig.agent.baseUrl = config.api.agent.base_url || ''
        modelConfig.agent.apiKey = config.api.agent.api_key || ''
        modelConfig.agent.model = config.api.agent.model || ''
        modelConfig.agent.maxTokenCount = config.api.agent.max_token_count || 128000

        modelConfig.utility.provider = config.api.utility.type
        modelConfig.utility.baseUrl = config.api.utility.base_url || ''
        modelConfig.utility.apiKey = config.api.utility.api_key || ''
        modelConfig.utility.model = config.api.utility.model || ''
        modelConfig.utility.maxTokenCount = config.api.utility.max_token_count || 128000

        retrievalConfig.embed.baseUrl = config.api.embed.base_url || ''
        retrievalConfig.embed.apiKey = config.api.embed.api_key || ''
        retrievalConfig.embed.model = config.api.embed.model || ''
        retrievalConfig.embed.dims = config.api.embed.dims || 1536

        retrievalConfig.rerank.baseUrl = config.api.rerank.base_url || ''
        retrievalConfig.rerank.apiKey = config.api.rerank.api_key || ''
        retrievalConfig.rerank.model = config.api.rerank.model || ''

        serviceTools.asr.baseUrl = config.api.asr.base_url || ''
        serviceTools.asr.apiKey = config.api.asr.api_key || ''

        serviceTools.mineru.baseUrl = config.file?.mineru?.base_url || ''
        serviceTools.mineru.apiKey = config.file?.mineru?.api_key || ''

        saveServiceConfig({
            agent: {
                baseUrl: modelConfig.agent.baseUrl,
                apiKey: modelConfig.agent.apiKey,
                model: modelConfig.agent.model,
                maxTokenCount: modelConfig.agent.maxTokenCount,
            },
            utility: {
                baseUrl: modelConfig.utility.baseUrl,
                apiKey: modelConfig.utility.apiKey,
                model: modelConfig.utility.model,
                maxTokenCount: modelConfig.utility.maxTokenCount,
            },
            embed: {
                baseUrl: retrievalConfig.embed.baseUrl,
                apiKey: retrievalConfig.embed.apiKey,
                model: retrievalConfig.embed.model,
                dims: retrievalConfig.embed.dims,
            },
            rerank: {
                baseUrl: retrievalConfig.rerank.baseUrl,
                apiKey: retrievalConfig.rerank.apiKey,
                model: retrievalConfig.rerank.model,
            },
            asr: {
                baseUrl: serviceTools.asr.baseUrl,
                apiKey: serviceTools.asr.apiKey,
            },
            mineru: {
                baseUrl: serviceTools.mineru.baseUrl,
                apiKey: serviceTools.mineru.apiKey,
            },
        })

        onebot.token = config.onebot?.token || ''
        onebot.superuserIdsText = (config.onebot?.superuser_ids || []).map(id => String(id)).join('\n')

        telegram.token = config.telegram?.token || ''
        telegram.superuserIdsText = (config.telegram?.superuser_ids || []).map(id => String(id)).join('\n')

        hydrateMcpDrafts(config.mcp || {})
    }

    function parseSuperuserIds (value: string) {
        return value
            .split(/[\n,]+/)
            .map(item => item.trim())
            .filter(Boolean)
    }

    function areStringArraysEqual (left: string[], right: string[]) {
        return left.length === right.length && left.every((value, index) => value === right[index])
    }

    async function loadConfigData () {
        loadingConfig.value = true
        loadError.value = ''

        try {
            const config = await getConfig()
            applyConfig(config)
        } catch (error) {
            loadError.value = getErrorMessage(error, 'Failed to load backend config.')
        } finally {
            loadingConfig.value = false
        }
    }

    function buildModelEndpointPatch (value: typeof modelConfig.agent): DeepPartial<LLMEndpointConfig> {
        return {
            type: value.provider,
            base_url: value.baseUrl.trim(),
            api_key: value.apiKey.trim(),
            model: value.model.trim(),
            max_token_count: value.maxTokenCount,
        }
    }

    function buildEmbedPatch (): DeepPartial<EmbedEndpointConfig> {
        return {
            type: 'OpenAI',
            base_url: retrievalConfig.embed.baseUrl.trim(),
            api_key: retrievalConfig.embed.apiKey.trim(),
            model: retrievalConfig.embed.model.trim(),
            dims: retrievalConfig.embed.dims,
        }
    }

    function buildRerankPatch (): DeepPartial<RerankerEndpointConfig> {
        return {
            type: 'OpenAI',
            base_url: retrievalConfig.rerank.baseUrl.trim(),
            api_key: retrievalConfig.rerank.apiKey.trim(),
            model: retrievalConfig.rerank.model.trim(),
        }
    }

    function buildAsrPatch (): DeepPartial<ASREndpointConfig> {
        return {
            type: 'Qwen',
            base_url: serviceTools.asr.baseUrl.trim(),
            api_key: serviceTools.asr.apiKey.trim(),
        }
    }

    function buildMineruPatch (): NonNullable<DeepPartial<FileConfig>['mineru']> {
        return {
            base_url: serviceTools.mineru.baseUrl.trim(),
            api_key: serviceTools.mineru.apiKey.trim(),
        }
    }

    function buildOnebotPatch (): DeepPartial<AppConfig> | null {
        const snapshot = loadedConfig.value
        if (!snapshot) return null

        const onebotPatch: DeepPartial<AppConfig['onebot']> = {}
        const nextToken = onebot.token.trim()
        const nextSuperuserIds = parseSuperuserIds(onebot.superuserIdsText)

        if (nextToken !== snapshot.onebot.token) {
            onebotPatch.token = nextToken
        }

        if (!areStringArraysEqual(nextSuperuserIds, snapshot.onebot.superuser_ids || [])) {
            onebotPatch.superuser_ids = nextSuperuserIds
        }

        if (!Object.keys(onebotPatch).length) return null

        return {
            onebot: onebotPatch,
        }
    }

    function buildTelegramPatch () {
        const snapshot = loadedConfig.value
        if (!snapshot) return null

        const telegramPatch: NonNullable<DeepPartial<AppConfig['telegram']>> = {}
        const nextToken = telegram.token.trim()
        const nextSuperuserIds = parseSuperuserIds(telegram.superuserIdsText)
        const currentTelegram = snapshot.telegram

        if (nextToken !== (currentTelegram?.token || '')) {
            telegramPatch.token = nextToken
        }

        if (!areStringArraysEqual(nextSuperuserIds, currentTelegram?.superuser_ids || [])) {
            telegramPatch.superuser_ids = nextSuperuserIds
        }

        if (!Object.keys(telegramPatch).length) return null

        return {
            value: {
                telegram: telegramPatch,
            } satisfies DeepPartial<AppConfig>,
        }
    }

    async function saveModelConfiguration () {
        saving.models = true

        try {
            const config = await patchConfig({
                api: {
                    agent: buildModelEndpointPatch(modelConfig.agent),
                    utility: buildModelEndpointPatch(modelConfig.utility),
                },
            })
            applyConfig(config)
            showNotice('Model configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save model configuration.'), 'error')
        } finally {
            saving.models = false
        }
    }

    async function saveRetrievalConfiguration () {
        saving.retrieval = true

        try {
            const config = await patchConfig({
                api: {
                    embed: buildEmbedPatch(),
                    rerank: buildRerankPatch(),
                },
            })
            applyConfig(config)
            showNotice('Retrieval configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save retrieval configuration.'), 'error')
        } finally {
            saving.retrieval = false
        }
    }

    async function saveServicesConfiguration () {
        saving.services = true

        try {
            const config = await patchConfig({
                api: {
                    asr: buildAsrPatch(),
                },
                file: {
                    mineru: buildMineruPatch(),
                },
            })
            applyConfig(config)
            showNotice('Service configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save service configuration.'), 'error')
        } finally {
            saving.services = false
        }
    }

    async function saveMcpConfiguration () {
        let patch: Record<string, MCPConfig | null> | null = null

        try {
            validateMcpDrafts()
            patch = buildMcpPatch()
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save MCP configuration.'), 'error')
            return
        }

        if (!patch) {
            showNotice('No MCP changes to save.', 'warning')
            return
        }

        saving.mcp = true

        try {
            const config = await patchConfig({
                mcp: patch,
            } as DeepPartial<AppConfig>)
            applyConfig(config)
            showNotice('MCP configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save MCP configuration.'), 'error')
        } finally {
            saving.mcp = false
        }
    }

    async function saveOnebotConfiguration () {
        const delta = buildOnebotPatch()
        if (!delta) {
            showNotice('No OneBot changes to save.', 'warning')
            return
        }

        saving.onebot = true

        try {
            const config = await patchConfig(delta)
            applyConfig(config)
            showNotice('OneBot configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save OneBot configuration.'), 'error')
        } finally {
            saving.onebot = false
        }
    }

    async function saveTelegramConfiguration () {
        const result = buildTelegramPatch()
        if (!result) {
            showNotice('No Telegram changes to save.', 'warning')
            return
        }

        saving.telegram = true

        try {
            const config = await patchConfig(result.value)
            applyConfig(config)
            showNotice('Telegram configuration saved.')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save Telegram configuration.'), 'error')
        } finally {
            saving.telegram = false
        }
    }

    async function saveCredentialVault () {
        saving.credentials = true

        saveCampusAuth({
            enabled: true,
            studentId: creds.studentId.trim(),
            password: creds.password,
        })

        try {
            const response = await patchCas({
                id: creds.studentId.trim(),
                password: creds.password,
            })
            showNotice(response.message || 'Credential vault saved')
        } catch (error) {
            showNotice(getErrorMessage(error, 'Failed to save CAS credentials.'), 'error')
        } finally {
            saving.credentials = false
        }
    }

    function cleanupShortcutCapture () {
        if (shortcutHandler) {
            window.removeEventListener('keydown', shortcutHandler)
            shortcutHandler = null
        }

        if (recordTimer) {
            clearTimeout(recordTimer)
            recordTimer = null
        }
    }

    function startRecording () {
        cleanupShortcutCapture()
        prefs.recording = true

        shortcutHandler = (event: KeyboardEvent) => {
            event.preventDefault()

            const parts: string[] = []
            if (event.ctrlKey) parts.push('Ctrl')
            if (event.altKey) parts.push('Alt')
            if (event.shiftKey) parts.push('Shift')
            if (event.metaKey) parts.push('Meta')
            if (event.key && !['Control', 'Alt', 'Shift', 'Meta'].includes(event.key)) {
                parts.push(event.key.toUpperCase())
            }

            if (parts.length < 2) return

            prefs.shortcut = parts.join(' + ')
            prefs.recording = false
            cleanupShortcutCapture()
        }

        window.addEventListener('keydown', shortcutHandler)
        recordTimer = window.setTimeout(() => {
            prefs.recording = false
            cleanupShortcutCapture()
        }, 5000)
    }

    function browseWorkspace () {
        showNotice('Workspace picker is not connected yet. You can still edit the path manually.', 'warning')
    }

    function savePreferences () {
        showNotice('Preferences saved')
    }

    function saveNotificationSettings () {
        showNotice('Notification settings saved')
    }

    watch(
        () => appearance.theme,
        (themeName) => {
            setStoredThemePreference(themeName)
            theme.global.name.value = themeName
        }
    )

    onMounted(() => {
        void loadConfigData()
    })

    onBeforeUnmount(() => {
        cleanupShortcutCapture()
    })
</script>
