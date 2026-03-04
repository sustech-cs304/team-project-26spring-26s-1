<template>
    <v-container fluid class="d-flex flex-column h-100 pa-0">

        <!-- 消息列表 -->
        <v-sheet ref="scrollEl" color="transparent" class="flex-grow-1 overflow-y-auto">
            <v-container max-width="800" class="px-6 py-4">
                <template v-for="(msg, i) in messages" :key="`${i}-${msg.role}`">

                    <!-- 用户消息 -->
                    <v-row v-if="msg.role === 'user'" justify="end" class="mb-1" density="compact">
                        <v-col cols="auto" class="d-flex align-end ga-2" style="max-width: 83%;">
                            <v-sheet rounded="lg" color="" class="px-3 py-2">
                                <MarkdownRenderer :content="msg.content" />
                            </v-sheet>
                            <v-avatar size="30" class="flex-shrink-0">
                                <v-icon size="16">mdi-account</v-icon>
                            </v-avatar>
                        </v-col>
                    </v-row>

                    <template v-else-if="msg.role === 'assistant'">
                        <!-- 思维链独立行：与消息气泡分离，确保组件挂载时 isActive 已就位 -->
                        <v-row v-if="msg.thinkingSteps && msg.thinkingSteps.length > 0" class="mb-0" density="compact">
                            <v-col class="pa-0" style="min-width: 0; max-width: 100%;">
                                <ThinkingChain :key="`thinking-${i}`" :steps="msg.thinkingSteps"
                                    :is-active="msg.thinkingActive" />
                            </v-col>
                        </v-row>

                        <!-- AI 消息气泡行 -->
                        <v-row v-if="msg.content" class="mb-1 ma-0" density="compact">
                            <v-col class="pa-0" style="min-width: 0; max-width: 100%;">
                                <v-sheet rounded="lg" color="transparent" class="px-0 py-1 pl-3">
                                    <MarkdownRenderer :content="msg.content" />
                                </v-sheet>
                                <v-row align="center" class="ml-2 ga-0" style="opacity: 0.6;">
                                    <span class="text-body-small">{{ msg.time }}</span>
                                    <v-tooltip text="Reload" location="bottom">
                                        <template v-slot:activator="{ props }">
                                            <v-btn v-bind="props" icon="mdi-reload" size="x-small" variant="text"
                                                active-color="primary" />
                                        </template>
                                    </v-tooltip>
                                    <v-tooltip text="Copy" location="bottom">
                                        <template v-slot:activator="{ props }">
                                            <v-btn v-bind="props" icon="mdi-content-copy" size="x-small" variant="text"
                                                @click="copy(msg.content)" />
                                        </template>
                                    </v-tooltip>
                                </v-row>
                            </v-col>
                        </v-row>
                    </template>

                </template>

                <!-- 加载中：仅当无活跃思维链时显示，避免与思维链卡片重叠 -->
                <TypingIndicator v-if="loading && !hasActiveThinking" />
            </v-container>
        </v-sheet>

        <!-- 底部输入区 -->
        <v-sheet elevation="0" color="transparent">
            <v-container max-width="800" class="px-6 pb-5 pt-2">
                <MessageInput v-model="input" :loading="loading" @send="send" />
            </v-container>
        </v-sheet>
    </v-container>
</template>


<style scoped></style>


<script setup lang="ts">
    import MessageInput from '@/components/MessageInput.vue'
    import TypingIndicator from '@/components/TypingIndicator.vue'
    import ThinkingChain from '@/components/ThinkingChain.vue'
    import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
    import type { ThinkingStep } from '@/components/ThinkingChain.vue'

    const route = useRoute()
    const conversationId = computed(() => route.params.conversationId)

    const scrollEl = ref<InstanceType<typeof import('vuetify/components').VSheet> | null>(null)
    const input = ref('')
    const loading = ref(false)

    interface Message {
        role: 'user' | 'assistant'
        content: string
        time: string
        /** 思维链步骤列表，仅 assistant 消息可能有 */
        thinkingSteps?: ThinkingStep[]
        /** 思维链是否仍在推入新节点 */
        thinkingActive?: boolean
    }

    const now = () => new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

    const messages = ref<Message[]>([])

    /** 当前是否有正在活跃的思维链（用于决定是否显示 TypingIndicator） */
    const hasActiveThinking = computed(() =>
        messages.value.some(m => m.thinkingActive)
    )

    // -------------------------
    // 模拟思维链场景预设
    // -------------------------
    interface ThinkingScenario {
        steps: Array<Omit<ThinkingStep, 'time' | 'status'>>
    }

    const THINKING_SCENARIOS: ThinkingScenario[] = [
        {
            steps: [
                { type: 'think', title: '分析用户意图', content: '用户的问题涉及多个知识领域，需要先拆解再逐步作答。' },
                { type: 'search', title: '搜索相关文档', content: '正在检索知识库中与问题相关的参考资料…' },
                { type: 'read', title: '读取检索结果', content: '共返回 12 条结果，开始逐条评估相关性。' },
                { type: 'think', title: '筛选高质量来源', content: '已筛选出 3 条高置信度文档，其余置信度低于阈值 0.72，丢弃。' },
                { type: 'think', title: '提取关键信息', content: '从文档中提取核心论点、数据与引用，整理成结构化摘要。' },
                { type: 'search', title: '补充二次检索', content: '初次检索存在信息空缺，针对子问题发起补充检索…' },
                { type: 'read', title: '读取补充文档', content: '补充文档 2 篇，内容与主题高度相关。' },
                { type: 'think', title: '整合所有搜索结果', content: '合并两轮检索结果，去重后共 5 条有效片段，准备引用。' },
                { type: 'think', title: '构建回答框架', content: '确定回答结构：背景介绍 → 核心要点 → 示例说明 → 总结。' },
                { type: 'code', title: '生成示例代码', content: '根据文档中的接口规范，生成配套代码示例…' },
                { type: 'think', title: '校验示例正确性', content: '代码示例通过静态分析，逻辑自洽，与文档描述一致。' },
                { type: 'think', title: '润色输出内容', content: '对回答进行语言风格统一，确保表述清晰、简洁，适合目标读者。' },
            ],
        },
        {
            steps: [
                { type: 'think', title: '理解任务目标', content: '用户希望实现一个新功能，需要先了解现有代码结构再动手。' },
                { type: 'read', title: '读取项目结构', content: 'src/\n  api/\n  components/\n  pages/\n  stores/' },
                { type: 'read', title: '读取核心文件', content: 'src/api/conversation.ts\nsrc/components/MessageInput.vue\nsrc/pages/c/[conversationId].vue' },
                { type: 'think', title: '分析现有依赖关系', content: 'MessageInput → conversationId.vue → conversation.ts，调用链清晰。' },
                { type: 'search', title: '查询 Vuetify 组件文档', content: '检索 v-window、v-expand-transition 相关 API 与用法示例…' },
                { type: 'think', title: '规划组件设计', content: '新组件采用 Composition API，props 定义 steps 与 isActive，内部管理 expanded 状态。' },
                { type: 'code', title: '生成组件骨架', content: '输出 ThinkingChain.vue 模板结构与 script setup 初稿…' },
                { type: 'think', title: '检查响应式追踪', content: '确认 thinkingSteps 与 thinkingActive 在创建时已预置，避免 Vue 追踪失效。' },
                { type: 'code', title: '补全动画与样式', content: '添加 v-expand-transition、v-window slide 动画，调整 opacity 减弱存在感。' },
                { type: 'think', title: '验证集成方式', content: '思维链行与消息气泡行独立渲染，避免共享 key 导致组件复用错误。' },
                { type: 'think', title: '输出最终方案', content: '所有细节确认完毕，准备输出完整实现代码。' },
            ],
        },
        {
            steps: [
                { type: 'think', title: '分解问题', content: '问题包含 3 个子任务，逐一处理。' },
                { type: 'api', title: '调用天气 API', content: 'GET /v1/weather?city=深圳&unit=metric' },
                { type: 'think', title: '解析天气响应', content: '当前气温 26°C，湿度 78%，天气状况：多云。' },
                { type: 'api', title: '调用地图 API', content: 'GET /v1/geocode?address=深圳市南山区' },
                { type: 'think', title: '解析地理坐标', content: '经度 113.93°E，纬度 22.53°N，解析成功。' },
                { type: 'tool', title: '计算日出日落时间', content: '基于坐标与日期，调用天文工具计算…\n日出：06:31  日落：18:14' },
                { type: 'think', title: '汇总子任务结果', content: '三个子任务均已完成，整理为统一格式准备输出。' },
                { type: 'think', title: '格式化最终回答', content: '将数据转为用户友好的自然语言描述，附带数据来源说明。' },
            ],
        },
        {
            steps: [
                { type: 'think', title: '识别计算类任务', content: '用户提出了一道多步骤数学推导题，需要分步求解。' },
                { type: 'tool', title: '第一步：展开表达式', content: '(a+b)² = a² + 2ab + b²，展开完成。' },
                { type: 'think', title: '检验展开结果', content: '逐项核对系数，展开正确。' },
                { type: 'tool', title: '第二步：代入数值', content: 'a=3, b=4 → 9 + 24 + 16 = 49' },
                { type: 'think', title: '验证计算结果', content: '49 = 7²，与直接计算 (3+4)²=49 一致，验证通过。' },
                { type: 'search', title: '检索相关定理', content: '搜索二项式定理的一般形式与应用场景…' },
                { type: 'think', title: '补充拓展说明', content: '找到 2 篇相关文献，提炼出有助于理解的延伸知识点。' },
                { type: 'think', title: '组织完整解答', content: '按"解题过程 → 验证 → 拓展"结构组织最终回答。' },
                { type: 'think', title: '语言风格检查', content: '确认措辞准确，公式格式符合 KaTeX 规范，可直接渲染。' },
            ],
        },
    ]

    /**
     * 模拟 SSE 推送思维链节点（随机场景，每隔 700ms 推一个节点）
     * 返回 Promise，在所有节点推完后 resolve
     */
    const simulateThinkingSSE = async (targetMsg: Message): Promise<void> => {
        // 随机决定是否触发思维链（约 60% 概率）
        if (Math.random() > 0.6) return

        const scenario = THINKING_SCENARIOS[Math.floor(Math.random() * THINKING_SCENARIOS.length)]

        // thinkingSteps 在创建时已预置为 []，直接置 active（响应式已追踪）
        targetMsg.thinkingActive = true

        for (const stepDef of (scenario?.steps ?? [])) {
            // 模拟 SSE 推送间隔
            await new Promise(r => setTimeout(r, 400 + Math.random() * 200))

            const step: ThinkingStep = {
                ...stepDef,
                status: 'running',
                time: now(),
            }
            // thinkingSteps 已是响应式数组，push 可被追踪
            targetMsg.thinkingSteps!.push(step)
            await scrollToBottom()

            // 短暂停留后标记为完成：通过响应式数组索引修改，确保视图更新
            await new Promise(r => setTimeout(r, 300 + Math.random() * 100))
            const idx = targetMsg.thinkingSteps!.length - 1
            targetMsg.thinkingSteps![idx]!.status = 'done'
        }

        targetMsg.thinkingActive = false
    }

    const scrollToBottom = async () => {
        await nextTick()
        const el = scrollEl.value?.$el as HTMLElement | undefined
        if (el) el.scrollTop = el.scrollHeight
    }

    // 处理对话核心逻辑
    const processMessage = async (text: string) => {
        messages.value.push({ role: 'user', content: text, time: now() })
        await scrollToBottom()

        loading.value = true
        await scrollToBottom()

        // 预先创建 assistant 消息占位，thinkingSteps/thinkingActive 必须预置以保证响应式追踪
        const assistantMsg: Message = {
            role: 'assistant',
            content: '',
            time: '',
            thinkingSteps: [],
            thinkingActive: false,
        }
        messages.value.push(assistantMsg)

        // push 后通过索引取响应式代理对象，确保 Vue 能追踪后续属性变更
        const msgIndex = messages.value.length - 1
        const reactiveMsg = messages.value[msgIndex]!

        // 思维链 SSE 模拟与 API 调用并行运行
        await Promise.all([
            simulateThinkingSSE(reactiveMsg),
            // TODO: 接入真实 API（这里用 setTimeout 模拟网络延迟）
            new Promise(r => setTimeout(r, 1200 + Math.random() * 800)),
        ])

        loading.value = false
        reactiveMsg.content = `模拟回复 你说的是："${text}"`
        reactiveMsg.time = now()
        await scrollToBottom()
    }

    const loadConversation = async () => {
        messages.value = []
        loading.value = true

        // 模拟网络延迟
        await new Promise(r => setTimeout(r, 600))

        const state = history.state as { prompt?: string }
        if (state.prompt) {
            const prompt = state.prompt
            history.replaceState({ ...history.state, prompt: undefined }, '')
            loading.value = false
            await processMessage(prompt)
        } else {
            // 简单的随机生成不同对话演示
            const random = Math.random()
            if (random > 0.5) {
                messages.value = [
                    { role: 'user', content: 'Vue 3 的生命周期有哪些？', time: '09:30' },
                    { role: 'assistant', content: 'Vue 3 的主要生命周期钩子包括 onMounted, onUpdated, onUnmounted 等，配合 Composition API 使用。', time: '09:31' },
                ]
            } else {
                messages.value = [
                    { role: 'user', content: 'Rust 语言适合写前端吗？', time: '14:20' },
                    { role: 'assistant', content: 'Rust 可以通过 WebAssembly (Wasm) 编写前端高性能模块，通常配合 Yew 或 Leptos 框架使用。', time: '14:21' },
                ]
            }
            loading.value = false
            await scrollToBottom()
        }
    }

    // 初始加载
    onMounted(() => {
        loadConversation()
    })

    // 监听路由参数变化，切换对话时重新加载
    watch(conversationId, () => {
        loadConversation()
    })

    const send = async () => {
        const text = input.value.trim()
        if (!text) return
        input.value = ''
        await processMessage(text)
    }

    const copy = (text: string) => navigator.clipboard.writeText(text)
</script>
