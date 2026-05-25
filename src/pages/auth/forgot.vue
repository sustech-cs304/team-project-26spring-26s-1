<template>
  <v-sheet color="background" class="auth-page h-100 d-flex align-center justify-center">
    <v-sheet color="transparent" width="100%" max-width="440" class="auth-shell px-4">
      <v-card rounded="lg" variant="flat" border class="auth-panel">
        <div class="auth-panel-header">
          <div class="d-flex align-center ga-2 min-width-0">
            <v-avatar size="30" rounded="lg" class="auth-header-icon">
              <v-icon icon="mdi-lock-question" size="18" />
            </v-avatar>
            <div class="min-width-0">
              <div class="auth-title text-truncate">Reset your password</div>
              <div class="auth-subtitle">Verify your email before setting a new password.</div>
            </div>
          </div>
        </div>

        <div class="auth-panel-body">
          <v-form ref="formRef" @submit.prevent="onSubmit">
            <p class="auth-helper mb-4">
              Enter your user account's verified email address and we will send you a verification code to reset your
              password.
            </p>

            <AuthTextField v-model="form.email" label="Email" placeholder="Enter your email address."
              icon="mdi-email-outline" :rules="emailRules">
              <template #append v-if="form.email.trim()">
                <v-btn :disabled="countdown > 0 || codeLoading" height="40" min-width="76" variant="tonal"
                  rounded="lg" size="small" class="text-none" @click="sendCode">
                  {{ countdown > 0 ? `${countdown}s` : 'Send' }}
                </v-btn>
              </template>
            </AuthTextField>

            <AuthTextField v-model="form.verificationCode" label="Verification Code"
              placeholder="Enter verification code" icon="mdi-shield-key-outline" :rules="requiredRules" />

            <AuthTextField v-model="form.newPassword" label="New Password" placeholder="At least 6 characters"
              icon="mdi-lock-outline" isPassword :rules="passwordRules" />
            <AuthTextField v-model="form.confirmPassword" label="Confirm Password"
              placeholder="Re-enter your new password" icon="mdi-lock-check-outline" isPassword
              :rules="confirmPasswordRules" />

            <v-btn type="submit" block size="small" height="40" variant="tonal" rounded="lg"
              class="text-none auth-submit-btn mb-2" :loading="submitLoading" :disabled="submitLoading">
              Reset Password
              <v-icon end size="16">mdi-arrow-right</v-icon>
            </v-btn>

            <v-btn block variant="text" size="small" rounded="lg" class="text-none auth-back-btn"
              @click="router.push('/auth')">
              <v-icon start size="16">mdi-arrow-left</v-icon>
              Back to Sign In
            </v-btn>
          </v-form>
        </div>
      </v-card>

      <v-sheet color="transparent" class="auth-note mt-3">
        <v-icon icon="mdi-shield-check-outline" size="16" class="mr-2" />
        <span>Reset link will be sent to your campus email</span>
      </v-sheet>
    </v-sheet>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="4000" location="top">
      {{ snackbar.text }}
    </v-snackbar>
  </v-sheet>
</template>

<script setup lang="ts">
  import { ref, reactive, computed, onUnmounted } from 'vue'
  import { useRouter } from 'vue-router'
  import AuthTextField from '@/components/AuthTextField.vue'
  import { sendResetPasswordCode, resetPassword } from '@/api/auth'

  const router = useRouter()
  const formRef = ref()
  const countdown = ref(0)
  let timer: ReturnType<typeof setInterval> | null = null

  const form = reactive({
    email: '',
    verificationCode: '',
    newPassword: '',
    confirmPassword: '',
  })

  const submitLoading = ref(false)
  const codeLoading = ref(false)
  const snackbar = reactive({
    show: false,
    text: '',
    color: 'success' as 'success' | 'error',
  })

  const requiredRules = [
    (v: string) => !!v.trim() || 'This field is required'
  ]

  const emailRules = [
    (v: string) => !!v.trim() || 'Email is required',
    (v: string) => /.+@.+\..+/.test(v) || 'Please enter a valid email address'
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
    (v: string) => v === form.newPassword || 'Passwords do not match',
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

  async function sendCode () {
    if (codeLoading.value || countdown.value > 0) return

    const emailValid = emailRules.every(rule => rule(form.email) === true)
    if (!emailValid) return

    codeLoading.value = true
    startCountdown(60)

    try {
      await sendResetPasswordCode({ email: form.email.trim() })
      showSnackbar('Verification code sent')
    } catch (error) {
      stopCountdown()
      showSnackbar(error instanceof Error ? error.message : 'Failed to send verification code', 'error')
    } finally {
      codeLoading.value = false
    }
  }

  async function onSubmit () {
    const { valid } = await formRef.value.validate()
    if (!valid) return
    submitLoading.value = true

    try {
      await resetPassword({
        email: form.email,
        newpassword: form.newPassword,
        verificationCode: form.verificationCode,
      })
      router.push('/auth')
    } catch (error) {
      showSnackbar(error instanceof Error ? error.message : 'Reset failed', 'error')
    } finally {
      submitLoading.value = false
    }
  }

  onUnmounted(() => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })
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

  .auth-subtitle,
  .auth-helper,
  .auth-note {
    color: rgba(var(--v-theme-on-surface), 0.58);
    font-size: 0.75rem;
    line-height: 1rem;
  }

  .auth-subtitle {
    margin-top: 2px;
  }

  .auth-panel-body {
    padding: 14px;
  }

  .auth-helper {
    margin: 0;
  }

  .auth-submit-btn {
    font-weight: 650;
  }

  .auth-back-btn {
    color: rgba(var(--v-theme-on-surface), 0.72) !important;
  }

  .auth-note {
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
  }

  @media (max-height: 720px) {
    .auth-shell {
      margin-top: 0;
    }
  }
</style>
