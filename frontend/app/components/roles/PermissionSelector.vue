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
  if (!searchQuery.value) {
    return groupedPermissions.value
  }
  
  const query = searchQuery.value.toLowerCase()
  
  return groupedPermissions.value
    .map(group => ({
      ...group,
      permissions: group.permissions.filter(permission => {
        return (
          permission.name.toLowerCase().includes(query) ||
          permission.display_name.toLowerCase().includes(query) ||
          permission.resource?.toLowerCase().includes(query) ||
          (permission.description?.toLowerCase().includes(query) ?? false)
        )
      })
    }))
    .filter(group => group.permissions.length > 0)
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


</script>

<template>
  <div class="space-y-3">
    <!-- Search and Selected Count -->
    <div class="flex items-center justify-between gap-4">
      <UInput
        v-model="searchQuery"
        placeholder="Filter permissions..."
        icon="i-lucide-filter"
        size="sm"
        class="flex-1 max-w-sm"
      />
      <span class="text-sm text-muted">
        <strong>{{ modelValue.length }}</strong> selected
      </span>
    </div>

    <!-- Permission Groups -->
    <div class="border border-default rounded-lg bg-card">
      <div v-if="permissionsStore.isLoading" class="p-8 text-center">
        <UIcon name="i-lucide-loader-2" class="h-5 w-5 animate-spin mx-auto mb-2 text-muted" />
        <p class="text-sm text-muted">Loading permissions...</p>
      </div>

      <div v-else-if="filteredGroups.length === 0" class="p-8 text-center">
        <UIcon name="i-lucide-search-x" class="h-6 w-6 mx-auto mb-2 text-muted" />
        <p class="text-sm text-muted">No permissions found</p>
      </div>

      <div v-else class="divide-y divide-default max-h-[400px] overflow-y-auto">
        <div v-for="group in filteredGroups" :key="group.resource">
          <!-- Group Header -->
          <div 
            class="flex items-center gap-2 px-3 py-2 hover:bg-muted cursor-pointer select-none"
            @click="toggleGroup(group.resource)"
          >
            <UIcon
              :name="expandedGroups.has(group.resource) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
              class="h-3 w-3 text-muted flex-shrink-0"
            />
            <UCheckbox
              :model-value="isGroupSelected(group.permissions)"
              :indeterminate="isGroupPartiallySelected(group.permissions)"
              @update:model-value="toggleGroupPermissions(group.permissions)"
              @click.stop
              class="flex-shrink-0"
            />
            <span class="text-sm font-medium capitalize flex-1">{{ group.resource }}</span>
            <span class="text-xs text-muted">
              {{ group.permissions.filter(p => modelValue.includes(p.name)).length }}/{{ group.permissions.length }}
            </span>
          </div>

          <!-- Permissions List -->
          <div v-if="expandedGroups.has(group.resource)" class="bg-muted/30 py-1">
            <label
              v-for="permission in group.permissions"
              :key="permission.name"
              class="flex items-start gap-2 px-3 py-1.5 hover:bg-muted/50 cursor-pointer"
            >
              <UCheckbox
                :model-value="modelValue.includes(permission.name)"
                @update:model-value="togglePermission(permission.name)"
                class="mt-0.5 flex-shrink-0"
              />
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <code class="text-xs px-1.5 py-0.5 rounded bg-accented font-mono">{{ permission.name }}</code>
                  <UBadge
                    v-if="permission.is_system"
                    label="System"
                    variant="subtle"
                    size="xs"
                    color="primary"
                  />
                  <UIcon
                    v-if="permission.conditions && permission.conditions.length > 0"
                    name="i-lucide-zap"
                    class="h-3 w-3 text-warning"
                    title="Has conditions"
                  />
                </div>
                <p v-if="permission.description" class="text-xs text-muted mt-0.5 leading-relaxed">
                  {{ permission.description }}
                </p>
              </div>
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="flex items-center justify-end gap-3 text-xs">
      <button
        type="button"
        class="text-muted hover:text-foreground transition-colors"
        @click="$emit('update:modelValue', permissionsStore.permissions.map(p => p.name))"
      >
        Select all
      </button>
      <span class="text-muted">·</span>
      <button
        type="button"
        class="text-muted hover:text-foreground transition-colors"
        @click="$emit('update:modelValue', [])"
      >
        Clear all
      </button>
    </div>
  </div>
</template>