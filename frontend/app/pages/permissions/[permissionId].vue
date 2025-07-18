<script setup lang="ts">
import type { Permission } from '~/types/auth.types'

// Get permission ID from route
const route = useRoute()
const permissionId = computed(() => route.params.permissionId as string)

// Stores
const permissionsStore = usePermissionsStore()
const contextStore = useContextStore()
const router = useRouter()

// State
const activeTab = ref('overview')

// Fetch permission on mount
const { data: permission, pending, error } = await useAsyncData(
  `permission-${permissionId.value}`,
  () => permissionsStore.fetchPermission(permissionId.value),
  {
    watch: [permissionId]
  }
)

// Check if user can edit
const canEdit = computed(() => {
  if (!permission.value) return false
  // Cannot edit system permissions
  if (permission.value.is_system) return false
  // In entity context, can only edit permissions created in that context
  if (!contextStore.isSystemContext && permission.value.entity_id !== contextStore.selectedOrganization?.id) {
    return false
  }
  return true
})

// Breadcrumb items
const breadcrumbItems = computed(() => {
  const items = [
    { label: "Dashboard", to: "/dashboard" },
    { label: "Permissions", to: "/permissions" }
  ]
  
  if (permission.value) {
    items.push({ 
      label: permission.value.display_name || permission.value.name, 
      to: `/permissions/${permission.value.id}` 
    })
  }
  
  return items
})

// Tab items
const tabItems = [
  { label: 'Overview', value: 'overview', icon: 'i-lucide-info' },
  { label: 'Usage', value: 'usage', icon: 'i-lucide-users' },
  { label: 'Activity', value: 'activity', icon: 'i-lucide-activity' },
]

// Methods
function handleEdit() {
  permissionsStore.openDrawer('edit', permission.value)
}

function handlePermissionUpdated() {
  // Refresh permission data
  permissionsStore.fetchPermission(permissionId.value)
}

function handlePermissionDeleted() {
  // Navigate back to permissions list
  router.push('/permissions')
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
        <UButton 
          v-if="canEdit"
          icon="i-lucide-pencil" 
          @click="handleEdit"
        >
          Edit Permission
        </UButton>
      </template>
    </UDashboardNavbar>

    <div class="flex-1 flex flex-col min-h-0">
      <!-- Loading State -->
      <div v-if="pending" class="text-center py-12">
        <UIcon name="i-lucide-loader-2" class="h-8 w-8 animate-spin text-primary" />
        <p class="mt-2 text-gray-600">Loading permission...</p>
      </div>

      <!-- Error State -->
      <UAlert 
        v-else-if="error" 
        color="error" 
        variant="subtle" 
        icon="i-lucide-alert-circle"
      >
        <template #title>Error loading permission</template>
        <template #description>{{ error.message || 'Failed to load permission details' }}</template>
      </UAlert>

      <!-- Permission Content -->
      <div v-else-if="permission" class="flex flex-col min-h-0">
        <!-- Compact Header Section -->
        <div class="bg-primary-100 dark:bg-primary-500/10 p-4">
          <div class="flex items-center justify-between gap-4">
            <!-- Left side - Permission info -->
            <div class="flex items-center gap-3 min-w-0">
              <div class="flex-shrink-0">
                <div class="p-2 bg-primary/10 rounded-md">
                  <UIcon
                    name="i-lucide-key"
                    class="h-5 w-5 text-primary"
                  />
                </div>
              </div>

              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2 flex-wrap">
                  <h1 class="text-lg font-semibold truncate">
                    {{ permission.display_name }}
                  </h1>
                  <UBadge
                    v-if="permission.is_system"
                    label="System"
                    color="blue"
                    variant="subtle"
                    size="xs"
                  />
                  <UBadge
                    v-if="!permission.is_active"
                    label="Inactive"
                    color="neutral"
                    variant="subtle"
                    size="xs"
                  />
                </div>

                <div class="flex items-center gap-2 mt-0.5 text-sm text-muted">
                  <span class="font-mono">{{ permission.name }}</span>
                  <span v-if="permission.description" class="hidden sm:inline">•</span>
                  <span v-if="permission.description" class="hidden sm:inline truncate max-w-xs">
                    {{ permission.description }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tabs -->
        <UTabs 
          v-model="activeTab" 
          :items="tabItems"
          class="flex-1 flex flex-col min-h-0"
          :ui="{
            wrapper: 'flex flex-col h-full',
            list: {
              base: 'rounded-none bg-neutral-500/10 flex-shrink-0',
              wrapper: 'flex-shrink-0'
            },
            content: 'flex-1 overflow-y-auto'
          }"
        >
          <!-- Overview Tab -->
          <template #overview>
            <div class="space-y-4 p-4">
              <!-- Basic Information -->
              <UCard>
                <template #header>
                  <h3 class="text-lg font-semibold">Basic Information</h3>
                </template>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label class="text-sm font-medium text-gray-500">Resource</label>
                    <p class="mt-1">{{ permission.resource }}</p>
                  </div>
                  <div>
                    <label class="text-sm font-medium text-gray-500">Action</label>
                    <p class="mt-1">{{ permission.action }}</p>
                  </div>
                  <div>
                    <label class="text-sm font-medium text-gray-500">Type</label>
                    <p class="mt-1">{{ permission.is_system ? 'System Permission' : 'Custom Permission' }}</p>
                  </div>
                  <div>
                    <label class="text-sm font-medium text-gray-500">Status</label>
                    <p class="mt-1">{{ permission.is_active ? 'Active' : 'Inactive' }}</p>
                  </div>
                  <div v-if="permission.entity_id">
                    <label class="text-sm font-medium text-gray-500">Entity Scope</label>
                    <p class="mt-1">{{ permission.entity_id }}</p>
                  </div>
                  <div v-if="permission.created_at">
                    <label class="text-sm font-medium text-gray-500">Created</label>
                    <p class="mt-1">{{ new Date(permission.created_at).toLocaleString() }}</p>
                  </div>
                </div>
              </UCard>

              <!-- Tags -->
              <UCard v-if="permission.tags && permission.tags.length > 0">
                <template #header>
                  <h3 class="text-lg font-semibold">Tags</h3>
                </template>
                <div class="flex flex-wrap gap-2">
                  <UBadge 
                    v-for="tag in permission.tags" 
                    :key="tag"
                    color="neutral"
                    variant="subtle"
                  >
                    {{ tag }}
                  </UBadge>
                </div>
              </UCard>

              <!-- Access Conditions -->
              <UCard v-if="permission.conditions && permission.conditions.length > 0">
                <template #header>
                  <h3 class="text-lg font-semibold">Access Conditions</h3>
                </template>
                <div class="space-y-4">
                  <p class="text-sm text-gray-600 dark:text-gray-400">
                    This permission has {{ permission.conditions.length }} condition(s) that must be met for access to be granted.
                  </p>
                  <div v-for="(condition, index) in permission.conditions" :key="index" class="border rounded-lg p-4">
                    <div class="flex items-center gap-2 mb-2">
                      <UIcon name="i-lucide-filter" class="h-4 w-4 text-primary" />
                      <span class="font-medium">Condition {{ index + 1 }}</span>
                    </div>
                    <div class="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <span class="text-gray-500">Attribute:</span>
                        <p class="font-mono">{{ condition.attribute }}</p>
                      </div>
                      <div>
                        <span class="text-gray-500">Operator:</span>
                        <p>{{ condition.operator }}</p>
                      </div>
                      <div>
                        <span class="text-gray-500">Value:</span>
                        <p class="font-mono">{{ JSON.stringify(condition.value) }}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </UCard>
            </div>
          </template>

          <!-- Usage Tab -->
          <template #usage>
            <div class="space-y-4 p-4">
              <UCard>
                <template #header>
                  <h3 class="text-lg font-semibold">Roles Using This Permission</h3>
                </template>
                <div class="text-center py-8 text-gray-500">
                  <UIcon name="i-lucide-shield" class="h-12 w-12 mb-4" />
                  <p>Role usage information coming soon</p>
                </div>
              </UCard>
            </div>
          </template>

          <!-- Activity Tab -->
          <template #activity>
            <div class="space-y-4 p-4">
              <UCard>
                <template #header>
                  <h3 class="text-lg font-semibold">Recent Activity</h3>
                </template>
                <div class="text-center py-8 text-gray-500">
                  <UIcon name="i-lucide-activity" class="h-12 w-12 mb-4" />
                  <p>Activity logging coming soon</p>
                </div>
              </UCard>
            </div>
          </template>
        </UTabs>
      </div>
    </div>

    <!-- Permission Drawer -->
    <PermissionsDrawer 
      v-model:open="permissionsStore.ui.drawerOpen" 
      :permission="permissionsStore.selectedPermission" 
      :mode="permissionsStore.ui.drawerMode" 
      @updated="handlePermissionUpdated" 
      @deleted="handlePermissionDeleted" 
    />
  </UDashboardPanel>
</template>