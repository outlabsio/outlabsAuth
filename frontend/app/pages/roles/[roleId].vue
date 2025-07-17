<template>
  <div class="w-full">
    <!-- Breadcrumb Navigation -->
    <div class="m-4">
      <UBreadcrumb :items="breadcrumbItems" />
    </div>

    <!-- Loading State -->
    <div v-if="pending" class="flex justify-center py-12">
      <div class="text-center space-y-3">
        <UIcon name="i-lucide-loader" class="h-8 w-8 animate-spin mx-auto text-primary" />
        <p class="text-muted-foreground">Loading role details...</p>
      </div>
    </div>

    <!-- Error State -->
    <UAlert v-else-if="error" color="error" variant="subtle" icon="i-lucide-alert-circle" :title="error.statusMessage || 'Failed to load role'" class="mb-6" />

    <!-- Role Details -->
    <div v-else-if="role" class="space-y-0">
      <!-- Compact Header Section -->
      <div class="bg-primary-100 dark:bg-primary-500/10 p-4">
        <div class="flex items-center justify-between gap-4">
          <!-- Left side - Role info -->
          <div class="flex items-center gap-3 min-w-0">
            <div class="flex-shrink-0">
              <div class="p-2 bg-primary/10 rounded-md">
                <UIcon
                  name="i-lucide-shield"
                  class="h-5 w-5 text-primary"
                />
              </div>
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <h1 class="text-lg font-semibold truncate">
                  {{ role.display_name || role.name }}
                </h1>
                <UBadge
                  v-if="role.is_system_role"
                  label="System"
                  color="neutral"
                  variant="subtle"
                  size="xs"
                />
                <UBadge
                  v-if="role.is_global"
                  label="Global"
                  color="primary"
                  variant="subtle"
                  size="xs"
                />
              </div>

              <div class="flex items-center gap-2 mt-0.5 text-sm text-muted">
                <span>{{ role.name }}</span>
                <span v-if="role.entity_name">•</span>
                <span v-if="role.entity_name">{{ role.entity_name }}</span>
                <span v-if="role.description" class="hidden sm:inline">•</span>
                <span v-if="role.description" class="hidden sm:inline truncate max-w-xs">
                  {{ role.description }}
                </span>
              </div>
            </div>
          </div>

          <!-- Right side - Actions -->
          <div class="flex items-center gap-2 flex-shrink-0">
            <UButton
              v-if="!role.is_system_role"
              icon="i-lucide-pencil"
              variant="subtle"
              size="sm"
              class="hidden sm:flex"
              @click="openEditDrawer"
            >
              Modify
            </UButton>
            <UButton
              v-if="!role.is_system_role"
              icon="i-lucide-pencil"
              variant="subtle"
              size="sm"
              class="sm:hidden"
              square
              @click="openEditDrawer"
            />
          </div>
        </div>
      </div>

      <!-- Tabs Section -->
      <UTabs 
        v-model="activeTab" 
        :items="tabItems" 
        class="w-full"
        :ui="{
          list: 'rounded-none bg-neutral-500/10'
        }"
      >
        <!-- Overview Tab -->
        <template #overview>
          <div class="space-y-4 p-4">
            <!-- Role Information -->
            <UCard>
              <template #header>
                <h3 class="text-lg font-semibold">Role Information</h3>
              </template>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">System Name</h4>
                  <p class="mt-1 font-mono text-sm bg-elevated px-2 py-1 rounded">{{ role.name }}</p>
                </div>

                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">Display Name</h4>
                  <p class="mt-1">{{ role.display_name }}</p>
                </div>

                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">Type</h4>
                  <p class="mt-1">{{ role.is_global ? 'Global Role' : 'Entity Role' }}</p>
                </div>

                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">System Role</h4>
                  <UBadge :label="role.is_system_role ? 'Yes' : 'No'" :color="role.is_system_role ? 'neutral' : 'success'" variant="subtle" />
                </div>

                <div v-if="role.entity_name">
                  <h4 class="text-sm font-medium text-muted-foreground">Owner Entity</h4>
                  <p class="mt-1">{{ role.entity_name }}</p>
                </div>

                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">Created</h4>
                  <p class="mt-1">{{ formatDate(role.created_at) }}</p>
                </div>

                <div v-if="role.updated_at">
                  <h4 class="text-sm font-medium text-muted-foreground">Last Updated</h4>
                  <p class="mt-1">{{ formatDate(role.updated_at) }}</p>
                </div>
              </div>

              <div v-if="role.description" class="mt-6">
                <h4 class="text-sm font-medium text-muted-foreground mb-2">Description</h4>
                <p class="text-sm">{{ role.description }}</p>
              </div>
            </UCard>

            <!-- Assignable At Types -->
            <UCard v-if="role.assignable_at_types && role.assignable_at_types.length > 0">
              <template #header>
                <h3 class="text-lg font-semibold">Can Be Assigned At</h3>
              </template>

              <div class="flex flex-wrap gap-2">
                <UBadge 
                  v-for="entityType in role.assignable_at_types" 
                  :key="entityType"
                  :label="entityType.charAt(0).toUpperCase() + entityType.slice(1).replace(/_/g, ' ')"
                  color="primary"
                  variant="subtle"
                />
              </div>
            </UCard>
          </div>
        </template>

        <!-- Permissions Tab -->
        <template #permissions>
          <div class="space-y-4 p-4">
            <!-- Permissions List -->
            <div v-if="role.permissions && role.permissions.length > 0" class="space-y-3">
              <UCard v-for="(permission, index) in groupedPermissions" :key="index">
                <template #header>
                  <div class="flex items-center gap-2">
                    <UIcon name="i-lucide-folder" class="h-4 w-4" />
                    <h4 class="font-medium capitalize">{{ permission.resource }}</h4>
                    <UBadge :label="`${permission.permissions.length} permissions`" variant="subtle" size="xs" />
                  </div>
                </template>

                <div class="space-y-2">
                  <div v-for="perm in permission.permissions" :key="perm" class="flex items-center gap-2 py-1">
                    <UIcon name="i-lucide-check" class="h-4 w-4 text-success" />
                    <span class="font-mono text-sm">{{ perm }}</span>
                    <span class="text-sm text-muted-foreground">- {{ getPermissionDescription(perm) }}</span>
                  </div>
                </div>
              </UCard>
            </div>

            <!-- Empty State -->
            <div v-else class="text-center py-12">
              <UIcon name="i-lucide-key" class="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <h3 class="font-medium mb-1">No permissions</h3>
              <p class="text-muted-foreground">This role doesn't have any permissions assigned.</p>
            </div>
          </div>
        </template>

        <!-- Usage Tab -->
        <template #usage>
          <div class="space-y-4 p-4">
            <h3 class="text-lg font-semibold">Usage Statistics</h3>

            <div v-if="roleUsage" class="grid grid-cols-1 md:grid-cols-3 gap-6">
              <UCard>
                <div class="text-center">
                  <div class="text-2xl font-bold text-primary">{{ roleUsage.total_users || 0 }}</div>
                  <div class="text-sm text-muted-foreground">Total Users</div>
                </div>
              </UCard>

              <UCard>
                <div class="text-center">
                  <div class="text-2xl font-bold text-success">{{ roleUsage.active_users || 0 }}</div>
                  <div class="text-sm text-muted-foreground">Active Users</div>
                </div>
              </UCard>

              <UCard>
                <div class="text-center">
                  <div class="text-2xl font-bold text-info">{{ roleUsage.entities_count || 0 }}</div>
                  <div class="text-sm text-muted-foreground">Entities Using</div>
                </div>
              </UCard>
            </div>

            <div v-else class="text-center py-12">
              <UIcon name="i-lucide-bar-chart" class="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <h3 class="font-medium mb-1">Loading usage data</h3>
              <p class="text-muted-foreground">Fetching role usage statistics...</p>
            </div>
          </div>
        </template>

        <!-- Activity Tab -->
        <template #activity>
          <div class="space-y-4 p-4">
            <h3 class="text-lg font-semibold">Activity Log</h3>

            <div class="text-center py-12">
              <UIcon name="i-lucide-activity" class="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <h3 class="font-medium mb-1">Activity tracking</h3>
              <p class="text-muted-foreground">Activity log functionality coming soon.</p>
            </div>
          </div>
        </template>
      </UTabs>
    </div>

    <!-- Drawers -->
    <RolesDrawer
      v-model:open="drawerOpen"
      :role="drawerRole"
      :mode="drawerMode"
      @updated="handleRoleUpdated"
      @deleted="handleRoleDeleted"
    />
  </div>
</template>

<script setup lang="ts">
import type { Role } from "~/types/auth.types"

// Route params
const route = useRoute()
const router = useRouter()
const roleId = computed(() => route.params.roleId as string)

// Store
const authStore = useAuthStore()
const rolesStore = useRolesStore()

// State
const activeTab = ref('overview')
const drawerOpen = ref(false)
const drawerMode = ref<"view" | "create" | "edit">("view")
const drawerRole = ref<Role | null>(null)
const roleUsage = ref<any>(null)

// Fetch role data
const {
  data: role,
  pending,
  error,
  refresh,
} = await useAsyncData(
  `role-${roleId.value}`,
  async () => {
    const response = await rolesStore.fetchRole(roleId.value)
    return response
  },
  {
    key: `role-${roleId.value}`,
    lazy: false,
  }
)

// Fetch role usage statistics
const fetchRoleUsage = async () => {
  try {
    const usage = await rolesStore.fetchRoleUsage(roleId.value)
    roleUsage.value = usage
  } catch (error) {
    console.error('Failed to fetch role usage:', error)
  }
}

// Watch for role changes and fetch usage
watchEffect(() => {
  if (role.value) {
    fetchRoleUsage()
  }
})

// Watch for route changes and refresh data
watch(roleId, async (newId, oldId) => {
  if (newId !== oldId) {
    await refresh()
    await fetchRoleUsage()
  }
})

// Build breadcrumb items
const breadcrumbItems = computed(() => {
  const items = [
    { label: "Dashboard", to: "/dashboard" },
    { label: "Roles", to: "/roles" }
  ]

  if (role.value) {
    items.push({
      label: role.value.display_name || role.value.name,
      to: `/roles/${role.value.id}`,
    })
  }

  return items
})

// Group permissions by resource
const groupedPermissions = computed(() => {
  if (!role.value?.permissions) return []
  
  const grouped: Record<string, string[]> = {}
  
  role.value.permissions.forEach(permission => {
    const [resource] = permission.split(':')
    if (!grouped[resource]) {
      grouped[resource] = []
    }
    grouped[resource].push(permission)
  })
  
  return Object.entries(grouped).map(([resource, permissions]) => ({
    resource,
    permissions: permissions.sort()
  }))
})

// Tab configuration
const tabItems = computed(() => [
  {
    slot: "overview",
    label: "Overview",
    icon: "i-lucide-info",
    value: "overview",
  },
  {
    slot: "permissions",
    label: `Permissions (${role.value?.permissions?.length || 0})`,
    icon: "i-lucide-key",
    value: "permissions",
  },
  {
    slot: "usage",
    label: "Usage",
    icon: "i-lucide-bar-chart",
    value: "usage",
  },
  {
    slot: "activity",
    label: "Activity",
    icon: "i-lucide-activity",
    value: "activity",
  },
])

// Methods
function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function getPermissionDescription(permission: string) {
  // Parse permission to get description
  const [resource, action] = permission.split(':')
  const actionParts = action.split('_')
  
  if (actionParts.length > 1) {
    const verb = actionParts[0]
    const scope = actionParts.slice(1).join(' ')
    return `Can ${verb} ${resource} at ${scope} level`
  }
  
  return `Can ${action} ${resource}`
}

function openEditDrawer() {
  drawerRole.value = role.value
  drawerMode.value = "edit"
  drawerOpen.value = true
}

function handleRoleUpdated(updatedRole: Role) {
  // Refresh current role
  refresh()
}

function handleRoleDeleted() {
  // Navigate back to roles list
  router.push("/roles")
}

// SEO
useHead({
  title: computed(() => (role.value ? `${role.value.display_name || role.value.name} - Roles` : "Role Details")),
  meta: [
    {
      name: "description",
      content: computed(() => role.value?.description || `Details for ${role.value?.display_name || role.value?.name}`),
    },
  ],
})
</script>