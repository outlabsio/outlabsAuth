<script setup lang="ts">
import type { User } from '~/types/auth.types'

const props = defineProps<{
  user: User
}>()

// Stores
const usersStore = useUsersStore()

// Mock activity data (in a real app, this would come from an API)
const activities = ref([
  {
    id: '1',
    type: 'login',
    action: 'User logged in',
    timestamp: new Date().toISOString(),
    ip_address: '192.168.1.1',
    user_agent: 'Mozilla/5.0...',
    success: true
  },
  {
    id: '2', 
    type: 'password_change',
    action: 'Password changed',
    timestamp: new Date(Date.now() - 86400000).toISOString(),
    success: true
  },
  {
    id: '3',
    type: 'profile_update',
    action: 'Profile updated',
    timestamp: new Date(Date.now() - 172800000).toISOString(),
    changes: ['first_name', 'last_name'],
    success: true
  },
  {
    id: '4',
    type: 'login_failed',
    action: 'Failed login attempt',
    timestamp: new Date(Date.now() - 259200000).toISOString(),
    ip_address: '10.0.0.1',
    reason: 'Invalid password',
    success: false
  }
])

// Methods
const getActivityIcon = (type: string) => {
  switch (type) {
    case 'login':
      return 'i-lucide-log-in'
    case 'login_failed':
      return 'i-lucide-shield-x'
    case 'logout':
      return 'i-lucide-log-out'
    case 'password_change':
      return 'i-lucide-key'
    case 'profile_update':
      return 'i-lucide-user-check'
    case 'entity_added':
      return 'i-lucide-building-2'
    case 'role_assigned':
      return 'i-lucide-shield'
    default:
      return 'i-lucide-activity'
  }
}

const getActivityColor = (activity: any) => {
  if (!activity.success) return 'error'
  switch (activity.type) {
    case 'login':
      return 'success'
    case 'password_change':
      return 'warning'
    default:
      return 'primary'
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Summary Stats -->
    <div class="grid grid-cols-2 gap-4">
      <UCard>
        <div class="text-center">
          <p class="text-2xl font-bold">{{ user.failed_login_attempts || 0 }}</p>
          <p class="text-sm text-gray-500">Failed Login Attempts</p>
        </div>
      </UCard>
      
      <UCard>
        <div class="text-center">
          <p class="text-2xl font-bold">
            {{ user.last_login ? '1d ago' : 'Never' }}
          </p>
          <p class="text-sm text-gray-500">Last Activity</p>
        </div>
      </UCard>
    </div>

    <!-- Activity Timeline -->
    <div>
      <h4 class="text-sm font-medium mb-4">Recent Activity</h4>
      
      <div class="space-y-3">
        <div v-for="activity in activities" :key="activity.id">
          <div class="flex gap-3">
            <!-- Icon -->
            <div class="flex-shrink-0">
              <div 
                :class="[
                  'w-8 h-8 rounded-full flex items-center justify-center',
                  activity.success ? 'bg-gray-100 dark:bg-gray-800' : 'bg-red-100 dark:bg-red-900/20'
                ]"
              >
                <UIcon 
                  :name="getActivityIcon(activity.type)" 
                  :class="[
                    'h-4 w-4',
                    activity.success ? 'text-gray-600 dark:text-gray-400' : 'text-red-600 dark:text-red-400'
                  ]"
                />
              </div>
            </div>

            <!-- Content -->
            <div class="flex-1 min-w-0">
              <div class="flex items-start justify-between gap-2">
                <div class="flex-1">
                  <p class="text-sm font-medium">{{ activity.action }}</p>
                  
                  <!-- Additional Details -->
                  <div class="mt-1 space-y-1">
                    <p v-if="activity.ip_address" class="text-xs text-gray-500">
                      IP: {{ activity.ip_address }}
                    </p>
                    <p v-if="activity.reason" class="text-xs text-red-500">
                      {{ activity.reason }}
                    </p>
                    <p v-if="activity.changes" class="text-xs text-gray-500">
                      Changed: {{ activity.changes.join(', ') }}
                    </p>
                  </div>
                </div>

                <span class="text-xs text-gray-500 whitespace-nowrap">
                  {{ usersStore.formatDate(activity.timestamp) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Divider -->
          <USeparator v-if="activities.indexOf(activity) < activities.length - 1" class="my-3" />
        </div>
      </div>
    </div>

    <!-- Note -->
    <div>
      <UAlert
        icon="i-lucide-info"
        variant="subtle"
        description="Activity logs are retained for 90 days. For detailed audit trails, contact your system administrator."
      />
    </div>
  </div>
</template>