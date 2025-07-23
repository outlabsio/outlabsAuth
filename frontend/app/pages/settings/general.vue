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
          <UButton type="submit" :loading="isSaving">
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
const authStore = useAuthStore()
const toast = useToast()

// State
const isSaving = ref(false)

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

// Form state
const generalSettings = reactive({
  platform_name: 'OutlabsAuth',
  platform_description: '',
  default_language: 'en',
  timezone: 'UTC'
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
</script>