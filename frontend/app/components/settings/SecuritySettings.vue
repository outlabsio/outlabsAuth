<template>
  <div class="space-y-6">
    <!-- Change Password -->
    <UCard>
      <template #header>
        <h3 class="text-lg font-semibold">Change Password</h3>
        <p class="text-sm text-muted-foreground mt-1">
          Update your password to keep your account secure
        </p>
      </template>

      <UForm 
        :schema="passwordSchema" 
        :state="passwordState" 
        @submit="onPasswordSubmit"
        class="space-y-4"
      >
        <UFormField name="current_password" label="Current Password" required>
          <UInput 
            v-model="passwordState.current_password" 
            type="password"
            placeholder="Enter current password"
            icon="i-lucide-lock"
          />
        </UFormField>

        <UFormField name="new_password" label="New Password" required>
          <UInput 
            v-model="passwordState.new_password" 
            type="password"
            placeholder="Enter new password"
            icon="i-lucide-lock"
          />
          <template #description>
            <span class="text-xs text-muted-foreground">
              Must be at least 8 characters with uppercase, lowercase, number, and special character
            </span>
          </template>
        </UFormField>

        <UFormField name="confirm_password" label="Confirm New Password" required>
          <UInput 
            v-model="passwordState.confirm_password" 
            type="password"
            placeholder="Confirm new password"
            icon="i-lucide-lock"
          />
        </UFormField>

        <div class="flex justify-end pt-4">
          <UButton 
            type="submit"
            :loading="isChangingPassword"
          >
            Update Password
          </UButton>
        </div>
      </UForm>
    </UCard>

    <!-- Two-Factor Authentication -->
    <UCard>
      <template #header>
        <h3 class="text-lg font-semibold">Two-Factor Authentication</h3>
        <p class="text-sm text-muted-foreground mt-1">
          Add an extra layer of security to your account
        </p>
      </template>

      <div v-if="!has2FA" class="space-y-4">
        <p class="text-sm text-muted-foreground">
          Two-factor authentication is not enabled for your account. Enable it to add an extra layer of security.
        </p>
        <UButton 
          icon="i-lucide-shield-check"
          @click="showEnable2FA = true"
        >
          Enable Two-Factor Authentication
        </UButton>
      </div>

      <div v-else class="space-y-4">
        <div class="flex items-center gap-3">
          <UIcon name="i-lucide-shield-check" class="h-5 w-5 text-success" />
          <span class="font-medium">Two-factor authentication is enabled</span>
        </div>
        <p class="text-sm text-muted-foreground">
          Your account is protected with two-factor authentication.
        </p>
        <UButton 
          variant="outline"
          color="error"
          @click="showDisable2FA = true"
        >
          Disable Two-Factor Authentication
        </UButton>
      </div>
    </UCard>

    <!-- Active Sessions -->
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-lg font-semibold">Active Sessions</h3>
            <p class="text-sm text-muted-foreground mt-1">
              Manage your active login sessions
            </p>
          </div>
          <UButton 
            variant="outline"
            size="sm"
            @click="fetchSessions"
            icon="i-lucide-refresh-cw"
          >
            Refresh
          </UButton>
        </div>
      </template>

      <div v-if="isLoadingSessions" class="flex justify-center py-8">
        <UIcon name="i-lucide-loader" class="h-6 w-6 animate-spin text-primary" />
      </div>

      <div v-else-if="sessions.length > 0" class="space-y-3">
        <div 
          v-for="session in sessions" 
          :key="session.id"
          class="p-4 border rounded-lg space-y-2"
          :class="session.is_current ? 'border-primary bg-primary/5' : 'border-border'"
        >
          <div class="flex items-start justify-between">
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-monitor" class="h-4 w-4 text-muted-foreground" />
                <span class="font-medium">{{ session.device || 'Unknown Device' }}</span>
                <UBadge v-if="session.is_current" size="xs" color="primary">
                  Current
                </UBadge>
              </div>
              <p class="text-sm text-muted-foreground">
                {{ session.browser || 'Unknown Browser' }} · {{ session.os || 'Unknown OS' }}
              </p>
              <p class="text-xs text-muted-foreground">
                {{ session.ip_address }} · Last active {{ formatRelativeTime(session.last_active) }}
              </p>
            </div>
            <UButton
              v-if="!session.is_current"
              variant="ghost"
              size="sm"
              color="error"
              icon="i-lucide-x"
              @click="revokeSession(session.id)"
            >
              Revoke
            </UButton>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-8">
        <p class="text-muted-foreground">No active sessions found</p>
      </div>
    </UCard>

    <!-- Enable 2FA Modal -->
    <UModal v-model="showEnable2FA">
      <UCard>
        <template #header>
          <h3 class="text-lg font-semibold">Enable Two-Factor Authentication</h3>
        </template>

        <div class="space-y-4">
          <p class="text-sm">
            Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
          </p>
          
          <!-- QR Code would go here -->
          <div class="bg-muted rounded-lg p-8 text-center">
            <p class="text-muted-foreground">QR Code Placeholder</p>
          </div>

          <UInput 
            v-model="totpCode" 
            placeholder="Enter 6-digit code"
            class="text-center text-lg"
            maxlength="6"
          />
        </div>

        <template #footer>
          <div class="flex justify-end gap-3">
            <UButton variant="outline" @click="showEnable2FA = false">
              Cancel
            </UButton>
            <UButton @click="enable2FA" :loading="isEnabling2FA">
              Enable
            </UButton>
          </div>
        </template>
      </UCard>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { z } from 'zod'

// Stores
const authStore = useAuthStore()
const userStore = useUserStore()
const toast = useToast()

// State
const isChangingPassword = ref(false)
const has2FA = ref(false)
const showEnable2FA = ref(false)
const showDisable2FA = ref(false)
const totpCode = ref('')
const isEnabling2FA = ref(false)
const sessions = ref<any[]>([])
const isLoadingSessions = ref(false)

// Password form schema
const passwordSchema = z.object({
  current_password: z.string().min(1, 'Current password is required'),
  new_password: z.string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
    .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
    .regex(/[0-9]/, 'Password must contain at least one number')
    .regex(/[^A-Za-z0-9]/, 'Password must contain at least one special character'),
  confirm_password: z.string()
}).refine((data) => data.new_password === data.confirm_password, {
  message: 'Passwords do not match',
  path: ['confirm_password']
})

// Password form state
const passwordState = reactive({
  current_password: '',
  new_password: '',
  confirm_password: ''
})

// Methods
const onPasswordSubmit = async () => {
  isChangingPassword.value = true

  try {
    await authStore.apiCall('/v1/auth/change-password', {
      method: 'POST',
      body: {
        current_password: passwordState.current_password,
        new_password: passwordState.new_password
      }
    })

    toast.add({
      title: 'Password updated',
      description: 'Your password has been successfully changed',
      color: 'success'
    })

    // Reset form
    passwordState.current_password = ''
    passwordState.new_password = ''
    passwordState.confirm_password = ''
  } catch (error: any) {
    toast.add({
      title: 'Failed to change password',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isChangingPassword.value = false
  }
}

const fetchSessions = async () => {
  isLoadingSessions.value = true
  try {
    // Mock sessions for now
    sessions.value = [
      {
        id: '1',
        device: 'MacBook Pro',
        browser: 'Chrome 120',
        os: 'macOS 14.2',
        ip_address: '192.168.1.100',
        last_active: new Date().toISOString(),
        is_current: true
      },
      {
        id: '2',
        device: 'iPhone 15',
        browser: 'Safari',
        os: 'iOS 17.2',
        ip_address: '192.168.1.101',
        last_active: new Date(Date.now() - 3600000).toISOString(),
        is_current: false
      }
    ]
  } catch (error) {
    console.error('Failed to fetch sessions:', error)
  } finally {
    isLoadingSessions.value = false
  }
}

const revokeSession = async (sessionId: string) => {
  try {
    // In a real implementation, this would call an API endpoint
    toast.add({
      title: 'Session revoked',
      description: 'The session has been terminated',
      color: 'success'
    })
    
    // Remove from list
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
  } catch (error: any) {
    toast.add({
      title: 'Failed to revoke session',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  }
}

const enable2FA = async () => {
  if (totpCode.value.length !== 6) {
    toast.add({
      title: 'Invalid code',
      description: 'Please enter a 6-digit code',
      color: 'error'
    })
    return
  }

  isEnabling2FA.value = true
  try {
    // In a real implementation, this would enable 2FA
    has2FA.value = true
    showEnable2FA.value = false
    
    toast.add({
      title: '2FA enabled',
      description: 'Two-factor authentication has been enabled',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Failed to enable 2FA',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isEnabling2FA.value = false
  }
}

const formatRelativeTime = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
  return date.toLocaleDateString()
}

// Fetch sessions on mount
onMounted(() => {
  fetchSessions()
})
</script>