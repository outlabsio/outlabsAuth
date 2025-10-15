<script setup lang="ts">
// Auth is handled by global middleware

// Store references
const userStore = useUserStore()

// Computed properties
const userName = computed(() => {
  if (!userStore.user) return 'User'
  return userStore.user.profile.first_name || userStore.user.username || userStore.user.email
})
</script>

<template>
  <div>
    <UContainer>
      <div class="py-8">
        <h1 class="text-3xl font-bold mb-4">Welcome back, {{ userName }}!</h1>
        <p class="text-gray-600 dark:text-gray-400 mb-8">
          This is your OutlabsAuth dashboard. Navigate using the sidebar to manage entities, users, roles, and permissions.
        </p>

        <!-- Quick Stats -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <UCard>
            <div class="text-center">
              <UIcon name="i-lucide-building" class="h-8 w-8 text-primary mb-2" />
              <h3 class="text-lg font-semibold">Entities</h3>
              <p class="text-3xl font-bold">--</p>
            </div>
          </UCard>

          <UCard>
            <div class="text-center">
              <UIcon name="i-lucide-users" class="h-8 w-8 text-primary mb-2" />
              <h3 class="text-lg font-semibold">Users</h3>
              <p class="text-3xl font-bold">--</p>
            </div>
          </UCard>

          <UCard>
            <div class="text-center">
              <UIcon name="i-lucide-shield" class="h-8 w-8 text-primary mb-2" />
              <h3 class="text-lg font-semibold">Roles</h3>
              <p class="text-3xl font-bold">--</p>
            </div>
          </UCard>

          <UCard>
            <div class="text-center">
              <UIcon name="i-lucide-key" class="h-8 w-8 text-primary mb-2" />
              <h3 class="text-lg font-semibold">Permissions</h3>
              <p class="text-3xl font-bold">--</p>
            </div>
          </UCard>
        </div>

        <!-- Recent Activity -->
        <UCard>
          <template #header>
            <h2 class="text-xl font-semibold">Recent Activity</h2>
          </template>
          <div class="text-center py-8 text-gray-500">
            <UIcon name="i-lucide-activity" class="h-12 w-12 mb-4" />
            <p>No recent activity to display</p>
          </div>
        </UCard>
      </div>
    </UContainer>
  </div>
</template>