<template>
  <div class="space-y-6">
    <UCard>
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
          <UButton type="submit" :loading="settingsStore.isSaving">
            Save Changes
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

// Schema
const generalSchema = z.object({
  platform_name: z.string().min(1, 'Platform name is required'),
  platform_description: z.string().optional(),
  default_language: z.string(),
  timezone: z.string()
})

// Form state - reactive reference to store data
const generalSettings = reactive({
  ...settingsStore.general
})

// Watch for store updates
watch(() => settingsStore.general, (newSettings) => {
  Object.assign(generalSettings, newSettings)
}, { deep: true })

// Methods
const saveGeneralSettings = async () => {
  try {
    await settingsStore.saveGeneralSettings(generalSettings)
  } catch (error) {
    // Error handled in store
  }
}

// Load settings on mount
onMounted(() => {
  settingsStore.fetchSettings()
})
</script>