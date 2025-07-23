<template>
  <div class="space-y-6">
    <UCard>
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

        <USeparator class="my-6" />

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
          <UButton type="submit" :loading="settingsStore.isSaving">
            Save Security Settings
          </UButton>
        </div>
      </UForm>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import { z } from 'zod'

// Stores
const settingsStore = useSettingsStore()

// Schema
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

// Form state - reactive reference to store data
const securitySettings = reactive({
  ...settingsStore.security
})

// Watch for store updates
watch(() => settingsStore.security, (newSettings) => {
  Object.assign(securitySettings, newSettings)
}, { deep: true })

// Methods
const saveSecuritySettings = async () => {
  try {
    await settingsStore.saveSecuritySettings(securitySettings)
  } catch (error) {
    // Error handled in store
  }
}

// Load settings on mount
onMounted(() => {
  settingsStore.fetchSettings()
})
</script>