<template>
    <v-sheet color="background" class="auth-page h-100 d-flex align-center justify-center">
        <v-sheet color="transparent" width="100%" max-width="480" class="auth-shell px-4">
            <v-card rounded="lg" variant="flat" border class="auth-panel">
                <div class="auth-panel-header">
                    <div class="d-flex align-center ga-2 min-width-0">
                        <v-avatar size="30" rounded="lg" class="auth-header-icon">
                            <v-icon icon="mdi-account-outline" size="18" />
                        </v-avatar>
                        <div class="min-width-0">
                            <div class="auth-title text-truncate">
                                {{ isSignIn ? 'Sign in to OpenCrab' : 'Register for OpenCrab' }}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="auth-panel-body">
                    <v-btn-toggle v-model="isSignIn" class="auth-mode-toggle mb-4" rounded="lg" mandatory>
                        <v-btn :value="true" class="text-none flex-grow-1" size="small" variant="tonal">
                            Sign In
                        </v-btn>
                        <v-btn :value="false" class="text-none flex-grow-1" size="small" variant="tonal">
                            Register
                        </v-btn>
                    </v-btn-toggle>

                    <v-form v-if="isSignIn" ref="signInFormRef" @submit.prevent="onSignIn">
                        <AuthTextField v-model="signInForm.email" label="Email address" placeholder="user@gmail.com"
                            icon="mdi-email-outline" :rules="emailRules" />
                        <AuthTextField v-model="signInForm.password" label="Password" placeholder="Enter password"
                            icon="mdi-lock-outline" isPassword :rules="requiredRules">
                            <template #label-append>
                                <v-btn variant="text" size="x-small" class="text-none auth-inline-action"
                                    @click="router.push('/auth/forgot')">
                                    Forgot password?
                                </v-btn>
                            </template>
                        </AuthTextField>
                        <v-btn type="submit" block size="small" height="40" variant="tonal" rounded="lg"
                            class="text-none auth-submit-btn" :loading="signInLoading" :disabled="signInLoading">
                            Sign In
                            <v-icon end size="16">mdi-arrow-right</v-icon>
                        </v-btn>
                    </v-form>

                    <v-form v-else ref="signUpFormRef" @submit.prevent="onSignUp">
                        <AuthTextField v-model="signUpForm.email" label="Email" placeholder="user@gmail.com"
                            icon="mdi-email-outline" :rules="emailRules">
                            <template #append v-if="signUpForm.email.trim()">
                                <v-btn :disabled="countdown > 0 || codeLoading" height="40" min-width="76"
                                    variant="tonal" rounded="lg" size="small" class="text-none" @click="sendCode">
                                    {{ countdown > 0 ? `${countdown}s` : 'Send' }}
                                </v-btn>
                            </template>
                        </AuthTextField>
                        <v-row density="compact" class="my-n1">
                            <v-col cols="12" sm="6" class="py-1">
                                <AuthTextField v-model="signUpForm.username" label="Username"
                                    placeholder="Enter username" icon="mdi-account-outline" :rules="usernameRules" />
                            </v-col>
                            <v-col cols="12" sm="6" class="py-1">
                                <AuthTextField v-model="signUpForm.verificationCode" label="Verification Code"
                                    placeholder="Enter code" icon="mdi-shield-key-outline" :rules="requiredRules" />
                            </v-col>
                        </v-row>

                        <AuthTextField v-model="signUpForm.password" label="Password"
                            placeholder="At least 6 characters" icon="mdi-lock-outline" isPassword
                            :rules="passwordRules" />
                        <AuthTextField v-model="signUpForm.confirmPassword" label="Confirm Password"
                            placeholder="Re-enter your password" icon="mdi-lock-outline" isPassword
                            :rules="confirmPasswordRules" />
                        <v-btn type="submit" block size="small" height="40" variant="tonal" rounded="lg"
                            class="text-none auth-submit-btn mt-1" :loading="signUpLoading" :disabled="signUpLoading">
                            Create Account
                            <v-icon end size="16">mdi-arrow-right</v-icon>
                        </v-btn>
                    </v-form>
                </div>
            </v-card>

            <v-sheet color="transparent" class="auth-note mt-3">
                <v-icon icon="mdi-shield-check-outline" size="16" class="mr-2" />
                <span>Credentials are stored locally and never sent to third-party services</span>
            </v-sheet>
        </v-sheet>

        <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="4000" location="top">
            {{ snackbar.text }}
        </v-snackbar>
    </v-sheet>
</template>


<script setup lang="ts">
    import { ref, reactive, computed } from 'vue'
    import axios, { type AxiosError } from 'axios'
    import { useRoute, useRouter } from 'vue-router'
    import AuthTextField from '@/components/AuthTextField.vue'
    import { login, register, sendRegisterCode } from '@/api/auth'
    import { useAuthStore } from '@/stores/auth'
    import { normalizeReturnTo } from '@/utils/authSession'

    const route = useRoute()
    const router = useRouter()
    const authStore = useAuthStore()
    const isSignIn = ref(true)
    const signInFormRef = ref()
    const signUpFormRef = ref()
    const countdown = ref(0)
    const codeLoading = ref(false)
    const signInLoading = ref(false)
    const snackbar = reactive({
        show: false,
        text: '',
        color: 'success' as 'success' | 'error',
    })
    let timer: ReturnType<typeof setInterval> | null = null

    const signInForm = reactive({
        email: '',
        password: ''
    })

    const signUpForm = reactive({
        email: '',
        username: '',
        password: '',
        confirmPassword: '',
        verificationCode: ''
    })

    type ApiErrorBody = {
        detail?: unknown
        message?: unknown
    }

    const returnToPath = computed(() => {
        const target = normalizeReturnTo(route.query.returnTo, '/')
        if (target.startsWith('/auth')) {
            return '/'
        }
        return target
    })

    // Validation rules
    const requiredRules = [
        (v: string) => !!v.trim() || 'This field is required'
    ]

    const emailRules = [
        (v: string) => !!v.trim() || 'Email is required',
        (v: string) => /.+@.+\..+/.test(v) || 'Please enter a valid email address'
    ]

    const usernameRules = [
        (v: string) => !!v.trim() || 'Username is required',
        (v: string) => v.trim().length < 20 || 'Username must be less than 10 characters',
        (v: string) => /^[a-zA-Z0-9]+$/.test(v.trim()) || 'Username can only contain letters and numbers',
    ]

    const passwordRules = [
        (v: string) => !!v || 'Password is required',
        (v: string) => v.length >= 6 || 'Password must be at least 6 characters',
        (v: string) => v.length <= 20 || 'Password must be at most 20 characters',
        (v: string) => /[a-zA-Z]/.test(v) || 'Password must contain at least one letter',
        (v: string) => /[0-9]/.test(v) || 'Password must contain at least one number',
    ]

    const confirmPasswordRules = computed(() => [
        (v: string) => !!v || 'Please confirm your password',
        (v: string) => v === signUpForm.password || 'Passwords do not match'
    ])

    function startCountdown (seconds = 60) {
        if (timer) {
            clearInterval(timer)
            timer = null
        }

        countdown.value = seconds
        timer = setInterval(() => {
            countdown.value--
            if (countdown.value <= 0 && timer) {
                clearInterval(timer)
                timer = null
            }
        }, 1000)
    }

    function stopCountdown () {
        if (timer) {
            clearInterval(timer)
            timer = null
        }
        countdown.value = 0
    }

    function showSnackbar (text: string, color: 'success' | 'error' = 'success') {
        snackbar.text = text
        snackbar.color = color
        snackbar.show = true
    }

    function stringifyApiErrorDetail (detail: unknown): string {
        if (typeof detail === 'string') return detail
        if (Array.isArray(detail)) {
            return detail
                .map((item) => {
                    if (typeof item === 'string') return item
                    if (item && typeof item === 'object' && 'msg' in item) {
                        return String((item as { msg?: unknown }).msg)
                    }
                    return ''
                })
                .filter(Boolean)
                .join('；')
        }
        if (detail && typeof detail === 'object' && 'message' in detail) {
            return String((detail as { message?: unknown }).message)
        }
        return ''
    }

    function getApiErrorMessage (error: unknown, fallback: string): string {
        if (!axios.isAxiosError<ApiErrorBody>(error)) {
            return error instanceof Error ? error.message : fallback
        }

        const data = error.response?.data
        const apiMessage = stringifyApiErrorDetail(data?.detail) || stringifyApiErrorDetail(data?.message)
        return apiMessage || fallback
    }

    function getRegisterErrorMessage (error: unknown): string {
        if (!axios.isAxiosError<ApiErrorBody>(error)) {
            return error instanceof Error ? error.message : '注册失败，请稍后重试。'
        }

        const status = error.response?.status
        const apiMessage = getApiErrorMessage(error, '')
        const normalizedMessage = apiMessage.toLowerCase()

        if (status === 409 || normalizedMessage.includes('already exists') || normalizedMessage.includes('已存在')) {
            return '账号已存在，请直接登录或更换邮箱。'
        }
        if (status === 422) {
            return apiMessage || '验证码无效或已过期，请检查后重试。'
        }
        if (status === 500) {
            return '服务异常，请稍后重试。'
        }
        return apiMessage || '注册失败，请稍后重试。'
    }

    async function sendCode () {
        if (codeLoading.value || countdown.value > 0) return

        // Check if email is valid before sending
        const emailValid = emailRules.every(rule => rule(signUpForm.email) === true)
        if (!emailValid) return

        codeLoading.value = true
        startCountdown(60)

        try {
            await sendRegisterCode({ email: signUpForm.email })
            showSnackbar('Verification code sent')
        } catch (error) {
            stopCountdown()
            showSnackbar(getApiErrorMessage(error, '验证码发送失败，请稍后重试。'), 'error')
        } finally {
            codeLoading.value = false
        }
    }

    async function onSignIn () {
        const { valid } = await signInFormRef.value.validate()
        if (!valid) return
        signInLoading.value = true

        try {
            await login({
                email: signInForm.email,
                password: signInForm.password,
            })

            await authStore.refreshCurrentUser()
            await router.replace(returnToPath.value || '/')
        } catch (error) {
            const axiosError = error as AxiosError<ApiErrorBody>
            const status = axiosError.response?.status
            let message = ''

            if (status === 400) {
                message = '登录失败：邮箱或密码错误，请检查后重试。'
            } else if (status === 500) {
                message = '服务异常，请稍后重试。'
            } else {
                message = getApiErrorMessage(error, '登录失败，请稍后重试。')
            }
            showSnackbar(message, 'error')
        } finally {
            signInLoading.value = false
        }
    }

    const signUpLoading = ref(false)

    async function onSignUp () {
        const { valid } = await signUpFormRef.value.validate()
        if (!valid) return
        signUpLoading.value = true

        try {
            await register({
                email: signUpForm.email,
                username: signUpForm.username.trim(),
                password: signUpForm.password,
                verificationCode: signUpForm.verificationCode,
            })
            // 注册成功后切换到登录表单
            isSignIn.value = true
            signInForm.email = signUpForm.email
            showSnackbar('Account created. Please sign in.')
        } catch (error) {
            showSnackbar(getRegisterErrorMessage(error), 'error')
        } finally {
            signUpLoading.value = false
        }
    }
</script>

<style scoped>
    .auth-page {
        min-height: 100%;
        background: rgb(var(--v-theme-background));
    }

    .auth-shell {
        margin-top: -24px;
    }

    .auth-panel {
        overflow: hidden;
        background: rgba(var(--v-theme-on-surface), 0.018) !important;
        border: 1px solid rgba(var(--v-border-color), 0.16) !important;
    }

    .min-width-0 {
        min-width: 0;
    }

    .auth-panel-header {
        padding: 12px 14px;
        border-bottom: 1px solid rgba(var(--v-border-color), 0.14);
    }

    .auth-header-icon {
        background: rgba(var(--v-theme-on-surface), 0.055);
        color: rgba(var(--v-theme-on-surface), 0.78);
    }

    .auth-title {
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.35rem;
    }

    .auth-subtitle {
        margin-top: 2px;
        color: rgba(var(--v-theme-on-surface), 0.58);
        font-size: 0.75rem;
        line-height: 1rem;
    }

    .auth-panel-body {
        padding: 14px;
    }

    .auth-mode-toggle {
        display: flex;
        width: 100%;
        gap: 4px;
        background: transparent;
    }

    .auth-mode-toggle :deep(.v-btn) {
        min-width: 0;
        border-radius: 8px !important;
        background: rgba(var(--v-theme-on-surface), 0.035);
        font-size: 0.8125rem;
        font-weight: 600;
        letter-spacing: 0;
    }

    .auth-mode-toggle :deep(.v-btn.v-btn--active) {
        background: rgba(var(--v-theme-on-surface), 0.08);
        color: rgb(var(--v-theme-on-surface));
    }

    .auth-inline-action {
        color: rgba(var(--v-theme-on-surface), 0.72) !important;
    }

    .auth-submit-btn {
        font-weight: 650;
    }

    .auth-note {
        display: flex;
        align-items: center;
        justify-content: center;
        color: rgba(var(--v-theme-on-surface), 0.58);
        font-size: 0.75rem;
        line-height: 1rem;
        text-align: center;
    }

    @media (max-height: 720px) {
        .auth-shell {
            margin-top: 0;
        }
    }
</style>
