<template>
  <div class="flex flex-col items-center justify-center gap-4 p-4 min-h-screen">
    <UPageCard class="w-full max-w-md">
      <UAuthForm
        :schema="loginSchema"
        title="Welcome back!"
        description="Sign in to your OutlabsAuth account"
        icon="i-lucide-lock-keyhole"
        :fields="fields"
        :loading="isLoading"
        @submit="onSubmit"
      >
        <template #description>
          <p class="text-sm text-gray-600 dark:text-gray-400">
            Don't have an account? <ULink to="/signup" class="font-medium">Sign up</ULink>.
          </p>
        </template>

        <template #password-hint>
          <ULink to="/recovery" class="text-sm font-medium">
            Forgot password?
          </ULink>
        </template>

        <template #validation v-if="errorMessage">
          <UAlert
            color="error"
            icon="i-lucide-alert-circle"
            :title="errorMessage"
            :close-button="{ icon: 'i-lucide-x', color: 'error', variant: 'link', padded: false }"
            @close="errorMessage = ''"
          />
        </template>
      </UAuthForm>
    </UPageCard>
  </div>
</template>

<script setup lang="ts">
import { z } from 'zod'
import type { FormSubmitEvent, AuthFormField } from '@nuxt/ui'

// Metadata
definePageMeta({
  layout: false // Use no layout for login page
})

// Auth form fields configuration
const fields: AuthFormField[] = [{
  name: 'email',
  type: 'email',
  label: 'Email',
  placeholder: 'you@example.com',
  required: true
}, {
  name: 'password',
  type: 'password',
  label: 'Password',
  placeholder: 'Enter your password',
  required: true
}]

// Zod validation schema
const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required')
})

type LoginSchema = z.infer<typeof loginSchema>

// Component state
const isLoading = ref(false)
const errorMessage = ref('')

// Stores
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

// Form submission
const onSubmit = async (event: FormSubmitEvent<LoginSchema>) => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    await authStore.login({
      email: event.data.email,
      password: event.data.password
    })

    // Initialize context after successful login
    const contextStore = useContextStore()
    await contextStore.initialize()

    // Redirect to intended page or dashboard
    const redirect = route.query.redirect as string
    await router.push(redirect || '/dashboard')
  } catch (error: any) {
    console.error('Login error:', error)
    errorMessage.value = error.message || 'Invalid email or password'
  } finally {
    isLoading.value = false
  }
}
</script>
