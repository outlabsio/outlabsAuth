<script setup lang="ts">
/**
 * User Detail Layout Wrapper
 * Provides tab navigation and user context for nested routes
 * Follows Nuxt nested routes pattern
 */

const route = useRoute()
const userStore = useUserStore()

// Extract user ID from route params
const userId = computed(() => route.params.id as string)

// Fetch user data when route changes
watch(userId, async (id) => {
  if (id) {
    await userStore.fetchUser(id)
    // Prefetch roles and permissions
    await Promise.all([
      userStore.fetchUserRoles(id),
      userStore.fetchUserPermissions(id)
    ])
  }
}, { immediate: true })

// User data from store
const user = computed(() => userStore.currentUser)
const isLoading = computed(() => userStore.isLoading)

// Tab navigation
const currentTab = computed({
  get: () => {
    // Map route path to tab index
    const path = route.path
    if (path.endsWith('/roles')) return 1
    if (path.endsWith('/permissions')) return 2
    if (path.endsWith('/activity')) return 3
    return 0 // Basic info (index)
  },
  set: (index: number) => {
    const tabs = [
      `/users/${userId.value}`,
      `/users/${userId.value}/roles`,
      `/users/${userId.value}/permissions`,
      `/users/${userId.value}/activity`
    ]
    navigateTo(tabs[index])
  }
})

// Status badge color
const statusColor = computed(() => {
  if (!user.value) return 'neutral'
  switch (user.value.status) {
    case 'active': return 'success'
    case 'suspended': return 'warning'
    case 'banned': return 'error'
    case 'deleted': return 'neutral'
    default: return 'neutral'
  }
})

// Cleanup on unmount
onUnmounted(() => {
  userStore.clearUser()
})
</script>

<template>
  <div class="container mx-auto py-6 px-4">
    <!-- Loading State -->
    <div v-if="isLoading && !user" class="flex items-center justify-center py-12">
      <div class="text-center">
        <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary mb-2" />
        <p class="text-sm text-muted">Loading user...</p>
      </div>
    </div>

    <!-- User Content -->
    <div v-else-if="user">
      <!-- Header -->
      <div class="mb-6">
        <div class="flex items-start justify-between">
          <!-- User Info -->
          <div class="flex items-start gap-4">
            <!-- Avatar Placeholder -->
            <div class="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
              <UIcon name="i-lucide-user" class="w-8 h-8 text-primary" />
            </div>

            <div>
              <div class="flex items-center gap-2 mb-1">
                <h1 class="text-2xl font-bold text-foreground">
                  {{ user.full_name || user.username || user.email }}
                </h1>
                <UBadge :color="statusColor" variant="subtle">
                  {{ user.status }}
                </UBadge>
                <UBadge v-if="user.is_superuser" color="primary" variant="subtle">
                  <UIcon name="i-lucide-shield" class="w-3 h-3 mr-1" />
                  Superuser
                </UBadge>
              </div>
              <p class="text-sm text-muted">{{ user.email }}</p>
              <p v-if="user.username && user.username !== user.email" class="text-xs text-muted">
                @{{ user.username }}
              </p>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-2">
            <UButton
              icon="i-lucide-arrow-left"
              label="Back to Users"
              variant="outline"
              color="neutral"
              @click="navigateTo('/users')"
            />
          </div>
        </div>
      </div>

      <!-- Tab Navigation -->
      <UTabs
        v-model="currentTab"
        :items="[
          {
            label: 'Basic Info',
            icon: 'i-lucide-user',
            to: `/users/${userId}`
          },
          {
            label: 'Roles',
            icon: 'i-lucide-shield',
            to: `/users/${userId}/roles`
          },
          {
            label: 'Permissions',
            icon: 'i-lucide-lock',
            to: `/users/${userId}/permissions`
          },
          {
            label: 'Activity',
            icon: 'i-lucide-activity',
            to: `/users/${userId}/activity`
          }
        ]"
        class="mb-6"
      />

      <!-- Tab Content (nested route outlet) -->
      <div class="mt-6">
        <NuxtPage :user="user" />
      </div>
    </div>

    <!-- Error State -->
    <div v-else class="flex items-center justify-center py-12">
      <div class="text-center">
        <UIcon name="i-lucide-alert-circle" class="w-12 h-12 text-error mb-4" />
        <p class="text-lg font-semibold text-foreground mb-2">User not found</p>
        <p class="text-sm text-muted mb-4">The requested user could not be found.</p>
        <UButton
          label="Back to Users"
          variant="outline"
          @click="navigateTo('/users')"
        />
      </div>
    </div>
  </div>
</template>
