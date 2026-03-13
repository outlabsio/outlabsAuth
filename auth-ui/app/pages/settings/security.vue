<script setup lang="ts">
const authStore = useAuthStore()
const currentUser = computed(() => authStore.currentUser)

const securityAlert = computed(() => {
  if (!currentUser.value) return null

  if (currentUser.value.status === 'suspended') {
    return {
      color: 'warning' as const,
      icon: 'i-lucide-shield-alert',
      title: 'This account is currently suspended',
      description: 'Access is restricted until the suspension expires or an administrator reactivates the account.'
    }
  }

  if (currentUser.value.status === 'banned') {
    return {
      color: 'error' as const,
      icon: 'i-lucide-ban',
      title: 'This account is banned',
      description: 'Administrative intervention is required before this account can authenticate again.'
    }
  }

  if (!currentUser.value.email_verified) {
    return {
      color: 'warning' as const,
      icon: 'i-lucide-mail-warning',
      title: 'Email verification is still pending',
      description: 'This account can authenticate, but email verification has not been completed yet.'
    }
  }

  return null
})

function formatDateTime(dateString?: string | null): string {
  if (!dateString) return 'Not available'

  return new Date(dateString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
}

function formatRelativeTime(dateString?: string | null): string {
  if (!dateString) return 'No recent activity'

  const then = new Date(dateString)
  const now = new Date()
  const diffMinutes = Math.floor((now.getTime() - then.getTime()) / 60000)

  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`

  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`

  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function statusColor(status?: string): 'success' | 'warning' | 'error' | 'neutral' {
  if (status === 'active') return 'success'
  if (status === 'suspended') return 'warning'
  if (status === 'banned' || status === 'deleted') return 'error'
  return 'neutral'
}
</script>

<template>
  <UDashboardPanel id="settings-security">
    <template #header>
      <UDashboardNavbar title="Security Overview">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            to="/settings"
            icon="i-lucide-arrow-left"
            label="Back to Settings"
            color="neutral"
            variant="ghost"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="space-y-6 max-w-5xl">
        <UAlert
          v-if="securityAlert"
          :color="securityAlert.color"
          variant="subtle"
          :icon="securityAlert.icon"
          :title="securityAlert.title"
          :description="securityAlert.description"
        />

        <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <UCard>
            <template #header>
              <div class="flex items-center gap-3">
                <UIcon name="i-lucide-key-round" class="w-5 h-5" />
                <h3 class="text-lg font-semibold">Password</h3>
              </div>
            </template>

            <div class="space-y-4">
              <p class="text-sm text-muted">
                Change your password through the dedicated secure flow. The backend records the last password change timestamp for audit visibility.
              </p>

              <div>
                <label class="text-sm font-medium text-muted">Last Password Change</label>
                <p class="mt-1 text-base">
                  {{ formatDateTime(currentUser?.last_password_change) }}
                </p>
              </div>

              <div>
                <label class="text-sm font-medium text-muted">Password Policy</label>
                <p class="mt-1 text-base">Minimum 8 characters</p>
              </div>
            </div>

            <template #footer>
              <div class="flex justify-end">
                <UButton
                  to="/settings/password"
                  icon="i-lucide-key"
                  label="Change Password"
                />
              </div>
            </template>
          </UCard>

          <UCard>
            <template #header>
              <div class="flex items-center gap-3">
                <UIcon name="i-lucide-shield" class="w-5 h-5" />
                <h3 class="text-lg font-semibold">Account State</h3>
              </div>
            </template>

            <div class="space-y-4">
              <div>
                <label class="text-sm font-medium text-muted">Current Status</label>
                <div class="mt-1">
                  <UBadge
                    :color="statusColor(currentUser?.status)"
                    variant="subtle"
                  >
                    {{ currentUser?.status || 'unknown' }}
                  </UBadge>
                </div>
              </div>

              <div>
                <label class="text-sm font-medium text-muted">Email Verification</label>
                <div class="mt-1">
                  <UBadge
                    :color="currentUser?.email_verified ? 'success' : 'warning'"
                    variant="subtle"
                  >
                    {{ currentUser?.email_verified ? 'Verified' : 'Pending' }}
                  </UBadge>
                </div>
              </div>

              <div>
                <label class="text-sm font-medium text-muted">Locked Until</label>
                <p class="mt-1 text-base">{{ formatDateTime(currentUser?.locked_until) }}</p>
              </div>

              <div>
                <label class="text-sm font-medium text-muted">Suspended Until</label>
                <p class="mt-1 text-base">{{ formatDateTime(currentUser?.suspended_until) }}</p>
              </div>
            </div>
          </UCard>

          <UCard>
            <template #header>
              <div class="flex items-center gap-3">
                <UIcon name="i-lucide-activity" class="w-5 h-5" />
                <h3 class="text-lg font-semibold">Audit Signals</h3>
              </div>
            </template>

            <div class="space-y-4">
              <div>
                <label class="text-sm font-medium text-muted">Last Login</label>
                <p class="mt-1 text-base">{{ formatDateTime(currentUser?.last_login) }}</p>
                <p class="text-xs text-muted mt-1">{{ formatRelativeTime(currentUser?.last_login) }}</p>
              </div>

              <div>
                <label class="text-sm font-medium text-muted">Last Activity</label>
                <p class="mt-1 text-base">{{ formatDateTime(currentUser?.last_activity) }}</p>
                <p class="text-xs text-muted mt-1">{{ formatRelativeTime(currentUser?.last_activity) }}</p>
              </div>
            </div>
          </UCard>

          <UCard>
            <template #header>
              <div class="flex items-center gap-3">
                <UIcon name="i-lucide-key-square" class="w-5 h-5" />
                <h3 class="text-lg font-semibold">Programmatic Access</h3>
              </div>
            </template>

            <div class="space-y-4">
              <p class="text-sm text-muted">
                API key management is handled from the shared admin UI and enforced by the backend permission model.
              </p>

              <div>
                <label class="text-sm font-medium text-muted">API Keys</label>
                <div class="mt-1">
                  <UBadge
                    :color="authStore.features.api_keys ? 'success' : 'neutral'"
                    variant="subtle"
                  >
                    {{ authStore.features.api_keys ? 'Enabled' : 'Disabled' }}
                  </UBadge>
                </div>
              </div>

              <div>
                <label class="text-sm font-medium text-muted">Activity Tracking</label>
                <div class="mt-1">
                  <UBadge
                    :color="authStore.features.activity_tracking ? 'success' : 'neutral'"
                    variant="subtle"
                  >
                    {{ authStore.features.activity_tracking ? 'Enabled' : 'Disabled' }}
                  </UBadge>
                </div>
              </div>
            </div>

            <template #footer>
              <div class="flex justify-end">
                <UButton
                  to="/api-keys"
                  icon="i-lucide-key"
                  label="Manage API Keys"
                  color="neutral"
                  variant="outline"
                />
              </div>
            </template>
          </UCard>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
