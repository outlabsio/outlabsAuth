<script setup lang="ts">
const open = defineModel<boolean>('open', { default: false })

const rolesStore = useRolesStore()
const toast = useToast()

// Available permissions
const availablePermissions = [
  // User permissions
  { value: 'user:read', label: 'User Read', category: 'Users' },
  { value: 'user:create', label: 'User Create', category: 'Users' },
  { value: 'user:update', label: 'User Update', category: 'Users' },
  { value: 'user:delete', label: 'User Delete', category: 'Users' },
  // Role permissions
  { value: 'role:read', label: 'Role Read', category: 'Roles' },
  { value: 'role:create', label: 'Role Create', category: 'Roles' },
  { value: 'role:update', label: 'Role Update', category: 'Roles' },
  { value: 'role:delete', label: 'Role Delete', category: 'Roles' },
  // Entity permissions
  { value: 'entity:read', label: 'Entity Read', category: 'Entities' },
  { value: 'entity:create', label: 'Entity Create', category: 'Entities' },
  { value: 'entity:update', label: 'Entity Update', category: 'Entities' },
  { value: 'entity:delete', label: 'Entity Delete', category: 'Entities' },
  // Permission permissions
  { value: 'permission:read', label: 'Permission Read', category: 'Permissions' },
  { value: 'permission:create', label: 'Permission Create', category: 'Permissions' },
  { value: 'permission:update', label: 'Permission Update', category: 'Permissions' },
  // API Key permissions
  { value: 'api_key:read', label: 'API Key Read', category: 'API Keys' },
  { value: 'api_key:create', label: 'API Key Create', category: 'API Keys' },
  { value: 'api_key:revoke', label: 'API Key Revoke', category: 'API Keys' }
]

// Group permissions by category
const permissionsByCategory = computed(() => {
  const grouped: Record<string, typeof availablePermissions> = {}
  availablePermissions.forEach(perm => {
    if (!grouped[perm.category]) {
      grouped[perm.category] = []
    }
    grouped[perm.category].push(perm)
  })
  return grouped
})

// Form state
const state = reactive({
  name: '',
  display_name: '',
  description: '',
  permissions: [] as string[],
  entity_type: undefined as string | undefined,
  is_context_aware: false
})

// Auto-generate name from display_name
watch(() => state.display_name, (newDisplayName) => {
  if (newDisplayName && !state.name) {
    state.name = newDisplayName.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_-]/g, '')
  }
})

// Entity type options for context-aware roles
const entityTypeOptions = [
  { label: 'None (Global Role)', value: undefined },
  { label: 'Organization', value: 'organization' },
  { label: 'Department', value: 'department' },
  { label: 'Team', value: 'team' },
  { label: 'Project', value: 'project' },
  { label: 'Division', value: 'division' }
]

// Clear entity_type when not context-aware
watch(() => state.is_context_aware, (isContextAware) => {
  if (!isContextAware) {
    state.entity_type = undefined
  }
})

// Helper to check if all permissions in a category are selected
function isCategoryFullySelected(category: string) {
  const categoryPerms = permissionsByCategory.value[category]
  if (!categoryPerms) return false
  return categoryPerms.every(perm => state.permissions.includes(perm.value))
}

// Helper to toggle all permissions in a category
function toggleCategory(category: string) {
  const categoryPerms = permissionsByCategory.value[category]
  if (!categoryPerms) return

  const isFullySelected = isCategoryFullySelected(category)

  if (isFullySelected) {
    // Remove all permissions from this category
    state.permissions = state.permissions.filter(
      p => !categoryPerms.some(cp => cp.value === p)
    )
  } else {
    // Add all permissions from this category
    const newPerms = categoryPerms.map(p => p.value)
    state.permissions = [...new Set([...state.permissions, ...newPerms])]
  }
}

// Submit handler
const isSubmitting = ref(false)
const showPermissionsHelp = ref(false)

async function handleSubmit() {
  isSubmitting.value = true
  try {
    const success = await rolesStore.createRole(state)

    if (success) {
      toast.add({
        title: 'Role created',
        description: `${state.display_name} has been created successfully.`,
        color: 'success'
      })

      // Close modal and reset form
      open.value = false
      Object.assign(state, {
        name: '',
        display_name: '',
        description: '',
        permissions: [],
        entity_type: undefined,
        is_context_aware: false
      })
    } else {
      toast.add({
        title: 'Error',
        description: 'Failed to create role. Please try again.',
        color: 'error'
      })
    }
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.message || 'Failed to create role',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Create Role"
    description="Create a new role with specific permissions"
    fullscreen
  >
    <template #body>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
        <!-- Left Column: Basic Info -->
        <div class="space-y-6">
          <div class="space-y-4">
            <h3 class="text-lg font-semibold flex items-center gap-2">
              <UIcon name="i-lucide-info" class="w-5 h-5" />
              Basic Information
            </h3>

            <!-- Grid layout for Display Name and Name only -->
            <div class="grid grid-cols-2 gap-4">
              <div class="space-y-2">
                <label class="block text-sm font-medium flex items-center gap-1.5">
                  Display Name
                  <UPopover>
                    <UButton
                      icon="i-lucide-help-circle"
                      color="neutral"
                      variant="ghost"
                      size="2xs"
                      class="text-muted hover:text-highlighted"
                    />
                    <template #content>
                      <div class="p-4 max-w-xs space-y-2">
                        <h4 class="font-semibold text-sm">Display Name</h4>
                        <p class="text-sm text-muted">
                          The human-friendly name shown throughout the UI. This is what users will see when viewing or selecting roles.
                        </p>
                        <div class="text-xs text-muted mt-2">
                          <p class="font-medium mb-1">Examples:</p>
                          <ul class="list-disc list-inside pl-2 space-y-0.5">
                            <li>"Content Manager"</li>
                            <li>"Department Admin"</li>
                            <li>"Regional Supervisor"</li>
                          </ul>
                        </div>
                      </div>
                    </template>
                  </UPopover>
                </label>
                <UInput
                  v-model="state.display_name"
                  placeholder="Content Manager"
                  icon="i-lucide-shield"
                />
              </div>

              <div class="space-y-2">
                <label class="block text-sm font-medium flex items-center gap-1.5">
                  Name
                  <UPopover>
                    <UButton
                      icon="i-lucide-help-circle"
                      color="neutral"
                      variant="ghost"
                      size="2xs"
                      class="text-muted hover:text-highlighted"
                    />
                    <template #content>
                      <div class="p-4 max-w-xs space-y-2">
                        <h4 class="font-semibold text-sm">Role Name (Identifier)</h4>
                        <p class="text-sm text-muted">
                          The technical identifier used in code, APIs, and database. Must be unique, lowercase, and use underscores or hyphens only.
                        </p>
                        <div class="text-xs text-muted mt-2">
                          <p class="font-medium mb-1">Examples:</p>
                          <ul class="list-disc list-inside pl-2 space-y-0.5">
                            <li>"content_manager"</li>
                            <li>"dept-admin"</li>
                            <li>"regional_supervisor"</li>
                          </ul>
                        </div>
                        <UAlert
                          icon="i-lucide-lightbulb"
                          color="info"
                          variant="subtle"
                          description="Auto-generated from Display Name, but you can customize it."
                          class="mt-2"
                        />
                      </div>
                    </template>
                  </UPopover>
                </label>
                <UInput
                  v-model="state.name"
                  placeholder="content_manager"
                  icon="i-lucide-tag"
                />
                <p class="text-xs text-muted">Lowercase, no spaces</p>
              </div>
            </div>

            <!-- Full width description outside the grid -->
            <div class="space-y-2 w-full">
              <label class="block text-sm font-medium">Description</label>
              <UTextarea
                v-model="state.description"
                placeholder="A brief description of what this role can do..."
                :rows="4"
                class="w-full"
              />
            </div>
          </div>

          <UDivider />

          <div>
            <h3 class="text-lg font-semibold mb-4 flex items-center gap-2">
              <UIcon name="i-lucide-settings" class="w-5 h-5" />
              Context Settings
              <UPopover>
                <UButton
                  icon="i-lucide-help-circle"
                  color="neutral"
                  variant="ghost"
                  size="xs"
                />
                <template #content>
                  <div class="p-4 max-w-sm space-y-2">
                    <h4 class="font-semibold text-sm">Context-Aware Roles</h4>
                    <p class="text-sm text-muted">
                      Enable this for roles that should have different permissions based on the entity type they're assigned to.
                    </p>
                    <div class="text-xs text-muted mt-2 space-y-1">
                      <p class="font-medium">Example:</p>
                      <p>A "Manager" role could have:</p>
                      <ul class="list-disc list-inside pl-2">
                        <li>Full control in Teams</li>
                        <li>Read-only in Departments</li>
                        <li>No access in Organizations</li>
                      </ul>
                    </div>
                  </div>
                </template>
              </UPopover>
            </h3>

            <div class="space-y-3">
              <UCheckbox
                v-model="state.is_context_aware"
                label="Context-aware role"
                help="Role permissions adapt based on entity type"
              />

              <div v-if="state.is_context_aware" class="space-y-2">
                <label class="block text-sm font-medium flex items-center gap-1.5">
                  Entity Type
                  <UPopover>
                    <UButton
                      icon="i-lucide-help-circle"
                      color="neutral"
                      variant="ghost"
                      size="2xs"
                      class="text-muted hover:text-highlighted"
                    />
                    <template #content>
                      <div class="p-4 max-w-sm space-y-2">
                        <h4 class="font-semibold text-sm">Entity Type</h4>
                        <p class="text-sm text-muted">
                          Specify which type of entity this role's permissions apply to. When assigned, the role will adapt its permissions based on the entity type.
                        </p>
                        <UAlert
                          icon="i-lucide-lightbulb"
                          color="info"
                          variant="subtle"
                          title="Context-Aware Behavior"
                          description="Same role, different permissions depending on where it's assigned in your organization."
                          class="mt-2"
                        />
                        <div class="text-xs text-muted mt-2">
                          <p class="font-medium mb-1">Example:</p>
                          <p class="mb-1">A "Manager" role set to "Team" type:</p>
                          <ul class="list-disc list-inside pl-2 space-y-0.5">
                            <li>Full permissions when assigned to a Team</li>
                            <li>Different permissions when assigned to a Department</li>
                            <li>May have no permissions at Organization level</li>
                          </ul>
                        </div>
                      </div>
                    </template>
                  </UPopover>
                </label>
                <USelect
                  v-model="state.entity_type"
                  :items="entityTypeOptions"
                  placeholder="Select entity type"
                />
                <p class="text-xs text-muted">Which entity type does this role apply to?</p>
              </div>
            </div>
          </div>

          <!-- Selected permissions count -->
          <UCard>
            <div class="flex items-center gap-3">
              <div class="p-2 bg-primary/10 rounded-lg">
                <UIcon name="i-lucide-check-circle" class="w-6 h-6 text-primary" />
              </div>
              <div>
                <p class="text-2xl font-bold">{{ state.permissions.length }}</p>
                <p class="text-sm text-muted">Permission(s) selected</p>
              </div>
            </div>
          </UCard>
        </div>

        <!-- Right Columns: Permissions (2 columns) -->
        <div class="lg:col-span-2 space-y-6">
          <div>
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold flex items-center gap-2">
                <UIcon name="i-lucide-shield-check" class="w-5 h-5" />
                Permissions
              </h3>
              <UButton
                label="Learn about permissions"
                icon="i-lucide-book-open"
                color="neutral"
                variant="ghost"
                size="xs"
                @click="showPermissionsHelp = true"
              />
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div v-for="(perms, category) in permissionsByCategory" :key="category">
                <UCard>
                  <!-- Category header with select all -->
                  <div class="flex items-center justify-between mb-3">
                    <h4 class="text-sm font-semibold">{{ category }}</h4>
                    <UButton
                      :label="isCategoryFullySelected(category) ? 'Clear' : 'All'"
                      size="xs"
                      :variant="isCategoryFullySelected(category) ? 'solid' : 'ghost'"
                      :color="isCategoryFullySelected(category) ? 'primary' : 'neutral'"
                      @click="toggleCategory(category)"
                    />
                  </div>

                  <!-- Permission checkboxes -->
                  <div class="space-y-2">
                    <div v-for="perm in perms" :key="perm.value">
                      <UCheckbox
                        :model-value="state.permissions.includes(perm.value)"
                        @update:model-value="(checked) => {
                          if (checked) {
                            state.permissions = [...state.permissions, perm.value]
                          } else {
                            state.permissions = state.permissions.filter(p => p !== perm.value)
                          }
                        }"
                        :label="perm.label"
                      />
                    </div>
                  </div>
                </UCard>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex items-center justify-between w-full">
        <div class="text-sm text-muted">
          All fields are required except description and context settings
        </div>
        <div class="flex justify-end gap-2">
          <UButton
            label="Cancel"
            color="neutral"
            variant="outline"
            @click="open = false"
            :disabled="isSubmitting"
          />
          <UButton
            label="Create Role"
            icon="i-lucide-shield"
            :loading="isSubmitting"
            @click="handleSubmit"
          />
        </div>
      </div>
    </template>
  </UModal>

  <!-- Permissions Help Slideover -->
  <USlideover v-model:open="showPermissionsHelp" title="Understanding Permissions">
    <template #body>
      <div class="space-y-6">
        <div>
          <h4 class="font-semibold mb-2">Permission Format</h4>
          <p class="text-sm text-muted mb-3">
            Permissions follow the pattern: <code class="px-1.5 py-0.5 bg-elevated rounded text-xs">resource:action</code>
          </p>
          <div class="space-y-2 text-sm">
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-arrow-right" class="w-4 h-4 mt-0.5 text-primary" />
              <div>
                <code class="text-xs bg-elevated px-1.5 py-0.5 rounded">user:read</code>
                <span class="text-muted ml-2">Read user information</span>
              </div>
            </div>
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-arrow-right" class="w-4 h-4 mt-0.5 text-primary" />
              <div>
                <code class="text-xs bg-elevated px-1.5 py-0.5 rounded">user:create</code>
                <span class="text-muted ml-2">Create new users</span>
              </div>
            </div>
          </div>
        </div>

        <UDivider />

        <div>
          <h4 class="font-semibold mb-2">Tree Permissions (EnterpriseRBAC)</h4>
          <p class="text-sm text-muted mb-3">
            Tree permissions allow hierarchical access control across entity trees.
          </p>
          <UAlert
            icon="i-lucide-lightbulb"
            color="info"
            variant="subtle"
            title="What are tree permissions?"
            description="Permissions ending in '_tree' grant access to the entity and all its descendants in the hierarchy."
          />
          <div class="mt-3 space-y-2 text-sm">
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-tree-deciduous" class="w-4 h-4 mt-0.5 text-success" />
              <div>
                <code class="text-xs bg-elevated px-1.5 py-0.5 rounded">user:read_tree</code>
                <p class="text-muted text-xs mt-1">Read users in this entity AND all child entities</p>
              </div>
            </div>
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-tree-deciduous" class="w-4 h-4 mt-0.5 text-success" />
              <div>
                <code class="text-xs bg-elevated px-1.5 py-0.5 rounded">entity:manage_tree</code>
                <p class="text-muted text-xs mt-1">Manage this entity AND all descendant entities</p>
              </div>
            </div>
          </div>
        </div>

        <UDivider />

        <div>
          <h4 class="font-semibold mb-2">Permission Categories</h4>
          <div class="space-y-3 text-sm">
            <div>
              <p class="font-medium mb-1 flex items-center gap-2">
                <UIcon name="i-lucide-users" class="w-4 h-4 text-primary" />
                Users
              </p>
              <p class="text-muted text-xs">Manage user accounts, profiles, and authentication</p>
            </div>
            <div>
              <p class="font-medium mb-1 flex items-center gap-2">
                <UIcon name="i-lucide-shield" class="w-4 h-4 text-primary" />
                Roles
              </p>
              <p class="text-muted text-xs">Create and modify role definitions and assignments</p>
            </div>
            <div>
              <p class="font-medium mb-1 flex items-center gap-2">
                <UIcon name="i-lucide-building" class="w-4 h-4 text-primary" />
                Entities
              </p>
              <p class="text-muted text-xs">Manage organizational structure (departments, teams, etc.)</p>
            </div>
            <div>
              <p class="font-medium mb-1 flex items-center gap-2">
                <UIcon name="i-lucide-key" class="w-4 h-4 text-primary" />
                API Keys
              </p>
              <p class="text-muted text-xs">Create and manage programmatic access keys</p>
            </div>
          </div>
        </div>

        <UDivider />

        <div>
          <h4 class="font-semibold mb-2">Best Practices</h4>
          <div class="space-y-2 text-sm text-muted">
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="w-4 h-4 mt-0.5 text-success" />
              <span>Grant minimum permissions needed (principle of least privilege)</span>
            </div>
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="w-4 h-4 mt-0.5 text-success" />
              <span>Use tree permissions for managers overseeing teams</span>
            </div>
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="w-4 h-4 mt-0.5 text-success" />
              <span>Group related permissions into meaningful roles</span>
            </div>
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="w-4 h-4 mt-0.5 text-success" />
              <span>Review and audit role permissions regularly</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </USlideover>
</template>
