<template>
    <v-sheet rounded="lg" border class="my-2 pa-3 text-body-2" width="100%" max-width="720">
        <v-row align="center" class="ma-0 mb-2" no-gutters>
            <v-icon size="16" color="primary" class="mr-2">mdi-help-circle-outline</v-icon>
            <v-sheet color="transparent" class="font-weight-medium">Quiz</v-sheet>
            <v-spacer />
            <v-chip size="x-small" color="primary" variant="flat">{{ typeLabel }}</v-chip>
        </v-row>

        <v-tabs v-if="quizList.length > 1" v-model="activeIndex" density="compact" color="primary" class="mb-2">
            <v-tab v-for="(item, index) in quizList" :key="`quiz-tab-${index}`" :value="index">
                第 {{ index + 1 }} 题
            </v-tab>
        </v-tabs>

        <v-window v-model="activeIndex" class="mb-2">
            <v-window-item v-for="(quiz, index) in quizList" :key="`quiz-${index}`" :value="index">
                <v-sheet color="transparent" class="mb-2">
                    <MarkdownRenderer :content="`### ${quiz.title}`" />
                </v-sheet>

                <v-sheet v-if="quiz.description" color="transparent" class="mb-2 text-medium-emphasis">
                    <MarkdownRenderer :content="quiz.description" />
                </v-sheet>

                <v-radio-group v-if="quiz.type === 'single'" v-model="singleAnswer" :disabled="submitted"
                    color="primary" hide-details class="mb-2" density="compact">
                    <v-radio v-for="option in quiz.options" :key="`single-${index}-${option.id}`" :value="option.id"
                        density="compact" class="mb-1">
                        <template #label>
                            <v-sheet rounded="lg" class="pa-1 ml-1" :color="optionTone(option.id)">
                                <MarkdownRenderer :content="`**${option.id}.** ${option.content}`" />
                            </v-sheet>
                        </template>
                    </v-radio>
                </v-radio-group>

                <v-selection-control-group v-else v-model="multipleAnswers" multiple color="primary" hide-details
                    density="compact">
                    <v-checkbox v-for="option in quiz.options" :key="`multiple-${index}-${option.id}`"
                        :value="option.id" :disabled="submitted" density="compact" hide-details class="mb-1">
                        <template #label>
                            <v-sheet rounded="lg" class="pa-1 ml-1" :color="optionTone(option.id)">
                                <MarkdownRenderer :content="`**${option.id}.** ${option.content}`" />
                            </v-sheet>
                        </template>
                    </v-checkbox>
                </v-selection-control-group>

                <v-row class="ma-0 ga-1 justify-end mb-1" no-gutters>
                    <v-btn color="primary" variant="flat" size="small" rounded @click="submitAnswer"
                        :disabled="!canSubmit">
                        <v-icon start size="16">mdi-check-circle-outline</v-icon>
                        提交答案
                    </v-btn>
                    <v-btn variant="tonal" size="small" rounded @click="resetCurrent" :disabled="!submitted">
                        <v-icon start size="16">mdi-refresh</v-icon>
                        重新作答
                    </v-btn>
                </v-row>

                <v-expand-transition>
                    <v-sheet v-if="submitted" rounded="lg" border class="pa-3 mt-2">
                        <v-alert :type="isCorrect ? 'success' : 'error'" variant="tonal" rounded="lg" class="mb-2">
                            {{ isCorrect ? '回答正确' : '回答错误' }}
                        </v-alert>

                        <v-sheet color="transparent" class="mb-2 d-flex align-center flex-wrap ga-1">
                            <v-sheet color="transparent"
                                class="text-body-medium font-weight-medium mr-1">正确答案：</v-sheet>
                            <v-chip v-for="answer in normalizedAnswers" :key="`${index}-${answer}`" size="x-small"
                                color="success" variant="flat">
                                {{ answer }}
                            </v-chip>
                        </v-sheet>

                        <v-sheet color="transparent">
                            <MarkdownRenderer :content="`**解析：**\n\n${currentQuiz.explanation}`" />
                        </v-sheet>
                    </v-sheet>
                </v-expand-transition>
            </v-window-item>
        </v-window>

        <v-alert v-if="quizList.length === 0" type="warning" variant="tonal" rounded="lg">
            未提供可渲染的题目。
        </v-alert>
    </v-sheet>
</template>

<script setup lang="ts">
    import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
    import type { QuizCardData } from '@/types/conversation'

    interface QuizState {
        single: string
        multiple: string[]
        submitted: boolean
        isCorrect: boolean
    }

    const props = defineProps<{
        quiz?: QuizCardData
        quizzes?: QuizCardData[]
    }>()

    const quizList = computed(() => {
        if (props.quizzes && props.quizzes.length > 0) return props.quizzes
        if (props.quiz) return [props.quiz]
        return []
    })

    const activeIndex = ref(0)
    const states = ref<QuizState[]>([])

    const createState = (): QuizState => ({
        single: '',
        multiple: [],
        submitted: false,
        isCorrect: false,
    })

    const ensureStates = () => {
        states.value = quizList.value.map((_, i) => states.value[i] ?? createState())
        if (activeIndex.value >= quizList.value.length) {
            activeIndex.value = Math.max(quizList.value.length - 1, 0)
        }
    }

    watch(quizList, ensureStates, { immediate: true, deep: true })

    const currentQuiz = computed(() => quizList.value[activeIndex.value] as QuizCardData)
    const currentState = computed(() => states.value[activeIndex.value] ?? createState())
    const isSingle = computed(() => currentQuiz.value?.type === 'single')
    const typeLabel = computed(() => isSingle.value ? '单选题' : '多选题')

    const singleAnswer = computed({
        get: () => currentState.value.single,
        set: (value: string) => {
            if (currentState.value.submitted) return
            currentState.value.single = value
        },
    })

    const multipleAnswers = computed({
        get: () => currentState.value.multiple,
        set: (value: string[]) => {
            if (currentState.value.submitted) return
            currentState.value.multiple = [...value]
        },
    })

    const normalizedAnswers = computed(() => [...(currentQuiz.value?.answers ?? [])].sort())
    const currentAnswers = computed(() => {
        if (isSingle.value) {
            return singleAnswer.value ? [singleAnswer.value] : []
        }
        return [...multipleAnswers.value].sort()
    })

    const submitted = computed(() => currentState.value.submitted)
    const isCorrect = computed(() => currentState.value.isCorrect)
    const canSubmit = computed(() => currentAnswers.value.length > 0 && !submitted.value)

    const submitAnswer = () => {
        if (!canSubmit.value) return
        currentState.value.submitted = true
        const answers = [...currentAnswers.value].sort()
        currentState.value.isCorrect = JSON.stringify(answers) === JSON.stringify(normalizedAnswers.value)
    }

    const resetCurrent = () => {
        currentState.value.single = ''
        currentState.value.multiple = []
        currentState.value.submitted = false
        currentState.value.isCorrect = false
    }

    const optionTone = (optionId: string) => {
        if (!submitted.value) return undefined
        const answerSet = new Set(normalizedAnswers.value)
        const chosenSet = new Set(currentAnswers.value)
        if (answerSet.has(optionId)) return 'success'
        if (chosenSet.has(optionId) && !answerSet.has(optionId)) return 'error'
        return undefined
    }
</script>