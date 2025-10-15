<template>
  <div class="space-y-6">
    <UCard>
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
          <UButton type="submit" :loading="settingsStore.isSaving">
            Save Rate Limit Settings
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
const rateLimitSchema = z.object({
  enabled: z.boolean(),
  window_minutes: z.number().min(1).max(60),
  max_requests: z.number().min(10).max(1000),
  max_login_attempts: z.number().min(3).max(20),
  block_duration_minutes: z.number().min(5).max(1440)
})

// Form state - reactive reference to store data
const rateLimitSettings = reactive({
  ...settingsStore.rateLimiting
})

// Watch for store updates
watch(() => settingsStore.rateLimiting, (newSettings) => {
  Object.assign(rateLimitSettings, newSettings)
}, { deep: true })

// Methods
const saveRateLimitSettings = async () => {
  try {
    await settingsStore.saveRateLimitingSettings(rateLimitSettings)
  } catch (error) {
    // Error handled in store
  }
}

// Load settings on mount
onMounted(() => {
  settingsStore.fetchSettings()
})
</script>