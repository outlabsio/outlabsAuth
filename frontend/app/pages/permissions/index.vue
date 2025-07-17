<script setup lang="ts">
import type { Permission } from '~/types/auth.types'

// Store
const permissionsStore = usePermissionsStore()
const contextStore = useContextStore()
const authStore = useAuthStore()

// Check if user can create permissions
const canCreatePermissions = computed(() => {
  // In a real app, check user permissions
  return true // For now, allow if they can see the page
})

// Type filter options
const typeOptions = [
  { label: "All Types", value: "" },
  { label: "System", value: "system" },
  { label: "Custom", value: "custom" },
]

// Active filter options
const activeOptions = [
  { label: "All", value: "" },
  { label: "Active", value: "active" },
  { label: "Inactive", value: "inactive" },
]

// Condition filter options
const conditionOptions = [
  { label: "All", value: "" },
  { label: "With Conditions", value: "with" },
  { label: "Without Conditions", value: "without" },
]

// Fetch permissions on mount
onMounted(() => {
  permissionsStore.fetchPermissions()
})

// Context-aware breadcrumb items
const breadcrumbItems = computed(() => {
  const items = [{ label: "Dashboard", to: "/dashboard" }]
  
  if (contextStore.isSystemContext) {
    items.push({ label: "Permissions", to: "/permissions" })
  } else if (contextStore.selectedOrganization) {
    items.push(
      { label: contextStore.selectedOrganization.name, to: "/dashboard" },
      { label: "Permissions", to: "/permissions" }
    )
  } else {
    items.push({ label: "Permissions", to: "/permissions" })
  }
  
  return items
})

// Methods
function handleSearch(searchValue: string | number) {
  const search = String(searchValue)
  permissionsStore.setFilters({ search })
}

function handleTypeFilter(value: string) {
  if (value === "system") {
    permissionsStore.setFilters({ is_system: true })
  } else if (value === "custom") {
    permissionsStore.setFilters({ is_system: false })
  } else {
    permissionsStore.setFilters({ is_system: null })
  }
}

function handleActiveFilter(value: string) {
  if (value === "active") {
    permissionsStore.setFilters({ is_active: true })
  } else if (value === "inactive") {
    permissionsStore.setFilters({ is_active: false })
  } else {
    permissionsStore.setFilters({ is_active: null })
  }
}

function handleConditionFilter(value: string) {
  if (value === "with") {
    permissionsStore.setFilters({ has_conditions: true })
  } else if (value === "without") {
    permissionsStore.setFilters({ has_conditions: false })
  } else {
    permissionsStore.setFilters({ has_conditions: null })
  }
}

function openCreateDrawer() {
  permissionsStore.openDrawer('create')
}

function handlePermissionCreated() {
  permissionsStore.fetchPermissions()
}

function handlePermissionUpdated() {
  permissionsStore.fetchPermissions()
}

function handlePermissionDeleted() {
  permissionsStore.fetchPermissions()
}

// Get current filter values for selects
const currentTypeFilter = computed(() => {
  if (permissionsStore.filters.is_system === true) return "system"
  if (permissionsStore.filters.is_system === false) return "custom"
  return ""
})

const currentActiveFilter = computed(() => {
  if (permissionsStore.filters.is_active === true) return "active"
  if (permissionsStore.filters.is_active === false) return "inactive"
  return ""
})

const currentConditionFilter = computed(() => {
  if (permissionsStore.filters.has_conditions === true) return "with"
  if (permissionsStore.filters.has_conditions === false) return "without"
  return ""
})
</script>

<template>
  <UDashboardPanel>
    <UDashboardNavbar>
      <template #left>
        <div class="flex items-center gap-4">
          <UDashboardSidebarCollapse />
          <UBreadcrumb :items="breadcrumbItems" />
        </div>
      </template>
      <template #right>
        <UButton 
          v-if="canCreatePermissions"
          icon="i-lucide-plus" 
          @click="openCreateDrawer"
        >
          Create Permission
        </UButton>
      </template>
    </UDashboardNavbar>

    <div class="px-4 py-6 lg:px-8">
      <!-- Context Banner -->
      <div v-if="!contextStore.isSystemContext" class="mb-6">
        <UAlert
          icon="i-lucide-info"
          color="primary"
          variant="subtle"
          :title="`Viewing permissions for ${contextStore.selectedOrganization?.name}`"
          :description="'Showing custom permissions for this entity plus inherited and system permissions'"
        />
      </div>

      <!-- Stats Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-600 dark:text-gray-400">Total Permissions</p>
              <p class="text-2xl font-bold">{{ permissionsStore.totalPermissions }}</p>
            </div>
            <UIcon name="i-lucide-shield" class="h-8 w-8 text-primary" />
          </div>
        </UCard>
        
        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-600 dark:text-gray-400">System Permissions</p>
              <p class="text-2xl font-bold">{{ permissionsStore.systemCount }}</p>
            </div>
            <UIcon name="i-lucide-lock" class="h-8 w-8 text-blue-500" />
          </div>
        </UCard>
        
        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-gray-600 dark:text-gray-400">Custom Permissions</p>
              <p class="text-2xl font-bold">{{ permissionsStore.customCount }}</p>
            </div>
            <UIcon name="i-lucide-settings" class="h-8 w-8 text-green-500" />
          </div>
        </UCard>
      </div>

      <!-- Filters -->
      <UCard class="mb-6">
        <div class="grid grid-cols-1 md:grid-cols-6 gap-4">
          <!-- Search -->
          <div class="md:col-span-2">
            <UInput
              :model-value="permissionsStore.filters.search"
              @update:model-value="handleSearch"
              placeholder="Search permissions..."
              icon="i-lucide-search"
              size="md"
            />
          </div>

          <!-- Resource Filter -->
          <USelectMenu
            :model-value="permissionsStore.filters.resource || ''"
            @update:model-value="permissionsStore.setFilters({ resource: $event || null })"
            :options="[{ label: 'All Resources', value: '' }, ...permissionsStore.uniqueResources.map(r => ({ label: r, value: r }))]"
            placeholder="All Resources"
            value-attribute="value"
            option-attribute="label"
          />

          <!-- Type Filter -->
          <USelectMenu
            :model-value="currentTypeFilter"
            @update:model-value="handleTypeFilter"
            :options="typeOptions"
            placeholder="All Types"
            value-attribute="value"
            option-attribute="label"
          />

          <!-- Active Filter -->
          <USelectMenu
            :model-value="currentActiveFilter"
            @update:model-value="handleActiveFilter"
            :options="activeOptions"
            placeholder="All"
            value-attribute="value"
            option-attribute="label"
          />

          <!-- Conditions Filter -->
          <USelectMenu
            :model-value="currentConditionFilter"
            @update:model-value="handleConditionFilter"
            :options="conditionOptions"
            placeholder="All"
            value-attribute="value"
            option-attribute="label"
          />
        </div>

        <!-- Tags Filter -->
        <div v-if="permissionsStore.allTags.length > 0" class="mt-4">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-sm text-gray-600 dark:text-gray-400">Tags:</span>
            <UBadge 
              v-for="tag in permissionsStore.allTags" 
              :key="tag"
              :color="permissionsStore.filters.tags.includes(tag) ? 'primary' : 'neutral'"
              variant="subtle"
              size="sm"
              class="cursor-pointer"
              @click="() => {
                const tags = permissionsStore.filters.tags.includes(tag) 
                  ? permissionsStore.filters.tags.filter(t => t !== tag)
                  : [...permissionsStore.filters.tags, tag]
                permissionsStore.setFilters({ tags })
              }"
            >
              {{ tag }}
            </UBadge>
            <UButton 
              v-if="permissionsStore.filters.tags.length > 0"
              @click="permissionsStore.setFilters({ tags: [] })" 
              variant="link" 
              size="xs"
              color="neutral"
            >
              Clear tags
            </UButton>
          </div>
        </div>

        <!-- Reset Button -->
        <div class="mt-4 flex justify-end">
          <UButton 
            @click="permissionsStore.resetFilters" 
            variant="outline" 
            icon="i-lucide-rotate-ccw"
            size="sm"
          >
            Reset Filters
          </UButton>
        </div>
      </UCard>

      <!-- Loading State -->
      <div v-if="permissionsStore.isLoading" class="text-center py-12">
        <UIcon name="i-lucide-loader-2" class="h-8 w-8 animate-spin text-primary" />
        <p class="mt-2 text-gray-600">Loading permissions...</p>
      </div>

      <!-- Error State -->
      <UAlert v-else-if="permissionsStore.error" color="error" variant="subtle" icon="i-lucide-alert-circle" :title="permissionsStore.error" />

      <!-- Permissions by Resource -->
      <div v-else-if="Object.keys(permissionsStore.permissionsByResource).length > 0" class="space-y-6">
        <div v-for="(permissions, resource) in permissionsStore.permissionsByResource" :key="resource">
          <h3 class="text-lg font-semibold mb-3 capitalize flex items-center gap-2">
            <UIcon name="i-lucide-folder" class="h-5 w-5 text-gray-500" />
            {{ resource }} 
            <span class="text-sm font-normal text-gray-500">({{ permissions.length }})</span>
          </h3>
          
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <NuxtLink 
              v-for="permission in permissions" 
              :key="permission.id || permission.name" 
              :to="permission.id ? `/permissions/${permission.id}` : '#'"
              class="block"
            >
              <UCard class="cursor-pointer hover:shadow-lg transition-shadow h-full">
                <div class="space-y-2">
                  <div class="flex items-start justify-between">
                    <div class="flex-1">
                      <h4 class="font-medium">{{ permission.display_name }}</h4>
                      <p class="text-sm text-gray-600 dark:text-gray-400 font-mono">{{ permission.name }}</p>
                    </div>
                    <div class="flex items-center gap-2">
                      <UBadge 
                        v-if="permission.is_system" 
                        color="blue" 
                        variant="subtle" 
                        size="xs"
                      >
                        System
                      </UBadge>
                      <UBadge 
                        v-if="!permission.is_active" 
                        color="neutral" 
                        variant="subtle" 
                        size="xs"
                      >
                        Inactive
                      </UBadge>
                      <UIcon 
                        v-if="permission.conditions.length > 0" 
                        name="i-lucide-zap" 
                        class="h-4 w-4 text-yellow-500"
                        title="Has conditions"
                      />
                    </div>
                  </div>
                  
                  <p v-if="permission.description" class="text-sm text-gray-500 line-clamp-2">
                    {{ permission.description }}
                  </p>
                  
                  <div v-if="permission.tags.length > 0" class="flex items-center gap-1 flex-wrap">
                    <UBadge 
                      v-for="tag in permission.tags" 
                      :key="tag"
                      color="neutral"
                      variant="subtle"
                      size="xs"
                    >
                      {{ tag }}
                    </UBadge>
                  </div>
                </div>
              </UCard>
            </NuxtLink>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <UCard v-else class="text-center py-12">
        <UIcon name="i-lucide-shield-off" class="h-12 w-12 text-gray-400 mb-4" />
        <h3 class="text-lg font-semibold mb-2">No permissions found</h3>
        <p class="text-gray-600 dark:text-gray-400 mb-4">
          {{ permissionsStore.filters.search || Object.values(permissionsStore.filters).some(v => v !== null && v !== '' && (!Array.isArray(v) || v.length > 0)) ? "Try adjusting your filters" : "No permissions available in this context" }}
        </p>
        <UButton 
          v-if="canCreatePermissions && !permissionsStore.filters.search" 
          icon="i-lucide-plus" 
          @click="openCreateDrawer"
        >
          Create Permission
        </UButton>
      </UCard>
    </div>

    <!-- Permission Drawer -->
    <PermissionsDrawer 
      v-model:open="permissionsStore.ui.drawerOpen" 
      :permission="permissionsStore.selectedPermission" 
      :mode="permissionsStore.ui.drawerMode" 
      @created="handlePermissionCreated" 
      @updated="handlePermissionUpdated" 
      @deleted="handlePermissionDeleted" 
    />
  </UDashboardPanel>
</template>