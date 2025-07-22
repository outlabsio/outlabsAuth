<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">Platform Management</h1>
        <p class="text-muted-foreground mt-1">
          Configure platform settings and manage system-wide configurations
        </p>
      </div>
    </div>

    <!-- Platform Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <UCard>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted-foreground">Total Users</p>
            <p class="text-2xl font-bold">{{ stats.totalUsers }}</p>
          </div>
          <UIcon name="i-lucide-users" class="h-8 w-8 text-primary" />
        </div>
      </UCard>

      <UCard>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted-foreground">Active Entities</p>
            <p class="text-2xl font-bold">{{ stats.activeEntities }}</p>
          </div>
          <UIcon name="i-lucide-building" class="h-8 w-8 text-success" />
        </div>
      </UCard>

      <UCard>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted-foreground">Total Roles</p>
            <p class="text-2xl font-bold">{{ stats.totalRoles }}</p>
          </div>
          <UIcon name="i-lucide-shield" class="h-8 w-8 text-info" />
        </div>
      </UCard>

      <UCard>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted-foreground">Custom Permissions</p>
            <p class="text-2xl font-bold">{{ stats.customPermissions }}</p>
          </div>
          <UIcon name="i-lucide-key" class="h-8 w-8 text-warning" />
        </div>
      </UCard>
    </div>

    <!-- Quick Actions -->
    <div>
      <h2 class="text-lg font-semibold mb-4">Quick Actions</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <UCard class="hover:shadow-md transition-shadow cursor-pointer" @click="navigateTo('/platform/users')">
          <div class="flex items-center gap-3">
            <div class="p-3 bg-primary/10 rounded-lg">
              <UIcon name="i-lucide-user-cog" class="h-6 w-6 text-primary" />
            </div>
            <div>
              <h3 class="font-medium">User Management</h3>
              <p class="text-sm text-muted-foreground">Manage platform-wide users</p>
            </div>
          </div>
        </UCard>

        <UCard class="hover:shadow-md transition-shadow cursor-pointer" @click="navigateTo('/platform/settings')">
          <div class="flex items-center gap-3">
            <div class="p-3 bg-success/10 rounded-lg">
              <UIcon name="i-lucide-settings" class="h-6 w-6 text-success" />
            </div>
            <div>
              <h3 class="font-medium">Platform Settings</h3>
              <p class="text-sm text-muted-foreground">Configure platform options</p>
            </div>
          </div>
        </UCard>

        <UCard class="hover:shadow-md transition-shadow cursor-pointer" @click="navigateTo('/platform/entity-types')">
          <div class="flex items-center gap-3">
            <div class="p-3 bg-info/10 rounded-lg">
              <UIcon name="i-lucide-folder-tree" class="h-6 w-6 text-info" />
            </div>
            <div>
              <h3 class="font-medium">Entity Types</h3>
              <p class="text-sm text-muted-foreground">Manage entity type definitions</p>
            </div>
          </div>
        </UCard>
      </div>
    </div>

    <!-- Recent Activity -->
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold">Recent Activity</h2>
          <UButton variant="ghost" size="sm" icon="i-lucide-refresh-cw" @click="fetchRecentActivity">
            Refresh
          </UButton>
        </div>
      </template>

      <div v-if="isLoadingActivity" class="flex justify-center py-8">
        <UIcon name="i-lucide-loader" class="h-6 w-6 animate-spin text-primary" />
      </div>

      <div v-else-if="recentActivity.length > 0" class="space-y-3">
        <div v-for="activity in recentActivity" :key="activity.id" class="flex items-start gap-3 p-3 rounded-lg hover:bg-muted/50">
          <UIcon :name="getActivityIcon(activity.type)" class="h-5 w-5 mt-0.5" :class="getActivityIconClass(activity.type)" />
          <div class="flex-1">
            <p class="text-sm">{{ activity.description }}</p>
            <p class="text-xs text-muted-foreground">{{ formatRelativeTime(activity.created_at) }}</p>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-8">
        <p class="text-muted-foreground">No recent activity</p>
      </div>
    </UCard>
  </div>
</template>

<script setup lang="ts">
// Stores
const authStore = useAuthStore()
const contextStore = useContextStore()
const router = useRouter()

// State
const stats = reactive({
  totalUsers: 0,
  activeEntities: 0,
  totalRoles: 0,
  customPermissions: 0
})

const recentActivity = ref<any[]>([])
const isLoadingActivity = ref(false)

// Fetch platform statistics
const fetchStats = async () => {
  try {
    // In a real implementation, this would be a dedicated endpoint
    // For now, we'll fetch from existing endpoints
    const [usersResponse, entitiesResponse, rolesResponse] = await Promise.all([
      authStore.apiCall<{ total: number }>('/v1/users?page_size=1', { headers: contextStore.getContextHeaders }),
      authStore.apiCall<{ total: number }>('/v1/entities?page_size=1&status=active', { headers: contextStore.getContextHeaders }),
      authStore.apiCall<{ total: number }>('/v1/roles?page_size=1', { headers: contextStore.getContextHeaders })
    ])

    stats.totalUsers = usersResponse.total || 0
    stats.activeEntities = entitiesResponse.total || 0
    stats.totalRoles = rolesResponse.total || 0
    // Custom permissions would need a dedicated endpoint
    stats.customPermissions = 0
  } catch (error) {
    console.error('Failed to fetch platform stats:', error)
  }
}

// Fetch recent activity
const fetchRecentActivity = async () => {
  isLoadingActivity.value = true
  try {
    // In a real implementation, this would fetch from an audit log endpoint
    // For now, we'll return mock data
    recentActivity.value = [
      {
        id: '1',
        type: 'user_created',
        description: 'New user john.doe@example.com was created',
        created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString()
      },
      {
        id: '2',
        type: 'entity_updated',
        description: 'Entity "Sales Department" was updated',
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString()
      },
      {
        id: '3',
        type: 'role_created',
        description: 'New role "Marketing Manager" was created',
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString()
      }
    ]
  } catch (error) {
    console.error('Failed to fetch recent activity:', error)
    recentActivity.value = []
  } finally {
    isLoadingActivity.value = false
  }
}

// Utility functions
const getActivityIcon = (type: string) => {
  const icons: Record<string, string> = {
    user_created: 'i-lucide-user-plus',
    user_updated: 'i-lucide-user-cog',
    user_deleted: 'i-lucide-user-minus',
    entity_created: 'i-lucide-plus-circle',
    entity_updated: 'i-lucide-edit',
    entity_deleted: 'i-lucide-trash',
    role_created: 'i-lucide-shield-plus',
    role_updated: 'i-lucide-shield',
    role_deleted: 'i-lucide-shield-x'
  }
  return icons[type] || 'i-lucide-activity'
}

const getActivityIconClass = (type: string) => {
  if (type.includes('created')) return 'text-success'
  if (type.includes('updated')) return 'text-info'
  if (type.includes('deleted')) return 'text-error'
  return 'text-muted-foreground'
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

// Check permissions
const canAccessPlatformManagement = computed(() => {
  // Only system users should access platform management
  return authStore.currentUser?.is_system_user || false
})

// Redirect if not authorized
onMounted(() => {
  if (!canAccessPlatformManagement.value) {
    router.push('/')
  } else {
    fetchStats()
    fetchRecentActivity()
  }
})

// SEO
useHead({
  title: 'Platform Management',
  meta: [
    {
      name: 'description',
      content: 'Manage platform settings and system-wide configurations'
    }
  ]
})
</script>