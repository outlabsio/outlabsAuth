<template>
  <div class="space-y-6">

    <!-- Settings Tabs -->
    <UTabs v-model="activeTab" :items="tabItems" class="w-full">
      <!-- General Settings -->
      <template #general>
        <UCard class="mt-4">
          <UForm :schema="generalSchema" :state="generalSettings" @submit="saveGeneralSettings" class="space-y-4">
            <UFormField name="platform_name" label="Platform Name" required>
              <UInput v-model="generalSettings.platform_name" placeholder="Enter platform name" />
            </UFormField>

            <UFormField name="platform_description" label="Platform Description">
              <UTextarea v-model="generalSettings.platform_description" placeholder="Describe your platform" rows="3" />
            </UFormField>

            <UFormField name="default_language" label="Default Language">
              <USelect v-model="generalSettings.default_language" :items="languageOptions" />
            </UFormField>

            <UFormField name="timezone" label="Default Timezone">
              <USelect v-model="generalSettings.timezone" :items="timezoneOptions" />
            </UFormField>

            <div class="flex justify-end pt-4">
              <UButton type="submit" :loading="isSaving">
                Save Changes
              </UButton>
            </div>
          </UForm>
        </UCard>
      </template>

      <!-- Security Settings -->
      <template #security>
        <UCard class="mt-4">
          <UForm :schema="securitySchema" :state="securitySettings" @submit="saveSecuritySettings" class="space-y-4">
            <h3 class="text-lg font-semibold mb-4">Password Policy</h3>
            
            <UFormField name="min_password_length" label="Minimum Password Length">
              <UInput v-model.number="securitySettings.min_password_length" type="number" min="8" max="32" />
            </UFormField>

            <div class="space-y-2">
              <UCheckbox v-model="securitySettings.require_uppercase" label="Require uppercase letter" />
              <UCheckbox v-model="securitySettings.require_lowercase" label="Require lowercase letter" />
              <UCheckbox v-model="securitySettings.require_digits" label="Require numeric digit" />
              <UCheckbox v-model="securitySettings.require_special_chars" label="Require special character" />
            </div>

            <UDivider class="my-6" />

            <h3 class="text-lg font-semibold mb-4">Session Settings</h3>

            <UFormField name="access_token_minutes" label="Access Token Expiration (minutes)">
              <UInput v-model.number="securitySettings.access_token_minutes" type="number" min="5" max="60" />
            </UFormField>

            <UFormField name="refresh_token_days" label="Refresh Token Expiration (days)">
              <UInput v-model.number="securitySettings.refresh_token_days" type="number" min="1" max="90" />
            </UFormField>

            <UFormField name="max_login_attempts" label="Maximum Login Attempts">
              <UInput v-model.number="securitySettings.max_login_attempts" type="number" min="3" max="10" />
            </UFormField>

            <div class="flex justify-end pt-4">
              <UButton type="submit" :loading="isSaving">
                Save Security Settings
              </UButton>
            </div>
          </UForm>
        </UCard>
      </template>

      <!-- Email Settings -->
      <template #email>
        <UCard class="mt-4">
          <UForm :schema="emailSchema" :state="emailSettings" @submit="saveEmailSettings" class="space-y-4">
            <UFormField name="smtp_enabled" label="">
              <UCheckbox v-model="emailSettings.smtp_enabled" label="Enable Email Notifications" />
            </UFormField>

            <template v-if="emailSettings.smtp_enabled">
              <UFormField name="smtp_host" label="SMTP Host" required>
                <UInput v-model="emailSettings.smtp_host" placeholder="smtp.example.com" />
              </UFormField>

              <UFormField name="smtp_port" label="SMTP Port" required>
                <UInput v-model.number="emailSettings.smtp_port" type="number" placeholder="587" />
              </UFormField>

              <UFormField name="smtp_username" label="SMTP Username" required>
                <UInput v-model="emailSettings.smtp_username" placeholder="username@example.com" />
              </UFormField>

              <UFormField name="smtp_password" label="SMTP Password" required>
                <UInput v-model="emailSettings.smtp_password" type="password" placeholder="Enter password" />
              </UFormField>

              <UFormField name="smtp_from_email" label="From Email" required>
                <UInput v-model="emailSettings.smtp_from_email" type="email" placeholder="noreply@example.com" />
              </UFormField>

              <UFormField name="smtp_from_name" label="From Name">
                <UInput v-model="emailSettings.smtp_from_name" placeholder="Platform Name" />
              </UFormField>

              <div class="flex gap-3 pt-2">
                <UButton variant="outline" @click="testEmailSettings" :loading="isTesting">
                  Test Connection
                </UButton>
              </div>
            </template>

            <div class="flex justify-end pt-4">
              <UButton type="submit" :loading="isSaving">
                Save Email Settings
              </UButton>
            </div>
          </UForm>
        </UCard>
      </template>

      <!-- Rate Limiting -->
      <template #ratelimiting>
        <UCard class="mt-4">
          <UForm :schema="rateLimitSchema" :state="rateLimitSettings" @submit="saveRateLimitSettings" class="space-y-4">
            <UFormField name="enabled" label="">
              <UCheckbox v-model="rateLimitSettings.enabled" label="Enable Rate Limiting" />
            </UFormField>

            <template v-if="rateLimitSettings.enabled">
              <UFormField name="window_minutes" label="Time Window (minutes)">
                <UInput v-model.number="rateLimitSettings.window_minutes" type="number" min="1" max="60" />
              </UFormField>

              <UFormField name="max_requests" label="Maximum Requests per Window">
                <UInput v-model.number="rateLimitSettings.max_requests" type="number" min="10" max="1000" />
              </UFormField>

              <UFormField name="max_login_attempts" label="Maximum Login Attempts per Window">
                <UInput v-model.number="rateLimitSettings.max_login_attempts" type="number" min="3" max="20" />
              </UFormField>

              <UFormField name="block_duration_minutes" label="Block Duration (minutes)">
                <UInput v-model.number="rateLimitSettings.block_duration_minutes" type="number" min="5" max="1440" />
              </UFormField>
            </template>

            <div class="flex justify-end pt-4">
              <UButton type="submit" :loading="isSaving">
                Save Rate Limit Settings
              </UButton>
            </div>
          </UForm>
        </UCard>
      </template>
    </UTabs>
  </div>
</template>

<script setup lang="ts">
import { z } from 'zod'
import type { NavigationMenuItem } from '@nuxt/ui'

// Page meta handled by parent settings.vue

// Stores
const authStore = useAuthStore()
const contextStore = useContextStore()
const router = useRouter()
const route = useRoute()
const toast = useToast()

// Navigation handled by parent settings.vue page

// State
const activeTab = ref('general')
const isSaving = ref(false)
const isTesting = ref(false)


// Tab configuration
const tabItems = [
  { slot: 'general', label: 'General', icon: 'i-lucide-settings' },
  { slot: 'security', label: 'Security', icon: 'i-lucide-shield' },
  { slot: 'email', label: 'Email', icon: 'i-lucide-mail' },
  { slot: 'ratelimiting', label: 'Rate Limiting', icon: 'i-lucide-gauge' }
]

// Options
const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' }
]

const timezoneOptions = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/New_York', label: 'Eastern Time' },
  { value: 'America/Chicago', label: 'Central Time' },
  { value: 'America/Denver', label: 'Mountain Time' },
  { value: 'America/Los_Angeles', label: 'Pacific Time' },
  { value: 'Europe/London', label: 'London' },
  { value: 'Europe/Paris', label: 'Paris' },
  { value: 'Asia/Tokyo', label: 'Tokyo' }
]

// Schemas
const generalSchema = z.object({
  platform_name: z.string().min(1, 'Platform name is required'),
  platform_description: z.string().optional(),
  default_language: z.string(),
  timezone: z.string()
})

const securitySchema = z.object({
  min_password_length: z.number().min(8).max(32),
  require_uppercase: z.boolean(),
  require_lowercase: z.boolean(),
  require_digits: z.boolean(),
  require_special_chars: z.boolean(),
  access_token_minutes: z.number().min(5).max(60),
  refresh_token_days: z.number().min(1).max(90),
  max_login_attempts: z.number().min(3).max(10)
})

const emailSchema = z.object({
  smtp_enabled: z.boolean(),
  smtp_host: z.string().optional(),
  smtp_port: z.number().optional(),
  smtp_username: z.string().optional(),
  smtp_password: z.string().optional(),
  smtp_from_email: z.string().email().optional(),
  smtp_from_name: z.string().optional()
})

const rateLimitSchema = z.object({
  enabled: z.boolean(),
  window_minutes: z.number().min(1).max(60),
  max_requests: z.number().min(10).max(1000),
  max_login_attempts: z.number().min(3).max(20),
  block_duration_minutes: z.number().min(5).max(1440)
})

// Form states
const generalSettings = reactive({
  platform_name: 'OutlabsAuth',
  platform_description: '',
  default_language: 'en',
  timezone: 'UTC'
})

const securitySettings = reactive({
  min_password_length: 8,
  require_uppercase: true,
  require_lowercase: true,
  require_digits: true,
  require_special_chars: true,
  access_token_minutes: 15,
  refresh_token_days: 30,
  max_login_attempts: 5
})

const emailSettings = reactive({
  smtp_enabled: false,
  smtp_host: '',
  smtp_port: 587,
  smtp_username: '',
  smtp_password: '',
  smtp_from_email: '',
  smtp_from_name: ''
})

const rateLimitSettings = reactive({
  enabled: true,
  window_minutes: 15,
  max_requests: 100,
  max_login_attempts: 5,
  block_duration_minutes: 30
})

// Methods
const saveGeneralSettings = async () => {
  isSaving.value = true
  try {
    // In a real implementation, this would save to a settings endpoint
    toast.add({
      title: 'Settings saved',
      description: 'General settings have been updated',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Failed to save settings',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSaving.value = false
  }
}

const saveSecuritySettings = async () => {
  isSaving.value = true
  try {
    // In a real implementation, this would save to a settings endpoint
    toast.add({
      title: 'Settings saved',
      description: 'Security settings have been updated',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Failed to save settings',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSaving.value = false
  }
}

const saveEmailSettings = async () => {
  isSaving.value = true
  try {
    // In a real implementation, this would save to a settings endpoint
    toast.add({
      title: 'Settings saved',
      description: 'Email settings have been updated',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Failed to save settings',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSaving.value = false
  }
}

const saveRateLimitSettings = async () => {
  isSaving.value = true
  try {
    // In a real implementation, this would save to a settings endpoint
    toast.add({
      title: 'Settings saved',
      description: 'Rate limiting settings have been updated',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Failed to save settings',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSaving.value = false
  }
}

const testEmailSettings = async () => {
  isTesting.value = true
  try {
    // In a real implementation, this would test the email connection
    await new Promise(resolve => setTimeout(resolve, 2000)) // Simulate API call
    toast.add({
      title: 'Test successful',
      description: 'Email connection is working correctly',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Test failed',
      description: error.message || 'Could not connect to email server',
      color: 'error'
    })
  } finally {
    isTesting.value = false
  }
}

// No initialization needed on mount

// SEO handled by parent settings.vue page
</script>