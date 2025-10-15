<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const route = useRoute()

const links = [[{
  label: 'General',
  icon: 'i-lucide-settings',
  to: '/settings',
  exact: true
}, {
  label: 'Security',
  icon: 'i-lucide-shield',
  to: '/settings/security'
}, {
  label: 'Notifications',
  icon: 'i-lucide-bell',
  to: '/settings/notifications'
}, {
  label: 'Rate Limiting',
  icon: 'i-lucide-gauge',
  to: '/settings/rate-limiting'
}, {
  label: 'System Users',
  icon: 'i-lucide-users-2',
  to: '/settings/users'
}]] satisfies NavigationMenuItem[][]

// Breadcrumb items
const breadcrumbItems = computed(() => {
  const items: any[] = [
    { label: 'Home', to: '/' },
    { label: 'Settings', to: '/settings' }
  ]
  
  // Add current page to breadcrumbs if not on general
  if (route.path === '/settings/security') {
    items.push({ label: 'Security' })
  } else if (route.path === '/settings/notifications') {
    items.push({ label: 'Notifications' })
  } else if (route.path === '/settings/rate-limiting') {
    items.push({ label: 'Rate Limiting' })
  } else if (route.path === '/settings/users') {
    items.push({ label: 'System Users' })
  }
  
  return items
})

// Page title based on current route
const pageTitle = computed(() => {
  if (route.path === '/settings/security') return 'Security Settings'
  if (route.path === '/settings/notifications') return 'Notification Settings'
  if (route.path === '/settings/rate-limiting') return 'Rate Limiting'
  if (route.path === '/settings/users') return 'System Users'
  return 'General Settings'
})

// Page description based on current route
const pageDescription = computed(() => {
  if (route.path === '/settings/security') return 'Configure password policies and session settings'
  if (route.path === '/settings/notifications') return 'Configure notification channels and preferences'
  if (route.path === '/settings/rate-limiting') return 'Configure API rate limiting rules'
  if (route.path === '/settings/users') return 'Manage all users across the system'
  return 'Configure general platform settings'
})
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <!-- Breadcrumbs and Title -->
      <div class="border-b border-default">
        <div class="px-4 sm:px-6 lg:px-8 py-6">
          <UBreadcrumb :items="breadcrumbItems" class="mb-4" />
          <div class="flex items-center justify-between">
            <div>
              <h1 class="text-2xl font-bold">{{ pageTitle }}</h1>
              <p class="text-muted-foreground mt-1">{{ pageDescription }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Dashboard Toolbar -->
      <UDashboardToolbar>
        <UNavigationMenu :items="links" highlight class="flex-1" />
      </UDashboardToolbar>
    </template>

    <template #body>
      <div class="px-4 sm:px-6 lg:px-8 py-6">
        <NuxtPage />
      </div>
    </template>
  </UDashboardPanel>
</template>