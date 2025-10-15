<script setup lang="ts">
import type { User } from '~/types/auth.types'

const props = defineProps<{
  user: User
}>()

// Stores
const usersStore = useUsersStore()

// State
const isResettingPassword = ref(false)
const showPasswordOptions = ref(false)

// Methods
async function resetPassword(sendEmail: boolean) {
  isResettingPassword.value = true
  try {
    const response = await usersStore.resetUserPassword(props.user.id, sendEmail)
    
    if (!sendEmail && response.temporary_password) {
      // Show temporary password in a modal or alert
      alert(`Temporary password: ${response.temporary_password}\n\nPlease share this securely with the user.`)
    }
  } finally {
    isResettingPassword.value = false
    showPasswordOptions.value = false
  }
}

async function unlockAccount() {
  if (confirm('Unlock this user account?')) {
    await usersStore.updateUserStatus(props.user.id, 'active')
  }
}

// Computed
const accountStatus = computed(() => {
  if (props.user.locked_until && new Date(props.user.locked_until) > new Date()) {
    return 'locked'
  }
  return props.user.is_active ? 'active' : 'inactive'
})

const accountStatusColor = computed(() => {
  switch (accountStatus.value) {
    case 'active':
      return 'success'
    case 'locked':
      return 'error'
    default:
      return 'neutral'
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Account Status -->
    <div>
      <h4 class="text-sm font-medium mb-4">Account Status</h4>
      <UCard>
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">Status</span>
            <UBadge :color="accountStatusColor" variant="subtle">
              {{ accountStatus }}
            </UBadge>
          </div>
          
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">Email Verified</span>
            <UIcon 
              :name="user.email_verified ? 'i-lucide-check-circle' : 'i-lucide-x-circle'" 
              :class="user.email_verified ? 'text-green-500' : 'text-gray-400'"
            />
          </div>

          <div v-if="user.failed_login_attempts > 0" class="flex items-center justify-between">
            <span class="text-sm font-medium">Failed Login Attempts</span>
            <span class="text-sm text-error">{{ user.failed_login_attempts }}</span>
          </div>

          <div v-if="user.locked_until" class="flex items-center justify-between">
            <span class="text-sm font-medium">Locked Until</span>
            <span class="text-sm">{{ usersStore.formatDate(user.locked_until) }}</span>
          </div>
        </div>

        <template v-if="accountStatus === 'locked'" #footer>
          <UButton
            variant="outline"
            size="sm"
            icon="i-lucide-unlock"
            @click="unlockAccount"
          >
            Unlock Account
          </UButton>
        </template>
      </UCard>
    </div>

    <!-- Password Management -->
    <div>
      <h4 class="text-sm font-medium mb-4">Password Management</h4>
      <UCard>
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">Last Password Change</span>
            <span class="text-sm text-gray-500">
              {{ usersStore.formatDate(user.last_password_change) }}
            </span>
          </div>

          <div v-if="!showPasswordOptions">
            <UButton
              variant="outline"
              icon="i-lucide-key"
              @click="showPasswordOptions = true"
            >
              Reset Password
            </UButton>
          </div>

          <div v-else class="space-y-3">
            <p class="text-sm text-gray-600">How would you like to reset the password?</p>
            <div class="flex gap-3">
              <UButton
                variant="outline"
                size="sm"
                icon="i-lucide-mail"
                :loading="isResettingPassword"
                @click="resetPassword(true)"
              >
                Send Email
              </UButton>
              <UButton
                variant="outline"
                size="sm"
                icon="i-lucide-copy"
                :loading="isResettingPassword"
                @click="resetPassword(false)"
              >
                Generate & Copy
              </UButton>
              <UButton
                variant="ghost"
                size="sm"
                @click="showPasswordOptions = false"
              >
                Cancel
              </UButton>
            </div>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Login History -->
    <div>
      <h4 class="text-sm font-medium mb-4">Login History</h4>
      <UCard>
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">Last Login</span>
            <span class="text-sm text-gray-500">
              {{ usersStore.formatDate(user.last_login) }}
            </span>
          </div>
          
          <p class="text-xs text-gray-500">
            Detailed login history is available in the Activity tab
          </p>
        </div>
      </UCard>
    </div>

    <!-- System User Warning -->
    <div v-if="user.is_system_user">
      <UAlert
        icon="i-lucide-alert-triangle"
        color="warning"
        variant="subtle"
        title="System User"
        description="This is a system user account. Some security features may be restricted."
      />
    </div>
  </div>
</template>