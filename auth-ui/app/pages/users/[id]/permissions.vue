<script setup lang="ts">
/**
 * Permissions Tab
 * Display user's effective permissions from roles + direct assignments
 */

import type { User } from '~/types/auth'

const props = defineProps<{
  user: User
}>()

const userStore = useUserStore()

// User's effective permissions
const userPermissions = computed(() => userStore.userPermissions)

// Group permissions by source (role vs direct)
const permissionsFromRoles = computed(() =>
  userPermissions.value.filter(p => p.source === 'role')
)

const directPermissions = computed(() =>
  userPermissions.value.filter(p => p.source === 'direct')
)

// Group permissions by resource
const permissionsByResource = computed(() => {
  const grouped: Record<string, typeof userPermissions.value> = {}

  userPermissions.value.forEach(p => {
    const resource = p.permission.resource
    if (!grouped[resource]) {
      grouped[resource] = []
    }
    grouped[resource].push(p)
  })

  return grouped
})

// Search filter
const searchQuery = ref('')

// Filtered permissions
const filteredPermissions = computed(() => {
  if (!searchQuery.value) return userPermissions.value

  const query = searchQuery.value.toLowerCase()
  return userPermissions.value.filter(p =>
    p.permission.name.toLowerCase().includes(query) ||
    p.permission.display_name.toLowerCase().includes(query) ||
    p.permission.resource.toLowerCase().includes(query) ||
    p.permission.action.toLowerCase().includes(query)
  )
})

// View mode: 'list' or 'grouped'
const viewMode = ref<'list' | 'grouped'>('list')

// Fetch permissions on mount
onMounted(() => {
  userStore.fetchUserPermissions(props.user.id)
})
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center justify-between">
        <div>
          <h3 class="text-lg font-semibold text-foreground">Effective Permissions</h3>
          <p class="text-sm text-muted">All permissions from assigned roles + direct permissions</p>
        </div>
        <UBadge color="primary" variant="subtle">
          {{ userPermissions.length }} {{ userPermissions.length === 1 ? 'permission' : 'permissions' }}
        </UBadge>
      </div>
    </template>

    <!-- Controls -->
    <div class="flex items-center gap-3 mb-6">
      <!-- Search -->
      <UInput
        v-model="searchQuery"
        icon="i-lucide-search"
        placeholder="Search permissions..."
        class="flex-1"
      />

      <!-- View Mode Toggle -->
      <div class="flex gap-1 p-1 bg-muted rounded-lg">
        <UButton
          :variant="viewMode === 'list' ? 'solid' : 'ghost'"
          :color="viewMode === 'list' ? 'primary' : 'neutral'"
          icon="i-lucide-list"
          size="sm"
          @click="viewMode = 'list'"
        >
          List
        </UButton>
        <UButton
          :variant="viewMode === 'grouped' ? 'solid' : 'ghost'"
          :color="viewMode === 'grouped' ? 'primary' : 'neutral'"
          icon="i-lucide-layers"
          size="sm"
          @click="viewMode = 'grouped'"
        >
          Grouped
        </UButton>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="userStore.isLoadingPermissions" class="text-center py-12">
      <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary mb-2" />
      <p class="text-sm text-muted">Loading permissions...</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="userPermissions.length === 0" class="text-center py-12">
      <UIcon name="i-lucide-lock-open" class="w-12 h-12 text-muted mb-4" />
      <p class="text-sm font-medium text-foreground mb-1">No permissions</p>
      <p class="text-xs text-muted">This user has no permissions assigned</p>
    </div>

    <!-- List View -->
    <div v-else-if="viewMode === 'list'" class="space-y-2">
      <div v-if="filteredPermissions.length === 0" class="text-center py-8">
        <p class="text-sm text-muted">No permissions match your search</p>
      </div>

      <UCard
        v-else
        v-for="permSource in filteredPermissions"
        :key="permSource.permission.id"
        class="hover:bg-muted/50 transition-colors"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <p class="font-medium text-foreground">
                {{ permSource.permission.display_name || permSource.permission.name }}
              </p>
              <UBadge
                :color="permSource.source === 'role' ? 'blue' : 'green'"
                variant="subtle"
              >
                {{ permSource.source === 'role' ? 'From Role' : 'Direct' }}
              </UBadge>
              <UBadge v-if="permSource.permission.is_system" color="neutral" variant="subtle">
                System
              </UBadge>
            </div>

            <p v-if="permSource.permission.description" class="text-sm text-muted mb-2">
              {{ permSource.permission.description }}
            </p>

            <div class="flex items-center gap-3 text-xs">
              <code class="px-2 py-1 bg-muted rounded">{{ permSource.permission.resource }}</code>
              <code class="px-2 py-1 bg-muted rounded">{{ permSource.permission.action }}</code>
            </div>
          </div>

          <!-- Status Indicator -->
          <div class="ml-4">
            <UBadge :color="permSource.permission.is_active ? 'success' : 'neutral'" variant="subtle">
              {{ permSource.permission.is_active ? 'Active' : 'Inactive' }}
            </UBadge>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Grouped View -->
    <div v-else class="space-y-6">
      <div v-for="(perms, resource) in permissionsByResource" :key="resource">
        <div class="flex items-center gap-2 mb-3">
          <UIcon name="i-lucide-folder" class="w-4 h-4 text-primary" />
          <h4 class="text-sm font-semibold text-foreground">{{ resource }}</h4>
          <UBadge color="primary" variant="subtle" size="xs">
            {{ perms.length }}
          </UBadge>
        </div>

        <div class="space-y-2 pl-6">
          <UCard
            v-for="permSource in perms"
            :key="permSource.permission.id"
            class="hover:bg-muted/50 transition-colors"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <code class="px-2 py-1 bg-muted rounded text-xs">
                  {{ permSource.permission.action }}
                </code>
                <p class="text-sm text-foreground">
                  {{ permSource.permission.display_name || permSource.permission.name }}
                </p>
              </div>

              <div class="flex items-center gap-2">
                <UBadge
                  :color="permSource.source === 'role' ? 'blue' : 'green'"
                  variant="subtle"
                  size="xs"
                >
                  {{ permSource.source === 'role' ? 'Role' : 'Direct' }}
                </UBadge>
                <UBadge
                  :color="permSource.permission.is_active ? 'success' : 'neutral'"
                  variant="subtle"
                  size="xs"
                >
                  {{ permSource.permission.is_active ? 'Active' : 'Inactive' }}
                </UBadge>
              </div>
            </div>
          </UCard>
        </div>
      </div>
    </div>

    <!-- Summary -->
    <div class="mt-6 pt-6 border-t border-border">
      <div class="grid grid-cols-2 gap-4">
        <div class="text-center p-4 bg-blue-500/10 rounded-lg">
          <p class="text-2xl font-bold text-blue-600">{{ permissionsFromRoles.length }}</p>
          <p class="text-xs text-muted">From Roles</p>
        </div>
        <div class="text-center p-4 bg-green-500/10 rounded-lg">
          <p class="text-2xl font-bold text-green-600">{{ directPermissions.length }}</p>
          <p class="text-xs text-muted">Direct Permissions</p>
        </div>
      </div>
    </div>
  </UCard>
</template>
