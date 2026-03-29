<template>
  <v-container class="fill-height d-flex align-center justify-center">
    <v-row justify="center">
      <v-col cols="12" sm="10" md="8" lg="6" xl="4">
        <div class="d-flex justify-center mb-6">
          <v-avatar size="56">
            <v-icon icon="mdi-lock-question" size="52" />
          </v-avatar>
        </div>

        <v-card class="pa-4" color="grey-darken-4" rounded="lg">
          <div class="d-flex align-center justify-center mb-4 text-center">
            <v-icon icon="mdi-email-fast-outline" color="cyan-darken-2" size="24" class="mr-2" />
            <span class="text-body-1 font-weight-medium">Reset your password</span>
          </div>

          <v-form ref="formRef" @submit.prevent="onSubmit">
            <p class="text-body-large text-grey mb-4 text-center">
              Enter your user account's verified email address and we will send you a verification code to reset your
              password.
            </p>

            <AuthTextField v-model="form.email" label="Email" placeholder="Enter your email address."
              icon="mdi-email-outline" :rules="emailRules">
              <template #append v-if="form.email.trim()">
                <v-btn :disabled="countdown > 0 || codeLoading" :loading="codeLoading" height="56" min-width="100"
                  variant="tonal" color="cyan-darken-2" @click="sendCode">
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

            <v-alert v-if="errorMsg" type="error" variant="tonal" class="mb-4">
              {{ errorMsg }}
            </v-alert>

            <v-btn type="submit" block size="large" color="cyan-darken-2" class="text-none mb-3"
              :loading="submitLoading" :disabled="submitLoading">
              Reset Password
              <v-icon end>mdi-arrow-right</v-icon>
            </v-btn>

            <v-btn block variant="text" class="text-none" color="grey" @click="router.push('/auth')">
              <v-icon start>mdi-arrow-left</v-icon>
              Back to Sign In
            </v-btn>
          </v-form>
        </v-card>

        <div class="d-flex align-center justify-center mt-6 text-grey">
          <v-icon icon="mdi-shield-check-outline" size="18" class="mr-2" color="teal" />
          <span class="text-body-large">Reset link will be sent to your campus email</span>
        </div>
      </v-col>
    </v-row>
  </v-container>
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
  const errorMsg = ref('')

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

  async function sendCode () {
    if (codeLoading.value || countdown.value > 0) return

    const emailValid = emailRules.every(rule => rule(form.email) === true)
    if (!emailValid) return

    errorMsg.value = ''
    codeLoading.value = true

    try {
      await sendResetPasswordCode({ email: form.email.trim() })
      startCountdown(60)
    } catch (error) {
      errorMsg.value = error instanceof Error ? error.message : 'Failed to send verification code'
    } finally {
      codeLoading.value = false
    }
  }

  async function onSubmit () {
    const { valid } = await formRef.value.validate()
    if (!valid) return
    errorMsg.value = ''
    submitLoading.value = true

    try {
      await resetPassword({
        email: form.email,
        newpassword: form.newPassword,
        verificationCode: form.verificationCode,
      })
      router.push('/auth')
    } catch (error) {
      errorMsg.value = error instanceof Error ? error.message : 'Reset failed'
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
