<template>
  <div class="space-y-6">
    <!-- Email Notifications -->
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <USwitch v-model="emailSettings.enabled" />
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-mail" class="h-5 w-5" />
              <h3 class="text-lg font-semibold">Email Notifications</h3>
            </div>
          </div>
          <UButton 
            v-if="emailSettings.enabled && hasChanges" 
            type="submit" 
            :loading="settingsStore.isSaving"
            size="sm"
            @click="saveEmailSettings"
          >
            Save Changes
          </UButton>
        </div>
      </template>

      <UForm :schema="emailSchema" :state="emailSettings" @submit="saveEmailSettings" class="space-y-6">
        <template v-if="emailSettings.enabled">
          <!-- SMTP Configuration Grid -->
          <div class="space-y-6">
            <!-- Server Settings -->
            <div>
              <h4 class="text-sm font-medium text-muted-foreground mb-4">Server Configuration</h4>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UFormField name="smtp_host" label="SMTP Host" required>
                  <UInput 
                    v-model="emailSettings.smtp_host" 
                    placeholder="smtp.example.com"
                    icon="i-lucide-server"
                  />
                </UFormField>

                <UFormField name="smtp_port" label="SMTP Port" required>
                  <UInput 
                    v-model.number="emailSettings.smtp_port" 
                    type="number" 
                    placeholder="587"
                    icon="i-lucide-hash"
                  />
                </UFormField>
              </div>
            </div>

            <!-- Authentication -->
            <div>
              <h4 class="text-sm font-medium text-muted-foreground mb-4">Authentication</h4>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UFormField name="smtp_username" label="Username" required>
                  <UInput 
                    v-model="emailSettings.smtp_username" 
                    placeholder="username@example.com"
                    icon="i-lucide-user"
                  />
                </UFormField>

                <UFormField name="smtp_password" label="Password" required>
                  <UInput 
                    v-model="emailSettings.smtp_password" 
                    type="password" 
                    placeholder="Enter password"
                    icon="i-lucide-lock"
                  />
                </UFormField>
              </div>
            </div>

            <!-- Sender Information -->
            <div>
              <h4 class="text-sm font-medium text-muted-foreground mb-4">Sender Information</h4>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <UFormField name="smtp_from_email" label="From Email" required>
                  <UInput 
                    v-model="emailSettings.smtp_from_email" 
                    type="email" 
                    placeholder="noreply@example.com"
                    icon="i-lucide-at-sign"
                  />
                </UFormField>

                <UFormField name="smtp_from_name" label="From Name">
                  <UInput 
                    v-model="emailSettings.smtp_from_name" 
                    placeholder="Platform Name"
                    icon="i-lucide-tag"
                  />
                </UFormField>
              </div>
            </div>

            <!-- Test Connection -->
            <div class="flex items-center justify-between p-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <div>
                <h4 class="font-medium">Test Configuration</h4>
                <p class="text-sm text-muted-foreground mt-1">Send a test email to verify your settings</p>
              </div>
              <UButton 
                variant="outline" 
                @click="testEmailConnection" 
                :loading="isTesting"
                icon="i-lucide-send"
              >
                Send Test Email
              </UButton>
            </div>
          </div>
        </template>

        <!-- Disabled State -->
        <div v-else class="py-12 text-center">
          <p class="text-sm text-muted-foreground">Configure SMTP settings to enable email notifications</p>
        </div>
      </UForm>
    </UCard>

    <!-- Future Notification Channels -->
    <UCard>
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-bell-plus" class="h-5 w-5" />
          <h3 class="text-lg font-semibold">Additional Channels</h3>
        </div>
      </template>

      <div class="space-y-4">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <!-- Slack -->
          <div class="relative overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
            <div class="absolute top-0 right-0 p-2">
              <UBadge color="gray" variant="subtle" size="xs">Coming Soon</UBadge>
            </div>
            <div class="space-y-3">
              <div class="h-12 w-12 rounded-lg bg-[#4A154B] flex items-center justify-center">
                <UIcon name="i-simple-icons-slack" class="h-6 w-6 text-white" />
              </div>
              <div>
                <h4 class="font-semibold">Slack</h4>
                <p class="text-sm text-muted-foreground mt-1">Send real-time notifications to Slack channels and direct messages</p>
              </div>
              <div class="pt-2">
                <UButton variant="outline" size="sm" disabled block>
                  Configure
                </UButton>
              </div>
            </div>
          </div>

          <!-- Discord -->
          <div class="relative overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
            <div class="absolute top-0 right-0 p-2">
              <UBadge color="gray" variant="subtle" size="xs">Coming Soon</UBadge>
            </div>
            <div class="space-y-3">
              <div class="h-12 w-12 rounded-lg bg-[#5865F2] flex items-center justify-center">
                <UIcon name="i-simple-icons-discord" class="h-6 w-6 text-white" />
              </div>
              <div>
                <h4 class="font-semibold">Discord</h4>
                <p class="text-sm text-muted-foreground mt-1">Post notifications to Discord servers and channels</p>
              </div>
              <div class="pt-2">
                <UButton variant="outline" size="sm" disabled block>
                  Configure
                </UButton>
              </div>
            </div>
          </div>

          <!-- Webhooks -->
          <div class="relative overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700 p-6 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
            <div class="absolute top-0 right-0 p-2">
              <UBadge color="gray" variant="subtle" size="xs">Coming Soon</UBadge>
            </div>
            <div class="space-y-3">
              <div class="h-12 w-12 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <UIcon name="i-lucide-webhook" class="h-6 w-6 text-white" />
              </div>
              <div>
                <h4 class="font-semibold">Webhooks</h4>
                <p class="text-sm text-muted-foreground mt-1">Send JSON payloads to custom HTTP endpoints</p>
              </div>
              <div class="pt-2">
                <UButton variant="outline" size="sm" disabled block>
                  Configure
                </UButton>
              </div>
            </div>
          </div>
        </div>

        <UAlert 
          icon="i-lucide-sparkles" 
          variant="subtle"
        >
          <template #title>More channels coming soon</template>
          <template #description>
            We're working on adding support for Microsoft Teams, SMS, Push Notifications, and more.
          </template>
        </UAlert>
      </div>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import { z } from 'zod'

// Stores
const settingsStore = useSettingsStore()
const toast = useToast()

// State
const isTesting = ref(false)

// Schema
const emailSchema = z.object({
  enabled: z.boolean(),
  smtp_host: z.string().optional(),
  smtp_port: z.number().optional(),
  smtp_username: z.string().optional(),
  smtp_password: z.string().optional(),
  smtp_from_email: z.string().email().optional(),
  smtp_from_name: z.string().optional()
})

// Form state - reactive reference to store data
const emailSettings = reactive({
  ...settingsStore.notifications.email
})

// Track original settings for change detection
const originalSettings = ref({})

// Watch for store updates
watch(() => settingsStore.notifications.email, (newSettings) => {
  Object.assign(emailSettings, newSettings)
  originalSettings.value = { ...newSettings }
}, { deep: true, immediate: true })

// Computed
const hasChanges = computed(() => {
  return JSON.stringify(emailSettings) !== JSON.stringify(originalSettings.value)
})

// Methods
const saveEmailSettings = async () => {
  try {
    await settingsStore.saveNotificationSettings({
      ...settingsStore.notifications,
      email: emailSettings
    })
    // Reset original settings after successful save
    originalSettings.value = { ...emailSettings }
  } catch (error) {
    // Error handled in store
  }
}

const testEmailConnection = async () => {
  isTesting.value = true
  try {
    await settingsStore.testEmailConnection()
  } finally {
    isTesting.value = false
  }
}

// Load settings on mount
onMounted(async () => {
  await settingsStore.fetchSettings()
  // Initialize original settings after fetch
  originalSettings.value = { ...settingsStore.notifications.email }
})
</script>