<template>
  <UCard class="mt-4">
    <template #header>
      <h3 class="text-lg font-semibold">Profile Information</h3>
      <p class="text-sm text-muted-foreground mt-1">
        Update your personal information and profile details
      </p>
    </template>

    <UForm 
      :schema="schema" 
      :state="state" 
      @submit="onSubmit"
      class="space-y-4"
    >
      <!-- Name Fields -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <UFormField name="first_name" label="First Name">
          <UInput 
            v-model="state.first_name" 
            placeholder="John"
            icon="i-lucide-user"
          />
        </UFormField>

        <UFormField name="last_name" label="Last Name">
          <UInput 
            v-model="state.last_name" 
            placeholder="Doe"
          />
        </UFormField>
      </div>

      <!-- Email (Read-only) -->
      <UFormField name="email" label="Email Address">
        <UInput 
          v-model="state.email" 
          disabled
          icon="i-lucide-mail"
        />
        <template #description>
          <span class="text-xs text-muted-foreground">
            Contact your administrator to change your email address
          </span>
        </template>
      </UFormField>

      <!-- Phone -->
      <UFormField name="phone" label="Phone Number">
        <UInput 
          v-model="state.phone" 
          placeholder="+1 (555) 123-4567"
          icon="i-lucide-phone"
        />
        <template #description>
          <span class="text-xs text-muted-foreground">
            Used for two-factor authentication and account recovery
          </span>
        </template>
      </UFormField>

      <!-- Timezone -->
      <UFormField name="timezone" label="Timezone">
        <USelect
          v-model="state.timezone"
          :items="timezoneOptions"
          placeholder="Select timezone"
        />
      </UFormField>

      <!-- Language -->
      <UFormField name="language" label="Language">
        <USelect
          v-model="state.language"
          :items="languageOptions"
          placeholder="Select language"
        />
      </UFormField>

      <USeparator />

      <!-- Save Button -->
      <div class="flex justify-end">
        <UButton 
          type="submit"
          :loading="isSubmitting"
        >
          Save Changes
        </UButton>
      </div>
    </UForm>
  </UCard>
</template>

<script setup lang="ts">
import { z } from 'zod'

// Stores
const authStore = useAuthStore()
const userStore = useUserStore()
const toast = useToast()

// State
const isSubmitting = ref(false)

// Form schema
const schema = z.object({
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  email: z.string().email(),
  phone: z.string().optional(),
  timezone: z.string(),
  language: z.string()
})

// Form state - initialize with current user data
const state = reactive({
  first_name: userStore.user?.profile?.first_name || '',
  last_name: userStore.user?.profile?.last_name || '',
  email: userStore.user?.email || '',
  phone: userStore.user?.profile?.phone || '',
  timezone: 'America/New_York', // Default, would come from user preferences
  language: userStore.language || 'en'
})

// Options
const timezoneOptions = [
  { value: 'America/New_York', label: 'Eastern Time (ET)' },
  { value: 'America/Chicago', label: 'Central Time (CT)' },
  { value: 'America/Denver', label: 'Mountain Time (MT)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (PT)' },
  { value: 'UTC', label: 'UTC' },
  { value: 'Europe/London', label: 'London' },
  { value: 'Europe/Paris', label: 'Paris' },
  { value: 'Asia/Tokyo', label: 'Tokyo' },
  { value: 'Asia/Shanghai', label: 'Shanghai' },
  { value: 'Australia/Sydney', label: 'Sydney' }
]

const languageOptions = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ja', label: 'Japanese' }
]

// Methods
const onSubmit = async () => {
  isSubmitting.value = true

  try {
    // Update user profile
    const updateData = {
      first_name: state.first_name,
      last_name: state.last_name,
      phone: state.phone
    }

    await authStore.apiCall(`/v1/users/${userStore.id}`, {
      method: 'PUT',
      body: updateData
    })

    // Update language preference
    if (state.language !== userStore.language) {
      userStore.setLanguage(state.language)
    }

    // Refresh user data
    const userData = await authStore.apiCall('/v1/auth/me')
    userStore.setUser(userData)

    toast.add({
      title: 'Profile updated',
      description: 'Your profile information has been saved',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Failed to update profile',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}
</script>