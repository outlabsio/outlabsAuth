<script setup lang="ts">
import { useForm } from '@tanstack/vue-form'
import { zodValidator } from '@tanstack/zod-form-adapter'
import { z } from 'zod'

definePageMeta({
  layout: "auth",
})

// Validation schema - note: outlabsAuth uses username, not email
const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
  rememberMe: z.boolean().optional().default(false)
})

// Store references
const authStore = useAuthStore()
const router = useRouter()

// Form state
const isLoading = ref(false)
const errorMessage = ref('')

// Initialize form with TanStack Form
const form = useForm({
  defaultValues: {
    username: '',
    password: '',
    rememberMe: false
  },
  validatorAdapter: zodValidator(loginSchema),
  onSubmit: async ({ value }) => {
    isLoading.value = true
    errorMessage.value = ''
    
    console.log('Form submitted with values:', value)
    
    try {
      await authStore.login(value.username, value.password)
      await router.push('/dashboard')
    } catch (error: any) {
      console.error('Login error:', error)
      if (error.data?.detail) {
        // Handle array of validation errors
        if (Array.isArray(error.data.detail)) {
          errorMessage.value = error.data.detail.map((err: any) => err.msg).join(', ')
        } else {
          errorMessage.value = error.data.detail
        }
      } else if (error.statusMessage) {
        errorMessage.value = error.statusMessage
      } else {
        errorMessage.value = 'Login failed. Please check your credentials.'
      }
    } finally {
      isLoading.value = false
    }
  }
})

// Redirect if already authenticated
onMounted(() => {
  if (authStore.isAuthenticated) {
    router.push('/dashboard')
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="w-full max-w-md space-y-8">
      <!-- Logo and Title -->
      <div class="text-center">
        <div class="flex justify-center mb-6">
          <UIcon name="i-lucide-shield-check" class="h-12 w-12 text-primary" />
        </div>
        <h2 class="text-3xl font-bold tracking-tight">
          Sign in to OutlabsAuth
        </h2>
        <p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
          Enter your credentials to access the admin dashboard
        </p>
      </div>

      <!-- Login Form Card -->
      <UCard>
        <form @submit="(e) => { e.preventDefault(); form.handleSubmit() }" class="space-y-6">
          <!-- Error Alert -->
          <UAlert 
            v-if="errorMessage" 
            color="red" 
            variant="subtle"
            icon="i-lucide-alert-circle"
            :title="errorMessage"
            :close-button="{ icon: 'i-lucide-x' }"
            @close="errorMessage = ''"
          />

          <!-- Username Field with TanStack Form -->
          <form.Field name="username">
            <template v-slot="{ field }">
              <UFormField 
                label="Username" 
                :error="field.state.meta.touchedErrors?.[0]"
                required
              >
                <UInput 
                  :model-value="field.state.value" 
                  @update:model-value="field.handleChange"
                  @blur="field.handleBlur"
                  placeholder="Enter your username"
                  size="lg"
                  :disabled="isLoading"
                  autofocus
                />
              </UFormField>
            </template>
          </form.Field>

          <!-- Password Field with TanStack Form -->
          <form.Field name="password">
            <template v-slot="{ field }">
              <UFormField 
                label="Password" 
                :error="field.state.meta.touchedErrors?.[0]"
                required
              >
                <template #hint>
                  <NuxtLink to="/recovery" class="text-sm text-primary hover:underline">
                    Forgot password?
                  </NuxtLink>
                </template>
                <UInput 
                  :model-value="field.state.value" 
                  @update:model-value="field.handleChange"
                  @blur="field.handleBlur"
                  type="password"
                  placeholder="Enter your password"
                  size="lg"
                  :disabled="isLoading"
                />
              </UFormField>
            </template>
          </form.Field>

          <!-- Remember Me Checkbox with TanStack Form -->
          <form.Field name="rememberMe">
            <template v-slot="{ field }">
              <UCheckbox 
                v-model="field.state.value"
                label="Remember me"
                :disabled="isLoading"
              />
            </template>
          </form.Field>

          <!-- Submit Button -->
          <UButton 
            type="submit" 
            block 
            size="lg"
            :loading="isLoading"
            :disabled="isLoading"
          >
            {{ isLoading ? 'Signing in...' : 'Sign in' }}
          </UButton>

          <!-- Sign up link -->
          <div class="text-center text-sm">
            Don't have an account? 
            <NuxtLink to="/signup" class="text-primary font-medium hover:underline">
              Sign up
            </NuxtLink>
          </div>
        </form>
      </UCard>
    </div>
  </div>
</template>
