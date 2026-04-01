<template>
    <v-container class="py-8">
        <v-row justify="center">
            <v-col cols="12" md="10" lg="8">
                <v-sheet color="transparent" class="mb-6">
                    <v-sheet color="transparent" class="text-h4 font-weight-bold">Quiz 卡片调试页</v-sheet>
                    <v-sheet color="transparent" class="text-body-1 text-medium-emphasis mt-2">
                        临时模拟聊天区域中的 quiz 卡片消息渲染效果（单卡片内可切换多题）。
                    </v-sheet>
                </v-sheet>

                <v-card rounded="xl" class="pa-4 pa-sm-6" variant="outlined">
                    <v-sheet color="transparent" class="text-subtitle-1 font-weight-medium mb-4">聊天框临时预览</v-sheet>

                    <v-sheet rounded="xl" border color="surface" class="pa-4">
                        <v-row no-gutters class="ga-3" align="start">
                            <v-avatar size="34" color="surface-variant" class="flex-shrink-0">
                                <v-icon size="18">mdi-robot-outline</v-icon>
                            </v-avatar>

                            <QuizCardMessage :quizzes="quizExamples" />
                        </v-row>
                    </v-sheet>
                </v-card>
            </v-col>
        </v-row>
    </v-container>
</template>

<script setup lang="ts">
    import QuizCardMessage from '@/components/chat/QuizCardMessage.vue'
    import type { QuizCardData } from '@/types/conversation'

    const quizExamples: QuizCardData[] = [
        {
            title: 'Vue 组件通信中，父组件向子组件传递数据通常使用什么方式？',
            description: '请选择最常见且最符合 **Vue 单向数据流** 设计的做法。',
            type: 'single',
            options: [
                { id: 'A', content: '通过 props 向下传递数据' },
                { id: 'B', content: '通过 emit 向下传递数据' },
                { id: 'C', content: '通过 slot 直接修改子组件内部状态' },
                { id: 'D', content: '通过 computed 自动写入子组件数据' },
            ],
            answers: ['A'],
            explanation: '在 Vue 中，父组件向子组件传值的标准方式是 `props`。`emit` 通常用于子组件向父组件发送事件。',
        },
        {
            title: '以下哪些做法有助于提升前端工程的可维护性？',
            description: '这是一个**多选题**，请选择所有合理选项。',
            type: 'multiple',
            options: [
                { id: 'A', content: '拆分可复用组件，避免页面逻辑过于臃肿' },
                { id: 'B', content: '为核心数据结构定义清晰的 TypeScript 类型' },
                { id: 'C', content: '把所有业务逻辑都直接写进模板表达式中' },
                { id: 'D', content: '为关键交互建立统一状态管理或 composable' },
            ],
            answers: ['A', 'B', 'D'],
            explanation: '组件拆分、类型约束、逻辑抽离都能提升可维护性；将复杂业务逻辑塞进模板通常会降低可读性与可测试性。',
        },
        {
            title: '已知函数 $f(x) = x^2 + 2x + 1$，下列说法正确的是？',
            description: '提示：可先化简为 $f(x) = (x+1)^2$。',
            type: 'single',
            options: [
                { id: 'A', content: '$f(x)$ 的最小值为 $0$，在 $x=-1$ 取得' },
                { id: 'B', content: '$f(x)$ 的最小值为 $-1$，在 $x=1$ 取得' },
                { id: 'C', content: '$f(x)$ 在全体实数上单调递减' },
                { id: 'D', content: '$f(0)=0$' },
            ],
            answers: ['A'],
            explanation: '因为 $f(x)=(x+1)^2\\ge 0$，当且仅当 $x=-1$ 时等号成立，所以最小值是 $0$。',
        },
        {
            title: '关于复杂度与常见排序，以下哪些表述正确？',
            description: '请结合平均复杂度判断（可多选）。',
            type: 'multiple',
            options: [
                { id: 'A', content: '归并排序平均时间复杂度为 $O(n\\log n)$' },
                { id: 'B', content: '快速排序最坏时间复杂度可能退化到 $O(n^2)$' },
                { id: 'C', content: '冒泡排序平均时间复杂度为 $O(\\log n)$' },
                { id: 'D', content: '堆排序平均时间复杂度为 $O(n\\log n)$' },
            ],
            answers: ['A', 'B', 'D'],
            explanation: '归并、堆排平均复杂度均为 $O(n\\log n)$；快排在极端划分下可退化到 $O(n^2)$；冒泡排序平均是 $O(n^2)$。',
        },
        {
            title: '下面这段 Markdown 与公式说明中，哪项说法正确？',
            description: '块级公式示例：\n\n$$\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}$$\n\n并且可以使用 `code`、**加粗**、*斜体*。',
            type: 'single',
            options: [
                { id: 'A', content: '上式是等比数列求和公式' },
                { id: 'B', content: '上式是前 $n$ 个正整数求和公式' },
                { id: 'C', content: '上式恒等于 $n^2$' },
                { id: 'D', content: '该公式只在 $n$ 为偶数时成立' },
            ],
            answers: ['B'],
            explanation: '公式 $\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}$ 对任意正整数 $n$ 都成立，表示前 $n$ 个正整数的和。',
        },
    ]
</script>