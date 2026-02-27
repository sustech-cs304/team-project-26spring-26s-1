<template>
  <v-container class="fill-height d-flex align-center justify-center ">
    <v-row justify="center" >
        <v-col cols="12" sm="11" md="9" lg="7" xl="6">
            <div class=" d-flex justify-center mb-8">
                <v-avatar size="80">
                    <v-icon icon="mdi-account" size="60" />
                </v-avatar>
            </div>

            <v-btn-toggle v-model="isSignIn" class="d-flex justify-center mb-6" color="cyan-darken-2" rounded="pill" mandatory>
                <v-btn :value="true" class="text-none" width="220" size="x-large" variant="text">Sign In</v-btn>
                <v-btn :value="false" class="text-none" width="220" size="x-large" variant="text">Register</v-btn>
            </v-btn-toggle>

            <!-- Card Container -->
            <v-card class="pa-8" color="grey-darken-4" rounded="lg">
                <div class="d-flex align-center justify-space-between mb-6">
                    <div class="d-flex align-center">
                        <v-icon icon="mdi-shield-check" color="cyan-darken-2" size="24" class="mr-2" />
                        <span class="text-body-1 font-weight-medium">SUSTech CAS Authentication</span>
                    </div>
                </div>

                <!-- Sign In Form -->
                <v-form v-if="isSignIn" >
                    <AuthTextField v-model="signInForm.studentId" label="Student ID" placeholder="e.g. 12110001" icon="mdi-pound"/>
                    <AuthTextField v-model="signInForm.password" label="Password" placeholder="Enter your CAS password" type="password" icon="mdi-lock-outline"/>
                    <div class="d-flex justify-end mb-4">
                        <v-btn variant="text" size="small" class="text-none" color="cyan-darken-2">
                            Forgot password?
                        </v-btn>
                    </div>
                    <v-btn type="submit" block size="large" color="cyan-darken-2" class="text-none">
                        Sign In
                        <v-icon end>mdi-arrow-right</v-icon>
                    </v-btn>
                </v-form>

                <!-- Sign Up Form -->
                <v-form v-else >
                    <AuthTextField v-model="signUpForm.studentId" label="Student ID" placeholder="e.g. 12110001" icon="mdi-pound"/>
                    <AuthTextField v-model="signUpForm.email" label="Campus Email" placeholder="12110001@mail.sustech.edu.cn" type="email" icon="mdi-email-outline"/>
                    <AuthTextField v-model="signUpForm.password" label="Password" placeholder="At least 6 characters" type="password" icon="mdi-lock-outline"/>
                    <AuthTextField v-model="signUpForm.confirmPassword" label="Confirm Password" placeholder="Re-enter your password" type="password" icon="mdi-lock-outline" class="mb-8"/>
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
    import { ref, reactive } from 'vue'
    import AuthTextField from '@/components/AuthTextField.vue'

    const isSignIn = ref(true)

    const signInForm = reactive({
        studentId: '',
        password: ''
    })

    const signUpForm = reactive({
        studentId: '',
        email: '',
        password: '',
        confirmPassword: ''
    })

</script>
