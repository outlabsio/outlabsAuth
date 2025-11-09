<script setup lang="ts">
/**
 * Activity Tab
 * Display user activity tracking and statistics
 * Shows DAU/MAU status, last login, account age, etc.
 */

import type { User } from '~/types/auth'

const props = defineProps<{
  user: User
}>()

// Format date helper
function formatDate(date: string | undefined) {
  if (!date) return 'Never'
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Format date relative (e.g., "2 days ago")
function formatDateRelative(date: string | undefined) {
  if (!date) return 'Never'

  const now = new Date()
  const then = new Date(date)
  const diffMs = now.getTime() - then.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
  return `${Math.floor(diffDays / 365)} years ago`
}

// Calculate account age
function calculateAccountAge() {
  if (!props.user.created_at) return 'Unknown'

  const now = new Date()
  const created = new Date(props.user.created_at)
  const diffMs = now.getTime() - created.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 1) return 'Today'
  if (diffDays === 1) return '1 day'
  if (diffDays < 30) return `${diffDays} days`
  if (diffDays < 365) {
    const months = Math.floor(diffDays / 30)
    return `${months} ${months === 1 ? 'month' : 'months'}`
  }
  const years = Math.floor(diffDays / 365)
  const months = Math.floor((diffDays % 365) / 30)
  return `${years} ${years === 1 ? 'year' : 'years'}${months > 0 ? `, ${months} ${months === 1 ? 'month' : 'months'}` : ''}`
}

// Activity indicators (these would come from backend in real implementation)
const activityStatus = computed(() => {
  // These fields would be provided by backend's activity tracking
  return {
    is_dau: false, // Daily Active User
    is_wau: false, // Weekly Active User
    is_mau: false, // Monthly Active User
    last_active_at: props.user.updated_at,
    login_count: 0,
    last_action: 'Unknown'
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Activity Stats Grid -->
    <UCard>
      <template #header>
        <div>
          <h3 class="text-lg font-semibold text-foreground">Activity Statistics</h3>
          <p class="text-sm text-muted">User activity tracking and engagement metrics</p>
        </div>
      </template>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Last Login -->
        <div class="p-4 bg-muted/50 rounded-lg">
          <div class="flex items-center gap-2 mb-2">
            <UIcon name="i-lucide-clock" class="w-5 h-5 text-primary" />
            <p class="text-sm font-medium text-muted">Last Login</p>
          </div>
          <p class="text-xl font-bold text-foreground">
            {{ formatDateRelative(user.updated_at) }}
          </p>
          <p class="text-xs text-muted mt-1">
            {{ formatDate(user.updated_at) }}
          </p>
        </div>

        <!-- Account Created -->
        <div class="p-4 bg-muted/50 rounded-lg">
          <div class="flex items-center gap-2 mb-2">
            <UIcon name="i-lucide-calendar-plus" class="w-5 h-5 text-primary" />
            <p class="text-sm font-medium text-muted">Account Created</p>
          </div>
          <p class="text-xl font-bold text-foreground">
            {{ formatDateRelative(user.created_at) }}
          </p>
          <p class="text-xs text-muted mt-1">
            {{ formatDate(user.created_at) }}
          </p>
        </div>

        <!-- Account Age -->
        <div class="p-4 bg-muted/50 rounded-lg">
          <div class="flex items-center gap-2 mb-2">
            <UIcon name="i-lucide-calendar" class="w-5 h-5 text-primary" />
            <p class="text-sm font-medium text-muted">Account Age</p>
          </div>
          <p class="text-xl font-bold text-foreground">
            {{ calculateAccountAge() }}
          </p>
          <p class="text-xs text-muted mt-1">
            Member since {{ user.created_at ? new Date(user.created_at).getFullYear() : 'Unknown' }}
          </p>
        </div>
      </div>
    </UCard>

    <!-- Activity Status Indicators -->
    <UCard>
      <template #header>
        <div>
          <h3 class="text-lg font-semibold text-foreground">Activity Status</h3>
          <p class="text-sm text-muted">Daily, weekly, and monthly activity indicators</p>
        </div>
      </template>

      <div class="space-y-3">
        <!-- DAU Status -->
        <div class="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-success/20 flex items-center justify-center">
              <UIcon name="i-lucide-zap" class="w-5 h-5 text-success" />
            </div>
            <div>
              <p class="text-sm font-medium text-foreground">Daily Active User (DAU)</p>
              <p class="text-xs text-muted">Active within the last 24 hours</p>
            </div>
          </div>
          <UBadge :color="activityStatus.is_dau ? 'success' : 'neutral'" variant="subtle">
            {{ activityStatus.is_dau ? 'Active Today' : 'Inactive' }}
          </UBadge>
        </div>

        <!-- WAU Status -->
        <div class="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
              <UIcon name="i-lucide-calendar-days" class="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <p class="text-sm font-medium text-foreground">Weekly Active User (WAU)</p>
              <p class="text-xs text-muted">Active within the last 7 days</p>
            </div>
          </div>
          <UBadge :color="activityStatus.is_wau ? 'blue' : 'neutral'" variant="subtle">
            {{ activityStatus.is_wau ? 'Active This Week' : 'Inactive' }}
          </UBadge>
        </div>

        <!-- MAU Status -->
        <div class="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
              <UIcon name="i-lucide-calendar-range" class="w-5 h-5 text-primary" />
            </div>
            <div>
              <p class="text-sm font-medium text-foreground">Monthly Active User (MAU)</p>
              <p class="text-xs text-muted">Active within the last 30 days</p>
            </div>
          </div>
          <UBadge :color="activityStatus.is_mau ? 'primary' : 'neutral'" variant="subtle">
            {{ activityStatus.is_mau ? 'Active This Month' : 'Inactive' }}
          </UBadge>
        </div>
      </div>

      <div class="mt-4 p-3 bg-blue-500/10 rounded-lg">
        <div class="flex items-start gap-2">
          <UIcon name="i-lucide-info" class="w-4 h-4 text-blue-500 mt-0.5" />
          <div class="text-xs text-muted">
            <p class="font-medium text-foreground mb-1">About Activity Tracking</p>
            <p>Activity status is automatically updated based on user login and interaction timestamps. DAU, WAU, and MAU metrics help track user engagement and retention.</p>
          </div>
        </div>
      </div>
    </UCard>

    <!-- Account Details -->
    <UCard>
      <template #header>
        <div>
          <h3 class="text-lg font-semibold text-foreground">Account Details</h3>
          <p class="text-sm text-muted">System information and metadata</p>
        </div>
      </template>

      <div class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <!-- User ID -->
          <div>
            <p class="text-sm font-medium text-foreground mb-1">User ID</p>
            <code class="text-xs text-muted font-mono bg-muted px-2 py-1 rounded">
              {{ user.id }}
            </code>
          </div>

          <!-- Email Verified -->
          <div>
            <p class="text-sm font-medium text-foreground mb-1">Email Status</p>
            <UBadge :color="user.email_verified ? 'success' : 'warning'" variant="subtle">
              <UIcon :name="user.email_verified ? 'i-lucide-check-circle' : 'i-lucide-alert-circle'" class="w-3 h-3 mr-1" />
              {{ user.email_verified ? 'Verified' : 'Unverified' }}
            </UBadge>
          </div>

          <!-- Status -->
          <div>
            <p class="text-sm font-medium text-foreground mb-1">Account Status</p>
            <UBadge
              :color="user.status === 'active' ? 'success' : user.status === 'suspended' ? 'warning' : 'error'"
              variant="subtle"
            >
              {{ user.status }}
            </UBadge>
          </div>

          <!-- Superuser -->
          <div>
            <p class="text-sm font-medium text-foreground mb-1">Superuser</p>
            <UBadge :color="user.is_superuser ? 'primary' : 'neutral'" variant="subtle">
              {{ user.is_superuser ? 'Yes' : 'No' }}
            </UBadge>
          </div>
        </div>

        <!-- Metadata (if exists) -->
        <div v-if="user.metadata && Object.keys(user.metadata).length > 0" class="pt-4 border-t border-border">
          <p class="text-sm font-medium text-foreground mb-2">Additional Metadata</p>
          <pre class="text-xs bg-muted p-3 rounded overflow-x-auto">{{ JSON.stringify(user.metadata, null, 2) }}</pre>
        </div>
      </div>
    </UCard>
  </div>
</template>
