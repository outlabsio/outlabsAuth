<script setup lang="ts">
import type { Permission } from '~/types/auth.types'

const props = defineProps<{
  modelValue: string[]
  entityId?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

// Stores
const permissionsStore = usePermissionsStore()

// State
const searchQuery = ref('')
const selectedResource = ref<string | null>(null)
const expandedGroups = ref<Set<string>>(new Set())

// Fetch permissions on mount
onMounted(() => {
  permissionsStore.fetchPermissions()
})

// Group permissions by resource
const groupedPermissions = computed(() => {
  const permissions = permissionsStore.permissions
  const grouped: Record<string, Permission[]> = {}
  
  permissions.forEach(permission => {
    const resource = permission.resource || 'other'
    if (!grouped[resource]) {
      grouped[resource] = []
    }
    grouped[resource].push(permission)
  })
  
  // Sort resources and permissions within each group
  const sortedGroups = Object.entries(grouped)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([resource, perms]) => ({
      resource,
      permissions: perms.sort((a, b) => {
        // System permissions first
        if (a.is_system !== b.is_system) {
          return a.is_system ? -1 : 1
        }
        // Then by action
        return a.action.localeCompare(b.action)
      })
    }))
  
  return sortedGroups
})

// Filter permissions based on search
const filteredGroups = computed(() => {
  if (!searchQuery.value && !selectedResource.value) {
    return groupedPermissions.value
  }
  
  return groupedPermissions.value
    .filter(group => {
      if (selectedResource.value && group.resource !== selectedResource.value) {
        return false
      }
      return true
    })
    .map(group => ({
      ...group,
      permissions: group.permissions.filter(permission => {
        if (!searchQuery.value) return true
        const query = searchQuery.value.toLowerCase()
        return (
          permission.name.toLowerCase().includes(query) ||
          permission.display_name.toLowerCase().includes(query) ||
          (permission.description?.toLowerCase().includes(query) ?? false)
        )
      })
    }))
    .filter(group => group.permissions.length > 0)
})

// Resource filter options
const resourceOptions = computed(() => {
  const resources = new Set(permissionsStore.permissions.map(p => p.resource || 'other'))
  return [
    { value: null, label: 'All Resources' },
    ...Array.from(resources).sort().map(resource => ({
      value: resource,
      label: resource.charAt(0).toUpperCase() + resource.slice(1)
    }))
  ]
})

// Toggle group expansion
function toggleGroup(resource: string) {
  if (expandedGroups.value.has(resource)) {
    expandedGroups.value.delete(resource)
  } else {
    expandedGroups.value.add(resource)
  }
}

// Check if all permissions in a group are selected
function isGroupSelected(permissions: Permission[]): boolean {
  return permissions.every(p => props.modelValue.includes(p.name))
}

// Check if some permissions in a group are selected
function isGroupPartiallySelected(permissions: Permission[]): boolean {
  const selected = permissions.filter(p => props.modelValue.includes(p.name))
  return selected.length > 0 && selected.length < permissions.length
}

// Toggle all permissions in a group
function toggleGroupPermissions(permissions: Permission[]) {
  const allSelected = isGroupSelected(permissions)
  const permissionNames = permissions.map(p => p.name)
  
  if (allSelected) {
    // Remove all permissions from this group
    emit('update:modelValue', props.modelValue.filter(p => !permissionNames.includes(p)))
  } else {
    // Add all permissions from this group
    const newPermissions = new Set([...props.modelValue, ...permissionNames])
    emit('update:modelValue', Array.from(newPermissions))
  }
}

// Toggle individual permission
function togglePermission(permissionName: string) {
  if (props.modelValue.includes(permissionName)) {
    emit('update:modelValue', props.modelValue.filter(p => p !== permissionName))
  } else {
    emit('update:modelValue', [...props.modelValue, permissionName])
  }
}

// Expand all groups by default
onMounted(() => {
  groupedPermissions.value.forEach(group => {
    expandedGroups.value.add(group.resource)
  })
})
</script>

<template>
  <div class="space-y-4">
    <!-- Search and Filter -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <UInput
        v-model="searchQuery"
        placeholder="Search permissions..."
        icon="i-lucide-search"
        size="sm"
      />
      <USelectMenu
        v-model="selectedResource"
        :options="resourceOptions"
        placeholder="Filter by resource"
        value-attribute="value"
        option-attribute="label"
        size="sm"
      />
    </div>

    <!-- Selected Count -->
    <div class="text-sm text-muted-foreground">
      {{ modelValue.length }} permission{{ modelValue.length === 1 ? '' : 's' }} selected
    </div>

    <!-- Permission Groups -->
    <div class="border rounded-lg bg-gray-50 dark:bg-gray-900/50">
      <div v-if="permissionsStore.isLoading" class="p-8 text-center">
        <UIcon name="i-lucide-loader-2" class="h-6 w-6 animate-spin mx-auto mb-2" />
        <p class="text-sm text-muted-foreground">Loading permissions...</p>
      </div>

      <div v-else-if="filteredGroups.length === 0" class="p-8 text-center">
        <UIcon name="i-lucide-search-x" class="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
        <p class="text-sm text-muted-foreground">No permissions found</p>
      </div>

      <div v-else class="divide-y max-h-96 overflow-y-auto">
        <div v-for="group in filteredGroups" :key="group.resource" class="p-3">
          <!-- Group Header -->
          <div class="flex items-center gap-2 mb-2">
            <UButton
              variant="ghost"
              size="xs"
              square
              @click="toggleGroup(group.resource)"
            >
              <UIcon
                :name="expandedGroups.has(group.resource) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                class="h-3 w-3"
              />
            </UButton>
            <UCheckbox
              :model-value="isGroupSelected(group.permissions)"
              :indeterminate="isGroupPartiallySelected(group.permissions)"
              @update:model-value="toggleGroupPermissions(group.permissions)"
            />
            <span class="font-medium capitalize">{{ group.resource }}</span>
            <UBadge
              :label="`${group.permissions.filter(p => modelValue.includes(p.name)).length}/${group.permissions.length}`"
              variant="subtle"
              size="xs"
            />
          </div>

          <!-- Permissions List -->
          <div v-if="expandedGroups.has(group.resource)" class="ml-7 space-y-1">
            <div
              v-for="permission in group.permissions"
              :key="permission.name"
              class="flex items-start gap-2 py-1"
            >
              <UCheckbox
                :model-value="modelValue.includes(permission.name)"
                @update:model-value="togglePermission(permission.name)"
                class="mt-0.5"
              />
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-mono text-sm">{{ permission.name }}</span>
                  <UBadge
                    v-if="permission.is_system"
                    label="System"
                    variant="subtle"
                    size="xs"
                  />
                  <UIcon
                    v-if="permission.conditions && permission.conditions.length > 0"
                    name="i-lucide-zap"
                    class="h-3 w-3 text-yellow-500"
                    title="Has conditions"
                  />
                </div>
                <p v-if="permission.description" class="text-xs text-muted-foreground mt-0.5">
                  {{ permission.description }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="flex gap-2 text-sm">
      <UButton
        variant="link"
        size="xs"
        @click="$emit('update:modelValue', permissionsStore.permissions.map(p => p.name))"
      >
        Select All
      </UButton>
      <span class="text-muted-foreground">•</span>
      <UButton
        variant="link"
        size="xs"
        @click="$emit('update:modelValue', [])"
      >
        Clear All
      </UButton>
    </div>
  </div>
</template>