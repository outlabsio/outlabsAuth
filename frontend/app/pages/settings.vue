<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'

const route = useRoute()

const links = [[{
  label: 'Overview',
  icon: 'i-lucide-layout-dashboard',
  to: '/settings',
  exact: true
}, {
  label: 'Entity Types',
  icon: 'i-lucide-folder-tree',
  to: '/settings/entity-types'
}, {
  label: 'System Users',
  icon: 'i-lucide-users-2',
  to: '/settings/users'
}, {
  label: 'Platform Settings',
  icon: 'i-lucide-settings-2',
  to: '/settings/settings'
}]] satisfies NavigationMenuItem[][]

// Breadcrumb items
const breadcrumbItems = computed(() => {
  const items: any[] = [
    { label: 'Home', to: '/' },
    { label: 'Settings', to: '/settings' }
  ]
  
  // Add current page to breadcrumbs if not on overview
  if (route.path === '/settings/entity-types') {
    items.push({ label: 'Entity Types' })
  } else if (route.path === '/settings/users') {
    items.push({ label: 'System Users' })
  } else if (route.path === '/settings/settings') {
    items.push({ label: 'Platform Settings' })
  }
  
  return items
})

// Page title based on current route
const pageTitle = computed(() => {
  if (route.path === '/settings/entity-types') return 'Entity Types'
  if (route.path === '/settings/users') return 'System Users'
  if (route.path === '/settings/settings') return 'Platform Settings'
  return 'Settings Overview'
})

// Page description based on current route
const pageDescription = computed(() => {
  if (route.path === '/settings/entity-types') return 'Manage entity type definitions and their hierarchy rules'
  if (route.path === '/settings/users') return 'Manage all users across the system'
  if (route.path === '/settings/settings') return 'Configure system options'
  return 'System administration and configuration'
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