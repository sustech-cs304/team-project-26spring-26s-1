<template>
    <v-sheet rounded="xl" border color="surface" class="quiz-card my-2 pa-3" width="100%">
        <v-row align="center" class="ma-0 mb-2" density="compact">
            <v-icon size="18" class="mr-2 text-medium-emphasis">mdi-help-circle-outline</v-icon>
            <v-sheet color="transparent" class="quiz-card-title">Quiz</v-sheet>
        </v-row>

        <v-window v-model="activeIndex">
            <v-window-item v-for="(quiz, index) in quizList" :key="`quiz-${index}`" :value="index">
                <div class="quiz-question mb-2">
                    <span class="quiz-question-index">{{ index + 1 }}.</span>
                    <MarkdownRenderer :content="quiz.title" inline class="quiz-inline-md" />
                </div>

                <v-sheet v-if="quiz.description" color="transparent" class="mb-2 text-medium-emphasis">
                    <MarkdownRenderer :content="quiz.description" inline class="quiz-inline-md quiz-description" />
                </v-sheet>

                <v-radio-group v-if="quiz.type === 'single'" v-model="singleAnswer"
                    hide-details class="mb-2 quiz-control-group" density="compact" :disabled="submitted">
                    <v-radio v-for="(choice, choiceIndex) in quiz.choices" :key="`single-${index}-${choiceIndex}`" :value="choiceIndex"
                        density="compact" class="quiz-choice mb-1">
                        <template #label>
                            <v-sheet rounded="lg" :color="optionRowColor(choiceIndex)" class="quiz-choice-label px-2 py-1 ml-1" width="100%"
                                :class="[optionTextClass(choiceIndex), { 'cursor-pointer': !submitted }]"
                                @click.prevent.stop="selectChoice(choiceIndex)">
                                <span class="quiz-choice-prefix">{{ choiceLabel(choiceIndex) }}.</span>
                                <MarkdownRenderer :content="choice" inline class="quiz-inline-md" />
                            </v-sheet>
                        </template>
                    </v-radio>
                </v-radio-group>

                <v-selection-control-group v-else v-model="multipleAnswers" multiple hide-details
                    density="compact" class="quiz-control-group mb-2" :disabled="submitted">
                    <v-checkbox v-for="(choice, choiceIndex) in quiz.choices" :key="`multiple-${index}-${choiceIndex}`"
                        :value="choiceIndex" density="compact" hide-details class="quiz-choice mb-1">
                        <template #label>
                            <v-sheet rounded="lg" :color="optionRowColor(choiceIndex)" class="quiz-choice-label px-2 py-1 ml-1" width="100%"
                                :class="[optionTextClass(choiceIndex), { 'cursor-pointer': !submitted }]"
                                @click.prevent.stop="selectChoice(choiceIndex)">
                                <span class="quiz-choice-prefix">{{ choiceLabel(choiceIndex) }}.</span>
                                <MarkdownRenderer :content="choice" inline class="quiz-inline-md" />
                            </v-sheet>
                        </template>
                    </v-checkbox>
                </v-selection-control-group>

            </v-window-item>
        </v-window>

        <v-row class="quiz-actions ma-0" density="compact">
            <div v-if="hasMultipleQuizzes" class="quiz-pager">
                <v-btn icon="mdi-chevron-left" variant="text" size="x-small" class="quiz-pager-btn"
                    :disabled="!hasPreviousQuiz" aria-label="上一题" @click="goPreviousQuiz" />
                <span class="quiz-pager-count">{{ activeIndex + 1 }} / {{ quizList.length }}</span>
                <v-btn icon="mdi-chevron-right" variant="text" size="x-small" class="quiz-pager-btn"
                    :disabled="!hasNextQuiz" aria-label="下一题" @click="goNextQuiz" />
            </div>
            <v-spacer />
            <Transition name="quiz-feedback-pop" mode="out-in">
                <div v-if="submitFeedback" :key="`feedback-${submitFeedback}`" class="quiz-actions-inner">
                    <v-btn class="quiz-feedback-btn" :class="`quiz-feedback-btn--${submitFeedback}`"
                        size="small" rounded border variant="tonal">
                        <v-icon start size="16">
                            {{ submitFeedback === 'correct' ? 'mdi-check-circle-outline' : 'mdi-close-circle-outline' }}
                        </v-icon>
                        {{ submitFeedback === 'correct' ? '回答正确' : '回答错误' }}
                    </v-btn>
                </div>
                <div v-else key="actions" class="quiz-actions-inner d-flex ga-1 align-center">
                    <v-tooltip v-if="submitted" text="重新作答" location="bottom">
                        <template #activator="{ props: tooltipProps }">
                            <v-btn v-bind="tooltipProps" class="quiz-icon-btn" icon="mdi-refresh" variant="text"
                                size="x-small" :aria-label="'重新作答'" @click="resetCurrent" />
                        </template>
                    </v-tooltip>
                    <v-tooltip v-if="submitted" :text="explanationVisible ? '收起解析' : '查看解析'" location="bottom">
                        <template #activator="{ props: tooltipProps }">
                            <v-btn v-bind="tooltipProps" class="quiz-icon-btn"
                                :icon="explanationVisible ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
                                variant="text" size="x-small"
                                :aria-label="explanationVisible ? '收起解析' : '查看解析'" @click="toggleExplanation" />
                        </template>
                    </v-tooltip>
                    <v-btn v-if="!submitted || hasNextQuiz" class="quiz-submit-btn"
                        :variant="submitted ? 'tonal' : 'flat'" size="small" rounded border
                        @click="submitted ? goNextQuiz() : submitAnswer()" :disabled="!submitted && !canSubmit">
                        <v-icon v-if="!submitted" start size="16">mdi-check-circle-outline</v-icon>
                        <v-icon v-if="submitted" start size="16">mdi-chevron-right</v-icon>
                        {{ submitted ? '下一题' : '提交答案' }}
                    </v-btn>
                </div>
            </Transition>
        </v-row>

        <v-expand-transition>
            <div v-show="submitted && explanationVisible" class="overflow-hidden">
                <v-sheet rounded="lg" border color="transparent" class="px-3 py-2 mt-2">
                    <v-sheet color="transparent" class="mb-2 text-body-2 d-flex align-center flex-wrap ga-1">
                        <v-sheet color="transparent" class="text-body-2 font-weight-medium mr-1">正确答案：</v-sheet>
                        <span v-for="answer in normalizedAnswerLabels" :key="answer"
                            class="font-weight-bold mx-1">
                            {{ answer }}
                        </span>
                    </v-sheet>

                    <v-sheet color="transparent" class="text-body-2">
                        <MarkdownRenderer :content="`**解析：** ${currentQuiz.explanation}`" />
                    </v-sheet>
                </v-sheet>
            </div>
        </v-expand-transition>

        <v-alert v-if="quizList.length === 0" type="warning" variant="tonal" rounded="lg">
            未提供可渲染的题目。
        </v-alert>
    </v-sheet>
</template>

<script setup lang="ts">
    import MarkdownRenderer from '@/components/chat/MarkdownRenderer.vue'
    import type { QuizCardData } from '@/types/conversation'

    interface QuizState {
        single: number | null
        multiple: number[]
        submitted: boolean
        isCorrect: boolean
        explanationVisible: boolean
        feedback: 'correct' | 'incorrect' | null
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
    let feedbackTimer: ReturnType<typeof window.setTimeout> | null = null

    const createState = (): QuizState => ({
        single: null,
        multiple: [],
        submitted: false,
        isCorrect: false,
        explanationVisible: false,
        feedback: null,
    })

    const ensureStates = () => {
        states.value = quizList.value.map((_, i) => states.value[i] ?? createState())
        if (activeIndex.value >= quizList.value.length) {
            activeIndex.value = Math.max(quizList.value.length - 1, 0)
        }
    }

    watch(quizList, ensureStates, { immediate: true, deep: true })
    onBeforeUnmount(() => clearFeedbackTimer())

    const currentQuiz = computed(() => quizList.value[activeIndex.value] as QuizCardData)
    const currentState = computed(() => states.value[activeIndex.value] ?? createState())
    const isSingle = computed(() => currentQuiz.value?.type === 'single')
    const typeLabel = computed(() => isSingle.value ? '单选题' : '多选题')

    const singleAnswer = computed({
        get: () => currentState.value.single,
        set: (value: number | null) => {
            if (currentState.value.submitted) return
            currentState.value.single = value
        },
    })

    const multipleAnswers = computed({
        get: () => currentState.value.multiple,
        set: (value: number[]) => {
            if (currentState.value.submitted) return
            currentState.value.multiple = [...value]
        },
    })

    const normalizedAnswers = computed(() =>
        [...(currentQuiz.value?.correct_choice_indexes ?? [])].sort((a, b) => a - b)
    )
    const normalizedAnswerLabels = computed(() => normalizedAnswers.value.map(choiceLabel))
    const currentAnswers = computed(() => {
        if (isSingle.value) {
            return singleAnswer.value === null ? [] : [singleAnswer.value]
        }
        return [...multipleAnswers.value].sort((a, b) => a - b)
    })

    const submitted = computed(() => currentState.value.submitted)
    const isCorrect = computed(() => currentState.value.isCorrect)
    const explanationVisible = computed(() => currentState.value.explanationVisible)
    const submitFeedback = computed(() => currentState.value.feedback)
    const canSubmit = computed(() => currentAnswers.value.length > 0 && !submitted.value)
    const hasMultipleQuizzes = computed(() => quizList.value.length > 1)
    const hasPreviousQuiz = computed(() => activeIndex.value > 0)
    const hasNextQuiz = computed(() => activeIndex.value < quizList.value.length - 1)

    const clearFeedbackTimer = () => {
        if (!feedbackTimer) return
        window.clearTimeout(feedbackTimer)
        feedbackTimer = null
    }

    const submitAnswer = () => {
        if (!canSubmit.value) return
        const isAnswerCorrect = JSON.stringify(currentAnswers.value) === JSON.stringify(normalizedAnswers.value)
        currentState.value.submitted = true
        currentState.value.isCorrect = isAnswerCorrect
        currentState.value.explanationVisible = false
        currentState.value.feedback = isAnswerCorrect ? 'correct' : 'incorrect'

        const submittedState = currentState.value
        clearFeedbackTimer()
        feedbackTimer = window.setTimeout(() => {
            submittedState.feedback = null
            feedbackTimer = null
        }, 750)
    }

    const resetCurrent = () => {
        clearFeedbackTimer()
        currentState.value.single = null
        currentState.value.multiple = []
        currentState.value.submitted = false
        currentState.value.isCorrect = false
        currentState.value.explanationVisible = false
        currentState.value.feedback = null
    }

    const toggleExplanation = () => {
        currentState.value.explanationVisible = !currentState.value.explanationVisible
    }

    const goNextQuiz = () => {
        if (!hasNextQuiz.value) return
        activeIndex.value += 1
    }

    const goPreviousQuiz = () => {
        if (!hasPreviousQuiz.value) return
        activeIndex.value -= 1
    }

    const selectChoice = (choiceIndex: number) => {
        if (submitted.value) return
        if (isSingle.value) {
            currentState.value.single = choiceIndex
            return
        }

        const selected = new Set(currentState.value.multiple)
        if (selected.has(choiceIndex)) {
            selected.delete(choiceIndex)
        } else {
            selected.add(choiceIndex)
        }
        currentState.value.multiple = [...selected].sort((a, b) => a - b)
    }

    const choiceLabel = (choiceIndex: number) => String.fromCharCode(65 + choiceIndex)

    const optionRowColor = (choiceIndex: number) => {
        return 'transparent'
    }

    const optionTextClass = (choiceIndex: number) => {
        if (!submitted.value) return undefined
        const answerSet = new Set(normalizedAnswers.value)
        const chosenSet = new Set(currentAnswers.value)
        if (answerSet.has(choiceIndex)) return 'text-success font-weight-medium'
        if (chosenSet.has(choiceIndex) && !answerSet.has(choiceIndex)) return 'font-weight-medium'
        return undefined
    }
</script>

<style scoped>
    .quiz-card {
        font-size: 0.92rem;
        line-height: 1.45;
    }

    .quiz-card-title {
        font-size: 0.9rem;
        font-weight: 600;
        line-height: 1.3;
    }

    .quiz-question {
        display: flex;
        align-items: baseline;
        gap: 6px;
        font-size: 0.98rem;
        font-weight: 650;
        line-height: 1.45;
    }

    .quiz-question-index,
    .quiz-choice-prefix {
        flex: 0 0 auto;
        font-weight: 700;
    }

    .quiz-inline-md {
        display: inline;
        line-height: inherit;
    }

    .quiz-inline-md :deep(.md-body) {
        display: inline;
        line-height: inherit;
    }

    .quiz-inline-md :deep(p) {
        display: inline;
        margin: 0;
    }

    .quiz-description {
        font-size: 0.86rem;
    }

    .quiz-choice-label {
        display: inline-flex;
        align-items: baseline;
        gap: 6px;
        min-height: 28px;
        line-height: 1.45;
    }

    .quiz-choice :deep(.v-selection-control__input) {
        width: 28px;
        height: 28px;
    }

    .quiz-choice :deep(.v-selection-control__input .v-icon) {
        font-size: 18px;
    }

    .quiz-choice :deep(.v-label) {
        flex: 1 1 auto;
        min-width: 0;
        opacity: 1;
    }

    .quiz-control-group :deep(.v-selection-control--disabled) {
        opacity: 1;
    }

    .quiz-control-group :deep(.v-selection-control--disabled .v-label) {
        color: rgb(var(--v-theme-on-surface));
    }

    .quiz-actions {
        align-items: center;
        height: 30px;
        min-height: 30px;
        max-height: 30px;
        overflow: visible;
    }

    .quiz-pager {
        display: inline-flex;
        align-items: center;
        height: 28px;
        border-radius: 999px;
        background: rgba(var(--v-theme-on-surface), 0.05);
        overflow: hidden;
        user-select: none;
    }

    .quiz-pager-btn {
        width: 28px;
        min-width: 28px;
        opacity: 0.78;
    }

    .quiz-pager-count {
        min-width: 36px;
        padding: 0 4px;
        text-align: center;
        font-size: 0.78rem;
        font-weight: 650;
        line-height: 28px;
        color: rgba(var(--v-theme-on-surface), 0.78);
        user-select: none;
    }

    .quiz-actions-inner {
        display: flex;
        align-items: center;
        height: 28px;
        min-height: 28px;
        max-height: 28px;
    }

    .quiz-actions :deep(.v-btn) {
        height: 28px !important;
        min-height: 28px !important;
    }

    .quiz-submit-btn {
        font-weight: 650;
    }

    .quiz-icon-btn {
        width: 28px;
        min-width: 28px;
        opacity: 0.72;
    }

    .quiz-icon-btn:hover {
        opacity: 1;
    }

    .quiz-feedback-btn {
        font-weight: 700;
        pointer-events: none;
        animation: quiz-feedback-pulse 0.42s ease;
    }

    .quiz-feedback-btn--correct {
        color: rgb(var(--v-theme-success));
        background: rgba(var(--v-theme-success), 0.1);
        border-color: rgba(var(--v-theme-success), 0.28);
    }

    .quiz-feedback-btn--incorrect {
        color: rgb(var(--v-theme-error));
        background: rgba(var(--v-theme-error), 0.1);
        border-color: rgba(var(--v-theme-error), 0.28);
    }

    .quiz-feedback-pop-enter-active,
    .quiz-feedback-pop-leave-active {
        transition: opacity 0.16s ease, transform 0.16s ease;
    }

    .quiz-feedback-pop-enter-from,
    .quiz-feedback-pop-leave-to {
        opacity: 0;
        transform: translateY(4px) scale(0.94);
    }

    @keyframes quiz-feedback-pulse {
        0% {
            transform: scale(0.92);
        }

        55% {
            transform: scale(1.06);
        }

        100% {
            transform: scale(1);
        }
    }
</style>
