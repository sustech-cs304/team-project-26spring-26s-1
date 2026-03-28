<template>
  <v-container class="fill-height d-flex align-center justify-center ">
    <v-row justify="center" >
        <v-col cols="12" sm="10" md="8" lg="6" xl="4">
            <div class=" d-flex justify-center mb-6">
                <v-avatar size="56">
                    <v-icon icon="mdi-account" size="52" />
                </v-avatar>
            </div>

            <div class="d-flex justify-center mb-4" v-if="isSignIn">
                <div class="d-flex align-center">
                    <span class="font-weight-bold" style="font-size: 1.5rem;">Sign in to OpenCrab</span>
                </div>
            </div>

            <div class="d-flex justify-center mb-4" v-else>
                <div class="d-flex align-center">
                    <span class="font-weight-bold" style="font-size: 1.5rem;">Register for OpenCrab</span>
                </div>
            </div>
            
            
            <v-btn-toggle v-model="isSignIn" class="d-flex justify-center mb-6" color="cyan-darken-2" rounded="pill" mandatory>
                <v-btn :value="true" class="text-none" width="160" size="large" variant="text">Sign In</v-btn>
                <v-btn :value="false" class="text-none" width="160" size="large" variant="text">Register</v-btn>
            </v-btn-toggle>

            
            
            
            <v-card class="pa-4" color="grey-darken-4" rounded="lg">

                
                
                <!-- Sign In Form -->
                
                <v-form v-if="isSignIn" ref="signInFormRef" @submit.prevent="onSignIn">

                    <AuthTextField v-model="signInForm.email" label="Email address" placeholder="user@gmail.com" icon="mdi-email-outline" :rules="emailRules"/>
                    <AuthTextField v-model="signInForm.password" label="Password" placeholder="Enter password" icon="mdi-lock-outline" isPassword :rules="requiredRules">
                        <template #label-append>
                            <v-btn variant="text" size="small" class="text-none" color="cyan-darken-2" @click="router.push('/auth/forgot')">
                                Forgot password?
                            </v-btn>
                        </template>
                    </AuthTextField>
                    <v-alert v-if="signInError" type="error" variant="tonal" class="mb-4">
                        {{ signInError }}
                    </v-alert>
                    <v-btn type="submit" block size="large" color="cyan-darken-2" class="text-none" :loading="signInLoading" :disabled="signInLoading">
                        Sign In
                        <v-icon end>mdi-arrow-right</v-icon>
                    </v-btn>
                </v-form>

                <!-- Sign Up Form -->
                <v-form v-else ref="signUpFormRef" @submit.prevent="onSignUp">
                    <AuthTextField v-model="signUpForm.email" label="Email" placeholder="user@gmail.com" icon="mdi-email-outline" :rules="emailRules">
                      <template #append v-if="signUpForm.email.trim()">
                        <v-btn 
                          :disabled="countdown > 0" 
                          height="56" 
                          min-width="100"
                          variant="tonal" 
                          color="cyan-darken-2"
                          @click="sendCode"
                        >
                          {{ countdown > 0 ? `${countdown}s` : 'Send' }}
                        </v-btn>
                      </template>
                    </AuthTextField>
                    <AuthTextField v-model="signUpForm.verificationCode" label="Verification Code" placeholder="Enter verification code" icon="mdi-shield-key-outline" :rules="requiredRules"/>
                    <AuthTextField v-model="signUpForm.password" label="Password" placeholder="At least 6 characters" icon="mdi-lock-outline" isPassword :rules="passwordRules"/>
                    <AuthTextField v-model="signUpForm.confirmPassword" label="Confirm Password" placeholder="Re-enter your password" icon="mdi-lock-outline" isPassword :rules="confirmPasswordRules" class="mb-8"/>
                    <v-btn type="submit" block size="large" color="cyan-darken-2" class="text-none mt-2">
                        Create Account
                        <v-icon end>mdi-arrow-right</v-icon>
                    </v-btn>
                </v-form>
            </v-card>

            <!-- Security Notice -->
            <div class="d-flex align-center justify-center mt-6 text-grey">
                <v-icon icon="mdi-shield-check-outline" size="18" class="mr-2" color="teal" />
                <span class="text-body-2">Credentials are stored locally and never sent to third-party services</span>
            </div>
        </v-col>
    </v-row>
  </v-container>
</template>


<script setup lang="ts">
    import { ref, reactive, computed } from 'vue'
    import { useRouter } from 'vue-router'
    import AuthTextField from '@/components/AuthTextField.vue'
    import { login, register, sendRegisterCode } from '@/api/auth'

    const router = useRouter()
    const isSignIn = ref(true)
    const signInFormRef = ref()
    const signUpFormRef = ref()
    const countdown = ref(0)
    const signInLoading = ref(false)
    const signInError = ref('')
    let timer: ReturnType<typeof setInterval> | null = null

    const signInForm = reactive({
        email: '',
        password: ''
    })

    const signUpForm = reactive({
        email: '',
        password: '',
        confirmPassword: '',
        verificationCode: ''
    })

    // Validation rules
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
        (v: string) => v === signUpForm.password || 'Passwords do not match'
    ])

    async function sendCode() {
        // Check if email is valid before sending
        const emailValid = emailRules.every(rule => rule(signUpForm.email) === true)
        if (!emailValid) return

        try {
            await sendRegisterCode({ email: signUpForm.email })
            countdown.value = 60
            timer = setInterval(() => {
                countdown.value--
                if (countdown.value <= 0 && timer) {
                    clearInterval(timer)
                    timer = null
                }
            }, 1000)
        } catch (error) {
            signInError.value = error instanceof Error ? error.message : 'Failed to send verification code'
        }
    }

    async function onSignIn() {
        const { valid } = await signInFormRef.value.validate()
        if (!valid) return
        signInError.value = ''
        signInLoading.value = true

        try {
            const result = await login({
                email: signInForm.email,
                password: signInForm.password,
            })

            localStorage.setItem('accessToken', result.access_token)
            localStorage.setItem('user', JSON.stringify({ email: result.email }))
            localStorage.removeItem('refreshToken')

            router.push('/')
        } catch (error) {
            signInError.value = error instanceof Error ? error.message : 'Login failed'
        } finally {
            signInLoading.value = false
        }
    }

    const signUpLoading = ref(false)
    const signUpError = ref('')

    async function onSignUp() {
        const { valid } = await signUpFormRef.value.validate()
        if (!valid) return
        signUpError.value = ''
        signUpLoading.value = true

        try {
            await register({
                email: signUpForm.email,
                password: signUpForm.password,
                verificationCode: signUpForm.verificationCode,
            })
            // 注册成功后切换到登录表单
            isSignIn.value = true
            signInForm.email = signUpForm.email
        } catch (error) {
            signUpError.value = error instanceof Error ? error.message : 'Registration failed'
        } finally {
            signUpLoading.value = false
        }
    }
</script>
