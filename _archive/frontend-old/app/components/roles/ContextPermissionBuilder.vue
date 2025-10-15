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

// Fetch permissions on mount and expand first customized card
onMounted(() => {
  permissionsStore.fetchPermissions()
  
  // Automatically expand the first entity type that has customizations (accordion behavior)
  const customizedTypes = Object.keys(props.entityTypePermissions)
  if (customizedTypes.length > 0) {
    expandedTypes.value.add(customizedTypes[0])
  }
})

// Transform props into reactive entity configs
const entityConfigs = computed<EntityTypeConfig[]>(() => {
  return props.assignableTypes.map(type => ({
    type,
    permissions: props.entityTypePermissions[type] || [],
    isCustomized: !!props.entityTypePermissions[type]
  }))
})


// Get display name for entity type
function getEntityTypeDisplay(type: string): string {
  if (!type) return 'Unknown'
  return type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' ')
}

// Get icon for entity type
function getEntityTypeIcon(type: string): string {
  if (!type) return 'i-lucide-box'
  
  const iconMap: Record<string, string> = {
    platform: 'i-lucide-globe',
    organization: 'i-lucide-building',
    division: 'i-lucide-git-branch',
    branch: 'i-lucide-git-fork',
    team: 'i-lucide-users',
    access_group: 'i-lucide-shield',
    project: 'i-lucide-folder',
    department: 'i-lucide-briefcase',
    // Add more common entity types
    company: 'i-lucide-building-2',
    office: 'i-lucide-home',
    region: 'i-lucide-map',
    area: 'i-lucide-map-pin',
    group: 'i-lucide-users-2',
    unit: 'i-lucide-square',
    section: 'i-lucide-layout-grid',
    committee: 'i-lucide-users-round',
    board: 'i-lucide-presentation',
    // Default fallback for unknown types
  }
  
  // Try to find a matching icon by checking if the type contains certain keywords
  const typeL = type.toLowerCase()
  if (typeL.includes('team')) return 'i-lucide-users'
  if (typeL.includes('group')) return 'i-lucide-users-2'
  if (typeL.includes('org')) return 'i-lucide-building'
  if (typeL.includes('div')) return 'i-lucide-git-branch'
  if (typeL.includes('dept') || typeL.includes('department')) return 'i-lucide-briefcase'
  if (typeL.includes('project')) return 'i-lucide-folder'
  
  return iconMap[type] || 'i-lucide-box'
}

// Toggle entity type expansion (accordion behavior - only one at a time)
function toggleType(type: string) {
  if (expandedTypes.value.has(type)) {
    expandedTypes.value.clear()
  } else {
    expandedTypes.value.clear()
    expandedTypes.value.add(type)
  }
}

// Toggle customization for entity type
function toggleCustomization(type: string) {
  const newPermissions = { ...props.entityTypePermissions }
  
  if (newPermissions[type]) {
    // Remove customization
    delete newPermissions[type]
    // Also collapse the card
    expandedTypes.value.delete(type)
  } else {
    // Add customization with default permissions as starting point
    newPermissions[type] = [...props.defaultPermissions]
    // Automatically expand the card when enabling customization
    expandedTypes.value.clear()
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

// Count permissions difference from default
function getPermissionDiff(type: string): { added: number; removed: number } {
  const customPerms = props.entityTypePermissions[type] || []
  const defaultPerms = props.defaultPermissions
  
  const added = customPerms.filter(p => !defaultPerms.includes(p)).length
  const removed = defaultPerms.filter(p => !customPerms.includes(p)).length
  
  return { added, removed }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h5 class="text-sm font-medium uppercase tracking-wider text-primary">
          Context-Aware Permissions
        </h5>
        <p class="mt-1 text-sm text-muted-foreground">
          Customize permissions based on where this role is assigned
        </p>
      </div>
      <UTooltip text="Define different permissions for each entity type where this role can be assigned">
        <UIcon name="i-lucide-info" class="h-4 w-4 text-muted" />
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

    <!-- Entity Type List -->
    <div class="border border-default rounded-lg divide-y divide-default">
      <div
        v-for="config in entityConfigs"
        :key="config.type"
        class="group"
        :class="{ 'bg-primary/5': config.isCustomized }"
      >
        <!-- Compact Header Row -->
        <div 
          class="flex items-center justify-between p-4 cursor-pointer hover:bg-muted"
          @click="config.isCustomized && toggleType(config.type)"
        >
          <div class="flex items-center gap-3 flex-1">
            <UIcon :name="getEntityTypeIcon(config.type)" class="h-4 w-4 text-muted" />
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium capitalize">
                  {{ getEntityTypeDisplay(config.type) }}
                </span>
                <UBadge 
                  v-if="config.isCustomized" 
                  :label="`${config.permissions.length}`" 
                  variant="subtle"
                  size="xs"
                />
                <span v-if="config.isCustomized" class="text-xs text-muted">
                  <template v-if="getPermissionDiff(config.type).added > 0">
                    <span class="text-success">+{{ getPermissionDiff(config.type).added }}</span>
                  </template>
                  <template v-if="getPermissionDiff(config.type).removed > 0">
                    <span v-if="getPermissionDiff(config.type).added > 0" class="mx-1">•</span>
                    <span class="text-error">-{{ getPermissionDiff(config.type).removed }}</span>
                  </template>
                </span>
              </div>
            </div>
          </div>
          
          <div class="flex items-center gap-3">
            <UIcon 
              v-if="config.isCustomized"
              name="i-lucide-chevron-down"
              class="h-4 w-4 text-muted transition-transform"
              :class="{ 'rotate-180': expandedTypes.has(config.type) }"
            />
            <USwitch
              :model-value="config.isCustomized"
              @update:model-value="toggleCustomization(config.type)"
              @click.stop
            />
          </div>
        </div>

        <!-- Expanded Content -->
        <div v-if="config.isCustomized && expandedTypes.has(config.type)" class="border-t border-default bg-muted p-4">
          <!-- Custom Permission Selector -->
          <div>
            <p class="text-sm font-medium mb-3">Permissions for {{ getEntityTypeDisplay(config.type) }}</p>
            <RolesPermissionSelector
              :model-value="config.permissions"
              :entity-id="entityId"
              @update:model-value="(perms) => updateTypePermissions(config.type, perms)"
            />
          </div>
        </div>
      </div>
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