<template>
  <UCard class="mt-4">
    <template #header>
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold">Active Sessions</h3>
          <p class="text-sm text-muted-foreground mt-1">
            View and manage your active login sessions across devices
          </p>
        </div>
        <UButton 
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          @click="fetchSessions"
          :loading="isLoading"
        >
          Refresh
        </UButton>
      </div>
    </template>

    <!-- Current Session -->
    <div class="mb-6">
      <h4 class="font-medium mb-3">Current Session</h4>
      <UCard class="border-primary bg-primary/5">
        <div class="flex items-start justify-between">
          <div class="flex items-start gap-3">
            <div class="p-2 bg-primary/10 rounded-lg">
              <UIcon name="i-lucide-monitor" class="h-5 w-5 text-primary" />
            </div>
            <div class="space-y-1">
              <p class="font-medium">{{ currentDevice.name }}</p>
              <p class="text-sm text-muted-foreground">
                {{ currentDevice.browser }} on {{ currentDevice.os }}
              </p>
              <p class="text-xs text-muted-foreground">
                {{ currentDevice.ip }} · Active now
              </p>
            </div>
          </div>
          <UBadge color="primary" variant="subtle">
            This device
          </UBadge>
        </div>
      </UCard>
    </div>

    <!-- Other Sessions -->
    <div>
      <h4 class="font-medium mb-3">Other Sessions</h4>
      
      <div v-if="isLoading" class="flex justify-center py-8">
        <UIcon name="i-lucide-loader" class="h-6 w-6 animate-spin text-primary" />
      </div>

      <div v-else-if="otherSessions.length > 0" class="space-y-3">
        <UCard 
          v-for="session in otherSessions" 
          :key="session.id"
          class="hover:shadow-md transition-shadow"
        >
          <div class="flex items-start justify-between">
            <div class="flex items-start gap-3">
              <div class="p-2 bg-muted rounded-lg">
                <UIcon 
                  :name="getDeviceIcon(session.device_type)" 
                  class="h-5 w-5 text-muted-foreground" 
                />
              </div>
              <div class="space-y-1">
                <p class="font-medium">{{ session.device_name }}</p>
                <p class="text-sm text-muted-foreground">
                  {{ session.browser }} on {{ session.os }}
                </p>
                <p class="text-xs text-muted-foreground">
                  {{ session.ip_address }} · {{ session.location }}
                </p>
                <p class="text-xs text-muted-foreground">
                  Last active {{ formatLastActive(session.last_active) }}
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <UBadge 
                v-if="isSessionExpired(session.last_active)"
                color="warning"
                variant="subtle"
                size="xs"
              >
                Inactive
              </UBadge>
              <UButton
                variant="ghost"
                size="sm"
                color="error"
                icon="i-lucide-log-out"
                @click="confirmRevoke(session)"
              >
                Sign out
              </UButton>
            </div>
          </div>
        </UCard>
      </div>

      <div v-else class="text-center py-8 border-2 border-dashed border-border rounded-lg">
        <UIcon name="i-lucide-monitor-off" class="h-8 w-8 text-muted-foreground mb-2" />
        <p class="text-muted-foreground">No other active sessions</p>
        <p class="text-sm text-muted-foreground mt-1">
          You're only signed in on this device
        </p>
      </div>
    </div>

    <!-- Sign Out All Button -->
    <div v-if="otherSessions.length > 0" class="mt-6 pt-6 border-t">
      <div class="flex items-center justify-between">
        <div>
          <p class="font-medium">Sign out of all other sessions</p>
          <p class="text-sm text-muted-foreground">
            This will sign you out of all devices except this one
          </p>
        </div>
        <UButton 
          variant="outline"
          color="error"
          @click="confirmRevokeAll"
        >
          Sign out all
        </UButton>
      </div>
    </div>

    <!-- Revoke Confirmation Modal -->
    <ConfirmationModal
      v-model="showRevokeConfirm"
      :title="revokeTitle"
      :description="revokeDescription"
      confirm-text="Sign out"
      confirm-color="error"
      @confirm="handleRevoke"
    />
  </UCard>
</template>

<script setup lang="ts">
interface Session {
  id: string
  device_name: string
  device_type: 'desktop' | 'mobile' | 'tablet'
  browser: string
  os: string
  ip_address: string
  location: string
  last_active: string
  created_at: string
}

// Stores
const authStore = useAuthStore()
const toast = useToast()

// State
const isLoading = ref(false)
const sessions = ref<Session[]>([])
const showRevokeConfirm = ref(false)
const sessionToRevoke = ref<Session | null>(null)
const revokeAll = ref(false)

// Current device info (mock data)
const currentDevice = {
  name: 'MacBook Pro',
  browser: 'Chrome 120',
  os: 'macOS 14.2',
  ip: '192.168.1.100'
}

// Computed
const otherSessions = computed(() => sessions.value.filter(s => !s.is_current))

const revokeTitle = computed(() => 
  revokeAll.value ? 'Sign out of all devices' : 'Sign out of this device'
)

const revokeDescription = computed(() => 
  revokeAll.value 
    ? 'Are you sure you want to sign out of all other devices? You will remain signed in on this device.'
    : `Are you sure you want to sign out of "${sessionToRevoke.value?.device_name}"?`
)

// Methods
const fetchSessions = async () => {
  isLoading.value = true
  try {
    // Mock data - in a real app, this would fetch from API
    sessions.value = [
      {
        id: '1',
        device_name: 'iPhone 15 Pro',
        device_type: 'mobile',
        browser: 'Safari',
        os: 'iOS 17.2',
        ip_address: '192.168.1.101',
        location: 'San Francisco, CA',
        last_active: new Date(Date.now() - 3600000).toISOString(),
        created_at: new Date(Date.now() - 86400000).toISOString(),
        is_current: false
      },
      {
        id: '2',
        device_name: 'iPad Pro',
        device_type: 'tablet',
        browser: 'Safari',
        os: 'iPadOS 17.2',
        ip_address: '192.168.1.102',
        location: 'San Francisco, CA',
        last_active: new Date(Date.now() - 7200000).toISOString(),
        created_at: new Date(Date.now() - 172800000).toISOString(),
        is_current: false
      },
      {
        id: '3',
        device_name: 'Windows Desktop',
        device_type: 'desktop',
        browser: 'Edge 120',
        os: 'Windows 11',
        ip_address: '192.168.1.103',
        location: 'New York, NY',
        last_active: new Date(Date.now() - 86400000 * 5).toISOString(),
        created_at: new Date(Date.now() - 86400000 * 10).toISOString(),
        is_current: false
      }
    ]
  } catch (error) {
    console.error('Failed to fetch sessions:', error)
    toast.add({
      title: 'Failed to load sessions',
      description: 'Unable to fetch your active sessions',
      color: 'error'
    })
  } finally {
    isLoading.value = false
  }
}

const getDeviceIcon = (type: string) => {
  const icons = {
    desktop: 'i-lucide-monitor',
    mobile: 'i-lucide-smartphone',
    tablet: 'i-lucide-tablet'
  }
  return icons[type] || 'i-lucide-monitor'
}

const formatLastActive = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

const isSessionExpired = (lastActive: string) => {
  const date = new Date(lastActive)
  const now = new Date()
  const diffDays = Math.floor((now.getTime() - date.getTime()) / 86400000)
  return diffDays > 7
}

const confirmRevoke = (session: Session) => {
  sessionToRevoke.value = session
  revokeAll.value = false
  showRevokeConfirm.value = true
}

const confirmRevokeAll = () => {
  revokeAll.value = true
  showRevokeConfirm.value = true
}

const handleRevoke = async () => {
  try {
    if (revokeAll.value) {
      // Revoke all sessions
      await authStore.apiCall('/v1/auth/sessions/revoke-all', {
        method: 'POST'
      })
      
      sessions.value = sessions.value.filter(s => s.is_current)
      
      toast.add({
        title: 'Sessions revoked',
        description: 'You have been signed out of all other devices',
        color: 'success'
      })
    } else if (sessionToRevoke.value) {
      // Revoke single session
      await authStore.apiCall(`/v1/auth/sessions/${sessionToRevoke.value.id}/revoke`, {
        method: 'POST'
      })
      
      sessions.value = sessions.value.filter(s => s.id !== sessionToRevoke.value?.id)
      
      toast.add({
        title: 'Session revoked',
        description: 'The device has been signed out',
        color: 'success'
      })
    }
  } catch (error: any) {
    toast.add({
      title: 'Failed to revoke session',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    showRevokeConfirm.value = false
    sessionToRevoke.value = null
    revokeAll.value = false
  }
}

// Load sessions on mount
onMounted(() => {
  fetchSessions()
})
</script>