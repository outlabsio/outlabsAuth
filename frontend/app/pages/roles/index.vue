<script setup lang="ts">
import type { Role } from '~/types/auth.types'

// Store
const rolesStore = useRolesStore()
const contextStore = useContextStore()

// Role type options
const roleTypeOptions = [
  { label: "All Types", value: "" },
  { label: "Global Roles", value: "global" },
  { label: "Entity Roles", value: "entity" },
]

// System role options
const systemRoleOptions = [
  { label: "All Roles", value: "" },
  { label: "System Roles", value: "true" },
  { label: "Custom Roles", value: "false" },
]

// Assignable type options
const assignableTypeOptions = [
  { label: "All Levels", value: "" },
  { label: "Platform", value: "platform" },
  { label: "Organization", value: "organization" },
  { label: "Division", value: "division" },
  { label: "Branch", value: "branch" },
  { label: "Team", value: "team" },
  { label: "Access Group", value: "access_group" },
]

// Fetch roles on mount
onMounted(() => {
  console.log('[RolesPage] Mounted - current context:', contextStore.selectedOrganization?.name)
  rolesStore.fetchRoles()
})

// Watch for context changes
watch(() => contextStore.selectedOrganization, (newOrg, oldOrg) => {
  console.log('[RolesPage] Context changed from', oldOrg?.name, 'to', newOrg?.name)
  if (newOrg?.id !== oldOrg?.id) {
    rolesStore.fetchRoles()
  }
})

// Context-aware breadcrumb items
const breadcrumbItems = computed(() => {
  const items = [{ label: "Dashboard", to: "/dashboard" }]
  items.push({ label: "Roles", to: "/roles" })
  return items
})

// Methods
function handleSearch(searchValue: string | number) {
  const search = String(searchValue)
  rolesStore.setFilters({ search })
}

function handleTypeFilter(value: string) {
  if (value === "global") {
    rolesStore.setFilters({ is_global: true })
  } else if (value === "entity") {
    rolesStore.setFilters({ is_global: false })
  } else {
    rolesStore.setFilters({ is_global: null })
  }
}

function handleSystemFilter(value: string) {
  if (value === "true") {
    rolesStore.setFilters({ is_system_role: true })
  } else if (value === "false") {
    rolesStore.setFilters({ is_system_role: false })
  } else {
    rolesStore.setFilters({ is_system_role: null })
  }
}

function openCreateDrawer() {
  rolesStore.openDrawer('create')
}

function handleRoleCreated() {
  rolesStore.fetchRoles()
}

function handleRoleUpdated() {
  rolesStore.fetchRoles()
}

function handleRoleDeleted() {
  rolesStore.fetchRoles()
}
</script>

<template>
  <UDashboardPanel class="min-h-0 flex flex-col">
    <UDashboardNavbar class="flex-shrink-0">
      <template #left>
        <div class="flex items-center gap-4">
          <UDashboardSidebarCollapse />
          <UBreadcrumb :items="breadcrumbItems" />
        </div>
      </template>
      <template #right>
        <UButton icon="i-lucide-plus" @click="openCreateDrawer">
          Create Role
        </UButton>
      </template>
    </UDashboardNavbar>

    <div class="flex-1 overflow-y-auto">
      <div class="px-4 py-6 lg:px-8">
      <!-- Filters -->
      <UCard class="mb-6">
        <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
          <!-- Search -->
          <UInput
            :model-value="rolesStore.filters.search"
            @update:model-value="handleSearch"
            placeholder="Search roles..."
            icon="i-lucide-search"
            size="md"
          />

          <!-- Role Type Filter -->
          <USelectMenu
            :model-value="rolesStore.filters.is_global === true ? 'global' : rolesStore.filters.is_global === false ? 'entity' : ''"
            @update:model-value="handleTypeFilter"
            :options="roleTypeOptions"
            placeholder="All Types"
            value-attribute="value"
            option-attribute="label"
          />

          <!-- System Role Filter -->
          <USelectMenu
            :model-value="rolesStore.filters.is_system_role === true ? 'true' : rolesStore.filters.is_system_role === false ? 'false' : ''"
            @update:model-value="handleSystemFilter"
            :options="systemRoleOptions"
            placeholder="All Roles"
            value-attribute="value"
            option-attribute="label"
          />

          <!-- Assignable Type Filter -->
          <USelectMenu
            :model-value="rolesStore.filters.assignable_at_type || ''"
            @update:model-value="rolesStore.setFilters({ assignable_at_type: $event || null })"
            :options="assignableTypeOptions"
            placeholder="All Levels"
            value-attribute="value"
            option-attribute="label"
          />

          <!-- Reset Button -->
          <UButton 
            @click="rolesStore.resetFilters" 
            variant="outline" 
            icon="i-lucide-rotate-ccw"
          >
            Reset
          </UButton>
        </div>
      </UCard>

      <!-- Loading State -->
      <div v-if="rolesStore.isLoading" class="text-center py-12">
        <UIcon name="i-lucide-loader-2" class="h-8 w-8 animate-spin text-primary" />
        <p class="mt-2 text-gray-600">Loading roles...</p>
      </div>

      <!-- Error State -->
      <UAlert v-else-if="rolesStore.error" color="error" variant="subtle" icon="i-lucide-alert-circle" :title="rolesStore.error" />

      <!-- Roles Grid -->
      <div v-else-if="rolesStore.roles.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <NuxtLink v-for="role in rolesStore.roles" :key="role.id" :to="`/roles/${role.id}`" class="block">
          <UCard class="cursor-pointer hover:shadow-lg transition-shadow h-full">
            <div class="space-y-3">
              <div class="flex items-start justify-between">
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <UIcon name="i-lucide-shield" class="h-4 w-4 text-primary" />
                    <h3 class="font-semibold">
                      {{ role.display_name || role.name }}
                    </h3>
                  </div>
                  <div class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <span>{{ role.name }}</span>
                    <span v-if="role.is_system_role">•</span>
                    <UBadge v-if="role.is_system_role" color="neutral" variant="subtle" size="xs">
                      System
                    </UBadge>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  <UBadge v-if="role.is_global" color="primary" variant="subtle" size="xs">
                    Global
                  </UBadge>
                </div>
              </div>
              
              <p v-if="role.description" class="text-sm text-gray-500 line-clamp-2">
                {{ role.description }}
              </p>
              
              <div class="flex items-center justify-between text-sm">
                <div class="flex items-center gap-1 text-gray-600 dark:text-gray-400">
                  <UIcon name="i-lucide-key" class="h-3 w-3" />
                  <span>{{ role.permissions.length }} permissions</span>
                </div>
                <div v-if="role.entity_name" class="text-gray-600 dark:text-gray-400">
                  {{ role.entity_name }}
                </div>
              </div>
            </div>
          </UCard>
        </NuxtLink>
      </div>

      <!-- Empty State -->
      <UCard v-else class="text-center py-12">
        <UIcon name="i-lucide-shield" class="h-12 w-12 text-gray-400 mb-4" />
        <h3 class="text-lg font-semibold mb-2">No roles found</h3>
        <p class="text-gray-600 dark:text-gray-400 mb-4">
          {{ rolesStore.filters.search || rolesStore.filters.is_global !== null || rolesStore.filters.is_system_role !== null ? "Try adjusting your filters" : "Get started by creating your first role" }}
        </p>
        <UButton v-if="!rolesStore.filters.search && rolesStore.filters.is_global === null && rolesStore.filters.is_system_role === null" icon="i-lucide-plus" @click="openCreateDrawer">
          Create Role
        </UButton>
      </UCard>

      <!-- Pagination -->
      <div v-if="rolesStore.pagination.total > rolesStore.pagination.pageSize" class="mt-6 flex justify-center">
        <UPagination 
          :page="rolesStore.pagination.page" 
          :total="rolesStore.pagination.total" 
          :items-per-page="rolesStore.pagination.pageSize" 
          @update:page="rolesStore.setPage" 
        />
      </div>
      </div>
    </div>

    <!-- Role Drawer -->
    <RolesDrawer v-model:open="rolesStore.ui.drawerOpen" :role="rolesStore.selectedRole" :mode="rolesStore.ui.drawerMode" @created="handleRoleCreated" @updated="handleRoleUpdated" @deleted="handleRoleDeleted" />
  </UDashboardPanel>
</template>