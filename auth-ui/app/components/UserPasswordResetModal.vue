<template>
  <UModal v-model="isOpen" :ui="{ width: 'sm:max-w-md' }">
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold">Reset User Password</h3>
          <UButton
            color="gray"
            variant="ghost"
            icon="i-lucide-x"
            @click="close"
          />
        </div>
      </template>

      <form @submit.prevent="onSubmit" class="space-y-4">
        <UAlert
          color="warning"
          icon="i-lucide-alert-triangle"
          title="Admin Password Reset"
          description="You are about to reset this user's password. They will need to use the new password to login."
        />

        <UFormField
          label="User"
          name="user"
        >
          <UInput
            :model-value="user?.email"
            disabled
            icon="i-lucide-user"
          />
        </UFormField>

        <UFormField
          label="New Password"
          name="new_password"
          required
          help="Password must be at least 8 characters"
        >
          <UInput
            v-model="newPassword"
            type="password"
            placeholder="Enter new password"
            :disabled="isLoading"
          />
        </UFormField>

        <UFormField
          label="Confirm Password"
          name="confirm_password"
          required
        >
          <UInput
            v-model="confirmPassword"
            type="password"
            placeholder="Confirm new password"
            :disabled="isLoading"
          />
        </UFormField>

        <UAlert
          v-if="errorMessage"
          color="error"
          icon="i-lucide-alert-circle"
          :title="errorMessage"
          :close-button="{ icon: 'i-lucide-x', color: 'error', variant: 'link', padded: false }"
          @close="errorMessage = ''"
        />
      </form>

      <template #footer>
        <div class="flex justify-end gap-3">
          <UButton
            color="gray"
            variant="soft"
            @click="close"
            :disabled="isLoading"
          >
            Cancel
          </UButton>

          <UButton
            color="primary"
            @click="onSubmit"
            :loading="isLoading"
            :disabled="!isFormValid"
          >
            Reset Password
          </UButton>
        </div>
      </template>
    </UCard>
  </UModal>
</template>

<script setup lang="ts">
import type { User } from '~/types'

const props = defineProps<{
  user: User | null
}>()

const emit = defineEmits<{
  close: []
  success: []
}>()

// Modal state
const isOpen = defineModel<boolean>({ required: true })

// Form state
const newPassword = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)
const errorMessage = ref('')

// Auth store
const authStore = useAuthStore()

// Form validation
const isFormValid = computed(() => {
  return newPassword.value.length >= 8 &&
         confirmPassword.value.length >= 8 &&
         newPassword.value === confirmPassword.value
})

// Form submission
const onSubmit = async () => {
  if (!props.user?.id) {
    errorMessage.value = 'User not found'
    return
  }

  // Validate passwords match
  if (newPassword.value !== confirmPassword.value) {
    errorMessage.value = "Passwords don't match"
    return
  }

  // Validate password length
  if (newPassword.value.length < 8) {
    errorMessage.value = "Password must be at least 8 characters"
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    // Call admin password reset API
    await authStore.apiCall(`/v1/users/${props.user.id}/password`, {
      method: 'PATCH',
      body: {
        new_password: newPassword.value
      }
    })

    // Show success notification
    const toast = useToast()
    toast.add({
      title: 'Password reset successful',
      description: `Password reset for ${props.user.email}`,
      color: 'green',
      icon: 'i-lucide-check-circle'
    })

    // Emit success event and close modal
    emit('success')
    close()
  } catch (error: any) {
    console.error('Admin password reset error:', error)

    if (error.message) {
      errorMessage.value = error.message
    } else {
      errorMessage.value = 'Failed to reset password. Please try again.'
    }
  } finally {
    isLoading.value = false
  }
}

// Close modal and reset form
const close = () => {
  isOpen.value = false
  newPassword.value = ''
  confirmPassword.value = ''
  errorMessage.value = ''
  emit('close')
}

// Watch for modal close to reset form
watch(isOpen, (value) => {
  if (!value) {
    newPassword.value = ''
    confirmPassword.value = ''
    errorMessage.value = ''
  }
})
</script>
