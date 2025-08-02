<script setup lang="ts">
import type { Permission } from '~/types/auth.types'

interface EntityTypeConfig {
  type: string
  permissions: string[]
  isCustomized: boolean
}

const props = defineProps<{
  assignableTypes: string[]
  defaultPermissions: string[]
  entityTypePermissions: Record<string, string[]>
  entityId?: string | null
}>()

const emit = defineEmits<{
  'update:entityTypePermissions': [value: Record<string, string[]>]
}>()

// Stores
const permissionsStore = usePermissionsStore()

// State
const expandedTypes = ref<Set<string>>(new Set())
const selectedTemplates = ref<Record<string, string>>({})

// Fetch permissions on mount
onMounted(() => {
  permissionsStore.fetchPermissions()
})

// Transform props into reactive entity configs
const entityConfigs = computed<EntityTypeConfig[]>(() => {
  return props.assignableTypes.map(type => ({
    type,
    permissions: props.entityTypePermissions[type] || [],
    isCustomized: !!props.entityTypePermissions[type]
  }))
})

// Permission templates
const permissionTemplates = {
  full_control: {
    label: 'Full Control',
    icon: 'i-lucide-shield',
    description: 'Complete access to all resources',
    permissions: (resource: string) => [
      `${resource}:create`,
      `${resource}:read`,
      `${resource}:update`,
      `${resource}:delete`,
      `${resource}:create_tree`,
      `${resource}:read_tree`,
      `${resource}:update_tree`,
      `${resource}:delete_tree`
    ]
  },
  manager: {
    label: 'Manager',
    icon: 'i-lucide-briefcase',
    description: 'Manage resources and team members',
    permissions: (resource: string) => [
      `${resource}:read`,
      `${resource}:update`,
      `${resource}:read_tree`,
      `${resource}:update_tree`,
      'user:read',
      'user:create',
      'user:update',
      'member:create',
      'member:update',
      'member:delete'
    ]
  },
  editor: {
    label: 'Editor',
    icon: 'i-lucide-pencil',
    description: 'Create and modify content',
    permissions: (resource: string) => [
      `${resource}:create`,
      `${resource}:read`,
      `${resource}:update`,
      'user:read'
    ]
  },
  viewer: {
    label: 'Read Only',
    icon: 'i-lucide-eye',
    description: 'View-only access',
    permissions: (resource: string) => [
      `${resource}:read`,
      'user:read'
    ]
  }
}

// Get display name for entity type
function getEntityTypeDisplay(type: string): string {
  return type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' ')
}

// Get icon for entity type
function getEntityTypeIcon(type: string): string {
  const iconMap: Record<string, string> = {
    platform: 'i-lucide-globe',
    organization: 'i-lucide-building',
    division: 'i-lucide-git-branch',
    branch: 'i-lucide-git-fork',
    team: 'i-lucide-users',
    access_group: 'i-lucide-shield',
    project: 'i-lucide-folder',
    department: 'i-lucide-briefcase'
  }
  return iconMap[type] || 'i-lucide-box'
}

// Toggle entity type expansion
function toggleType(type: string) {
  if (expandedTypes.value.has(type)) {
    expandedTypes.value.delete(type)
  } else {
    expandedTypes.value.add(type)
  }
}

// Toggle customization for entity type
function toggleCustomization(type: string) {
  const newPermissions = { ...props.entityTypePermissions }
  
  if (newPermissions[type]) {
    // Remove customization
    delete newPermissions[type]
    delete selectedTemplates.value[type]
  } else {
    // Add customization with default permissions as starting point
    newPermissions[type] = [...props.defaultPermissions]
    expandedTypes.value.add(type)
  }
  
  emit('update:entityTypePermissions', newPermissions)
}

// Update permissions for entity type
function updateTypePermissions(type: string, permissions: string[]) {
  const newPermissions = { ...props.entityTypePermissions }
  newPermissions[type] = permissions
  emit('update:entityTypePermissions', newPermissions)
}

// Apply template to entity type
function applyTemplate(type: string, templateKey: string) {
  selectedTemplates.value[type] = templateKey
  const template = permissionTemplates[templateKey as keyof typeof permissionTemplates]
  
  // Get unique resources from available permissions
  const resources = new Set<string>()
  permissionsStore.permissions.forEach(p => {
    if (p.resource) resources.add(p.resource)
  })
  
  // Generate permissions for all resources
  const permissions: string[] = []
  resources.forEach(resource => {
    const resourcePerms = template.permissions(resource)
    // Only add permissions that actually exist in the system
    resourcePerms.forEach(perm => {
      if (permissionsStore.permissions.find(p => p.name === perm)) {
        permissions.push(perm)
      }
    })
  })
  
  updateTypePermissions(type, permissions)
}

// Count permissions difference from default
function getPermissionDiff(type: string): { added: number; removed: number } {
  const customPerms = props.entityTypePermissions[type] || []
  const defaultPerms = props.defaultPermissions
  
  const added = customPerms.filter(p => !defaultPerms.includes(p)).length
  const removed = defaultPerms.filter(p => !customPerms.includes(p)).length
  
  return { added, removed }
}

// Check if permissions match a template
function matchesTemplate(permissions: string[], templateKey: string): boolean {
  const template = permissionTemplates[templateKey as keyof typeof permissionTemplates]
  const resources = new Set<string>()
  permissionsStore.permissions.forEach(p => {
    if (p.resource) resources.add(p.resource)
  })
  
  const expectedPerms = new Set<string>()
  resources.forEach(resource => {
    template.permissions(resource).forEach(perm => {
      if (permissionsStore.permissions.find(p => p.name === perm)) {
        expectedPerms.add(perm)
      }
    })
  })
  
  const actualPerms = new Set(permissions)
  
  if (expectedPerms.size !== actualPerms.size) return false
  
  for (const perm of expectedPerms) {
    if (!actualPerms.has(perm)) return false
  }
  
  return true
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">
          Context-Aware Permissions
        </h5>
        <p class="mt-1 text-sm text-muted-foreground">
          Customize permissions based on where this role is assigned
        </p>
      </div>
      <UTooltip text="Define different permissions for each entity type where this role can be assigned">
        <UIcon name="i-lucide-info" class="h-4 w-4 text-muted-foreground" />
      </UTooltip>
    </div>

    <!-- Default Permissions Info -->
    <UAlert v-if="defaultPermissions.length > 0" icon="i-lucide-info" color="primary" variant="subtle">
      <template #description>
        <span class="text-sm">
          By default, this role grants <strong>{{ defaultPermissions.length }}</strong> permissions. 
          Customize below to override permissions for specific entity types.
        </span>
      </template>
    </UAlert>

    <!-- Entity Type Cards -->
    <div class="grid gap-4">
      <UCard
        v-for="config in entityConfigs"
        :key="config.type"
        :class="{ 'ring-2 ring-primary': config.isCustomized }"
      >
        <!-- Card Header -->
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <UIcon :name="getEntityTypeIcon(config.type)" class="h-5 w-5" />
              <div>
                <h6 class="font-medium capitalize">
                  {{ getEntityTypeDisplay(config.type) }} Context
                </h6>
                <p v-if="config.isCustomized" class="text-xs text-muted-foreground">
                  <template v-if="getPermissionDiff(config.type).added > 0">
                    <span class="text-success">+{{ getPermissionDiff(config.type).added }}</span>
                  </template>
                  <template v-if="getPermissionDiff(config.type).removed > 0">
                    <span v-if="getPermissionDiff(config.type).added > 0" class="mx-1">•</span>
                    <span class="text-error">-{{ getPermissionDiff(config.type).removed }}</span>
                  </template>
                  <span v-if="getPermissionDiff(config.type).added === 0 && getPermissionDiff(config.type).removed === 0">
                    Same as default
                  </span>
                </p>
                <p v-else class="text-xs text-muted-foreground">
                  Uses default permissions
                </p>
              </div>
            </div>
            
            <div class="flex items-center gap-2">
              <UBadge 
                v-if="config.isCustomized" 
                :label="`${config.permissions.length} permissions`" 
                variant="subtle"
                size="xs"
              />
              <UButton
                v-if="config.isCustomized"
                size="xs"
                variant="ghost"
                icon="i-lucide-chevron-down"
                :class="{ 'rotate-180': expandedTypes.has(config.type) }"
                @click="toggleType(config.type)"
              />
              <UToggle
                :model-value="config.isCustomized"
                size="sm"
                @update:model-value="toggleCustomization(config.type)"
              />
            </div>
          </div>
        </template>

        <!-- Card Body - Expanded Content -->
        <div v-if="config.isCustomized && expandedTypes.has(config.type)" class="space-y-4">
          <!-- Permission Templates -->
          <div>
            <p class="text-sm font-medium mb-2">Quick Templates</p>
            <div class="grid grid-cols-2 gap-2">
              <UButton
                v-for="(template, key) in permissionTemplates"
                :key="key"
                variant="outline"
                size="xs"
                :icon="template.icon"
                :color="selectedTemplates[config.type] === key || matchesTemplate(config.permissions, key) ? 'primary' : 'neutral'"
                @click="applyTemplate(config.type, key)"
              >
                {{ template.label }}
              </UButton>
            </div>
          </div>

          <USeparator />

          <!-- Custom Permission Selector -->
          <div>
            <p class="text-sm font-medium mb-2">Custom Permissions</p>
            <RolesPermissionSelector
              :model-value="config.permissions"
              :entity-id="entityId"
              :entity-type="config.type"
              :show-suggestions="true"
              @update:model-value="(perms) => updateTypePermissions(config.type, perms)"
            />
          </div>

          <!-- Permission Preview -->
          <div class="bg-neutral-50 dark:bg-neutral-800/50 rounded-lg p-3">
            <p class="text-xs font-medium text-muted-foreground mb-2">
              When assigned at {{ getEntityTypeDisplay(config.type) }} level:
            </p>
            <div class="space-y-1">
              <div v-if="config.permissions.length === 0" class="text-sm text-muted-foreground italic">
                No permissions granted
              </div>
              <div v-else class="grid grid-cols-2 gap-1">
                <div 
                  v-for="perm in config.permissions.slice(0, 6)" 
                  :key="perm"
                  class="text-xs font-mono bg-white dark:bg-neutral-900 px-2 py-1 rounded"
                >
                  {{ perm }}
                </div>
                <div v-if="config.permissions.length > 6" class="text-xs text-muted-foreground px-2 py-1">
                  +{{ config.permissions.length - 6 }} more...
                </div>
              </div>
            </div>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Summary -->
    <div v-if="Object.keys(entityTypePermissions).length > 0" class="mt-6">
      <UAlert icon="i-lucide-sparkles" color="success" variant="subtle">
        <template #description>
          <span class="text-sm">
            This role has context-aware permissions configured for 
            <strong>{{ Object.keys(entityTypePermissions).length }}</strong> entity type(s).
            Users will get different permissions based on where this role is assigned.
          </span>
        </template>
      </UAlert>
    </div>
  </div>
</template>