<script setup lang="ts">
import { useCreatePermissionMutation } from '~/queries/permissions'
import type { CreatePermissionData } from '~/api/permissions'

const open = defineModel<boolean>('open', { default: false })

const toast = useToast()

// Show help slideover
const showPermissionHelp = ref(false)

// Form state
const state = reactive({
  name: '',
  display_name: '',
  description: '',
  resource: '',
  action: '',
  scope: null as string | null,
  is_system: false,
  is_active: true,
  tags: [] as string[],
  metadata: {} as Record<string, any>
})

// Create mutation
const { mutate: createPermission, isPending: isSubmitting } = useCreatePermissionMutation()

// Auto-parse permission name
watch(() => state.name, (newName) => {
  if (newName && newName.includes(':')) {
    const parts = newName.split(':')
    if (parts.length >= 2 && parts[0] && parts[1]) {
      state.resource = parts[0].trim()

      // Check for scope suffix
      const actionPart = parts[1].trim()
      const scopeSuffixes = ['_tree', '_all']
      let foundScope = null

      for (const suffix of scopeSuffixes) {
        if (actionPart.endsWith(suffix)) {
          state.action = actionPart.substring(0, actionPart.length - suffix.length)
          foundScope = suffix.substring(1) // Remove the underscore
          break
        }
      }

      if (!foundScope) {
        state.action = actionPart
        state.scope = null
      } else {
        state.scope = foundScope
      }
    }
  }
})

// Available tags
const availableTags = [
  'user-management',
  'access-control',
  'entity-management',
  'api-management',
  'read-only',
  'write',
  'dangerous',
  'hierarchical',
  'finance',
  'reporting',
  'project-management',
  'organization',
  'system',
  'admin',
  'approval',
  'export'
]

// Scope options
const scopeOptions = [
  { value: null, label: 'None', description: 'Permission applies only to the specific resource' },
  { value: 'tree', label: 'Tree', description: 'Permission applies to resource and all descendants' },
  { value: 'all', label: 'All', description: 'Permission applies globally across all entities' }
]

// Selected scope for visual display
const selectedScopeOption = computed(() => {
  return scopeOptions.find(opt => opt.value === state.scope) || scopeOptions[0]
})

// Form validation
const canSubmit = computed(() => {
  return state.name.trim() !== '' &&
         state.display_name.trim() !== '' &&
         state.name.includes(':') &&
         state.resource.trim() !== '' &&
         state.action.trim() !== ''
})

// Validation message
const validationMessage = computed(() => {
  if (!state.name.trim()) return 'Permission name is required'
  if (!state.name.includes(':')) return 'Permission name must be in format resource:action'
  if (!state.display_name.trim()) return 'Display name is required'
  return ''
})

// Submit handler
async function handleSubmit() {
  if (!canSubmit.value) {
    toast.add({
      title: 'Validation Error',
      description: validationMessage.value,
      color: 'error'
    })
    return
  }

  // Prepare data for API
  const permissionData: CreatePermissionData = {
    name: state.name,
    display_name: state.display_name,
    description: state.description || undefined,
    is_system: state.is_system,
    is_active: state.is_active,
    tags: state.tags.length > 0 ? state.tags : undefined,
    metadata: Object.keys(state.metadata).length > 0 ? state.metadata : undefined
  }

  // Call mutation - toasts handled by mutation callbacks
  await createPermission(permissionData)

  // Close modal on success
  closeModal()
}

// Close and reset
function closeModal() {
  open.value = false
  setTimeout(() => {
    Object.assign(state, {
      name: '',
      display_name: '',
      description: '',
      resource: '',
      action: '',
      scope: null,
      is_system: false,
      is_active: true,
      tags: [],
      metadata: {}
    })
  }, 300)
}

// Format examples based on current state
const formatExample = computed(() => {
  if (!state.resource || !state.action) {
    return 'user:create'
  }
  const base = `${state.resource}:${state.action}`
  if (state.scope) {
    return `${base}_${state.scope}`
  }
  return base
})
</script>

<template>
  <UModal
    v-model:open="open"
    title="Create Permission"
    description="Define a new permission for your authorization system"
    fullscreen
  >
    <template #description>
      <div class="flex items-center justify-between w-full">
        <p class="text-sm text-muted">Define a new permission for your authorization system</p>
        <UButton
          icon="i-lucide-book-open"
          label="Learn about Permissions"
          variant="ghost"
          color="neutral"
          size="xs"
          @click="showPermissionHelp = true"
        />
      </div>
    </template>

    <template #body>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 h-full">
        <!-- Left Column: Basic Information -->
        <div class="space-y-6">
          <!-- Section: Basic Information -->
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-info" class="w-5 h-5 text-primary" />
              <h3 class="text-lg font-semibold">Basic Information</h3>
            </div>

            <!-- Permission Name -->
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <label class="block text-sm font-medium">Permission Name</label>
                <UPopover>
                  <UButton icon="i-lucide-help-circle" size="xs" variant="ghost" color="neutral" />
                  <template #content>
                    <div class="p-4 max-w-sm space-y-2">
                      <p class="font-semibold text-sm">Permission Format</p>
                      <p class="text-sm text-muted">
                        Use the format: <code class="text-xs bg-neutral-100 dark:bg-neutral-800 px-1 py-0.5 rounded">resource:action</code>
                      </p>
                      <div class="space-y-1">
                        <p class="text-xs font-medium">Examples:</p>
                        <ul class="text-xs text-muted space-y-1 list-disc list-inside">
                          <li><code>user:create</code> - Create users</li>
                          <li><code>invoice:approve</code> - Approve invoices</li>
                          <li><code>report:export</code> - Export reports</li>
                          <li><code>entity:read_tree</code> - Read with tree scope</li>
                        </ul>
                      </div>
                      <p class="text-xs text-muted">
                        Resource and action will be auto-parsed from this name.
                      </p>
                    </div>
                  </template>
                </UPopover>
              </div>
              <UInput
                v-model="state.name"
                placeholder="resource:action"
                icon="i-lucide-key"
                :class="state.name && !state.name.includes(':') ? 'border-error' : ''"
              />
              <p class="text-xs text-muted">Current format: <code class="font-mono">{{ formatExample }}</code></p>
            </div>

            <!-- Display Name -->
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <label class="block text-sm font-medium">Display Name</label>
                <UPopover>
                  <UButton icon="i-lucide-help-circle" size="xs" variant="ghost" color="neutral" />
                  <template #content>
                    <div class="p-4 max-w-sm space-y-2">
                      <p class="font-semibold text-sm">Human-Readable Name</p>
                      <p class="text-sm text-muted">
                        A friendly name that will be displayed in the UI when showing this permission.
                      </p>
                      <div class="space-y-1">
                        <p class="text-xs font-medium">Examples:</p>
                        <ul class="text-xs text-muted space-y-1 list-disc list-inside">
                          <li>"Create Users"</li>
                          <li>"Approve Invoices"</li>
                          <li>"Export Reports"</li>
                          <li>"Read Entities (Tree)"</li>
                        </ul>
                      </div>
                    </div>
                  </template>
                </UPopover>
              </div>
              <UInput
                v-model="state.display_name"
                placeholder="Create Users"
                icon="i-lucide-tag"
              />
            </div>

            <!-- Description -->
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <label class="block text-sm font-medium">Description</label>
                <UPopover>
                  <UButton icon="i-lucide-help-circle" size="xs" variant="ghost" color="neutral" />
                  <template #content>
                    <div class="p-4 max-w-sm space-y-2">
                      <p class="font-semibold text-sm">Permission Description</p>
                      <p class="text-sm text-muted">
                        Detailed explanation of what this permission allows users to do.
                      </p>
                      <p class="text-xs text-muted">
                        This helps administrators understand the permission's purpose when assigning roles.
                      </p>
                    </div>
                  </template>
                </UPopover>
              </div>
              <UTextarea
                v-model="state.description"
                placeholder="Describe what this permission allows..."
                :rows="3"
                class="w-full"
              />
            </div>
          </div>

          <!-- Section: Auto-Parsed Values -->
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-wand-2" class="w-5 h-5 text-purple-500" />
              <h3 class="text-lg font-semibold">Auto-Parsed Values</h3>
            </div>

            <UAlert
              icon="i-lucide-info"
              color="primary"
              variant="subtle"
              title="Automatically Derived"
              description="These values are parsed from the permission name. You can override them if needed."
            />

            <!-- Resource -->
            <div class="space-y-2">
              <label class="block text-sm font-medium">Resource</label>
              <UInput
                v-model="state.resource"
                placeholder="user"
                icon="i-lucide-database"
                :disabled="!state.name || !state.name.includes(':')"
              />
            </div>

            <!-- Action -->
            <div class="space-y-2">
              <label class="block text-sm font-medium">Action</label>
              <UInput
                v-model="state.action"
                placeholder="create"
                icon="i-lucide-zap"
                :disabled="!state.name || !state.name.includes(':')"
              />
            </div>
          </div>
        </div>

        <!-- Right Columns: Scope, Settings & Tags -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Section: Permission Scope -->
          <div class="space-y-4">
            <div class="flex items-center gap-2 justify-between">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-layers" class="w-5 h-5 text-primary" />
                <h3 class="text-lg font-semibold">Permission Scope</h3>
              </div>
              <UPopover>
                <UButton icon="i-lucide-help-circle" size="xs" variant="ghost" color="neutral" />
                <template #content>
                  <div class="p-4 max-w-md space-y-2">
                    <p class="font-semibold text-sm">What is Scope?</p>
                    <p class="text-sm text-muted">
                      Scope determines how the permission applies in hierarchical entity structures:
                    </p>
                    <ul class="text-xs text-muted space-y-2 mt-2">
                      <li><strong>None:</strong> Permission only applies to the specific resource in the current entity</li>
                      <li><strong>Tree:</strong> Permission applies to the resource in current entity AND all descendant entities</li>
                      <li><strong>All:</strong> Permission applies globally across all entities (rare)</li>
                    </ul>
                  </div>
                </template>
              </UPopover>
            </div>

            <!-- Scope Selection Cards -->
            <div class="grid grid-cols-3 gap-4">
              <UCard
                v-for="option in scopeOptions"
                :key="option.value || 'none'"
                :class="[
                  'cursor-pointer transition-all',
                  state.scope === option.value
                    ? 'ring-2 ring-primary bg-primary/5'
                    : 'hover:bg-neutral-50 dark:hover:bg-neutral-800'
                ]"
                @click="state.scope = option.value"
              >
                <div class="space-y-2">
                  <div class="flex items-center justify-between">
                    <p class="font-semibold text-sm">{{ option.label }}</p>
                    <UIcon
                      v-if="state.scope === option.value"
                      name="i-lucide-check-circle"
                      class="w-5 h-5 text-primary"
                    />
                    <UIcon
                      v-else
                      :name="option.value === 'tree' ? 'i-lucide-git-branch' : option.value === 'all' ? 'i-lucide-globe' : 'i-lucide-circle'"
                      class="w-5 h-5 text-muted"
                    />
                  </div>
                  <p class="text-xs text-muted">{{ option.description }}</p>
                </div>
              </UCard>
            </div>

            <!-- Scope Visualization -->
            <UCard v-if="state.scope === 'tree'">
              <div class="space-y-2">
                <p class="text-sm font-medium flex items-center gap-2">
                  <UIcon name="i-lucide-info" class="w-4 h-4 text-blue-500" />
                  Tree Scope Example
                </p>
                <div class="bg-neutral-50 dark:bg-neutral-900 p-3 rounded text-xs font-mono space-y-1">
                  <div>[+] Company (Has permission)</div>
                  <div class="pl-4">[+] Engineering (Inherited)</div>
                  <div class="pl-8">[+] Backend Team (Inherited)</div>
                  <div class="pl-8">[+] Frontend Team (Inherited)</div>
                  <div class="pl-4">[+] Sales (Inherited)</div>
                </div>
                <p class="text-xs text-muted">
                  With tree scope, granting <code>{{ formatExample }}</code> at the Company level
                  automatically grants it to all departments and teams below.
                </p>
              </div>
            </UCard>
          </div>

          <!-- Section: Settings -->
          <div class="space-y-4">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-settings" class="w-5 h-5 text-primary" />
              <h3 class="text-lg font-semibold">Settings</h3>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <!-- System Permission -->
              <UCard>
                <div class="space-y-3">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <label class="text-sm font-medium">System Permission</label>
                      <UPopover>
                        <UButton icon="i-lucide-help-circle" size="xs" variant="ghost" color="neutral" />
                        <template #content>
                          <div class="p-4 max-w-sm space-y-2">
                            <p class="font-semibold text-sm">System vs Custom</p>
                            <p class="text-sm text-muted">
                              <strong>System permissions</strong> are built-in and cannot be deleted.
                              They're typically for core functionality like user management, roles, and entities.
                            </p>
                            <p class="text-sm text-muted">
                              <strong>Custom permissions</strong> are application-specific and can be freely created and deleted.
                            </p>
                            <p class="text-xs text-warning">
                              [!] Only mark as system if this is a core permission that should never be removed.
                            </p>
                          </div>
                        </template>
                      </UPopover>
                    </div>
                    <UToggle v-model="state.is_system" />
                  </div>
                  <p class="text-xs text-muted">
                    {{ state.is_system ? 'Built-in permission, cannot be deleted' : 'Custom permission, can be managed freely' }}
                  </p>
                </div>
              </UCard>

              <!-- Active -->
              <UCard>
                <div class="space-y-3">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                      <label class="text-sm font-medium">Active</label>
                      <UPopover>
                        <UButton icon="i-lucide-help-circle" size="xs" variant="ghost" color="neutral" />
                        <template #content>
                          <div class="p-4 max-w-sm space-y-2">
                            <p class="font-semibold text-sm">Permission Status</p>
                            <p class="text-sm text-muted">
                              Inactive permissions are ignored during authorization checks.
                              This is useful for temporarily disabling permissions without deleting them.
                            </p>
                            <p class="text-xs text-muted">
                              Users with inactive permissions will be denied access as if they don't have the permission.
                            </p>
                          </div>
                        </template>
                      </UPopover>
                    </div>
                    <UToggle v-model="state.is_active" />
                  </div>
                  <p class="text-xs text-muted">
                    {{ state.is_active ? 'Permission is active and will be checked' : 'Permission is disabled and will be ignored' }}
                  </p>
                </div>
              </UCard>
            </div>
          </div>

          <!-- Section: Tags & Categories -->
          <div class="space-y-4">
            <div class="flex items-center gap-2 justify-between">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-tags" class="w-5 h-5 text-primary" />
                <h3 class="text-lg font-semibold">Tags & Categories</h3>
              </div>
              <UPopover>
                <UButton icon="i-lucide-help-circle" size="xs" variant="ghost" color="neutral" />
                <template #content>
                  <div class="p-4 max-w-sm space-y-2">
                    <p class="font-semibold text-sm">Organizing Permissions</p>
                    <p class="text-sm text-muted">
                      Tags help categorize and filter permissions. Common tags include:
                    </p>
                    <ul class="text-xs text-muted space-y-1 list-disc list-inside">
                      <li><strong>user-management:</strong> User-related permissions</li>
                      <li><strong>read-only:</strong> Read/view permissions</li>
                      <li><strong>write:</strong> Create/update/delete permissions</li>
                      <li><strong>dangerous:</strong> Permissions that can cause data loss</li>
                      <li><strong>hierarchical:</strong> Permissions with tree scope</li>
                    </ul>
                  </div>
                </template>
              </UPopover>
            </div>

            <!-- Tag Selection -->
            <div class="space-y-2">
              <p class="text-sm text-muted">Select tags to categorize this permission</p>
              <div class="flex flex-wrap gap-2">
                <UBadge
                  v-for="tag in availableTags"
                  :key="tag"
                  :color="state.tags.includes(tag) ? 'primary' : 'neutral'"
                  :variant="state.tags.includes(tag) ? 'solid' : 'outline'"
                  class="cursor-pointer"
                  @click="
                    state.tags.includes(tag)
                      ? state.tags = state.tags.filter(t => t !== tag)
                      : state.tags.push(tag)
                  "
                >
                  {{ tag }}
                </UBadge>
              </div>
              <p v-if="state.tags.length > 0" class="text-xs text-muted mt-2">
                Selected: {{ state.tags.join(', ') }}
              </p>
            </div>
          </div>

          <!-- Help Button -->
          <div class="pt-4 border-t">
            <UButton
              icon="i-lucide-book-open"
              label="Learn about Permissions"
              variant="outline"
              color="primary"
              block
              @click="showPermissionHelp = true"
            />
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-between items-center w-full">
        <div>
          <p v-if="validationMessage && !canSubmit" class="text-sm text-error">
            {{ validationMessage }}
          </p>
        </div>
        <div class="flex gap-2">
          <UButton
            label="Cancel"
            color="neutral"
            variant="outline"
            @click="closeModal"
            :disabled="isSubmitting"
          />
          <UButton
            label="Create Permission"
            icon="i-lucide-shield-plus"
            :loading="isSubmitting"
            :disabled="!canSubmit"
            @click="handleSubmit"
          />
        </div>
      </div>
    </template>
  </UModal>

  <!-- Permission Help Slideover -->
  <USlideover v-model:open="showPermissionHelp" title="Understanding Permissions">
    <template #body>
      <div class="space-y-6">
      <!-- What are Permissions -->
      <div class="space-y-3">
        <h3 class="text-lg font-semibold flex items-center gap-2">
          <UIcon name="i-lucide-shield-check" class="w-5 h-5 text-primary" />
          What are Permissions?
        </h3>
        <p class="text-sm text-muted">
          Permissions define what actions users can perform on specific resources in your application.
          They are the building blocks of your authorization system.
        </p>
      </div>

      <USeparator />

      <!-- Permission Format -->
      <div class="space-y-3">
        <h3 class="text-lg font-semibold flex items-center gap-2">
          <UIcon name="i-lucide-code" class="w-5 h-5 text-primary" />
          Permission Format
        </h3>
        <p class="text-sm text-muted">
          All permissions follow the format: <code class="text-xs bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded font-mono">resource:action</code>
        </p>
        <div class="space-y-2">
          <p class="text-sm font-medium">Structure:</p>
          <ul class="text-sm text-muted space-y-1 list-disc list-inside">
            <li><strong>Resource:</strong> The thing being accessed (user, role, entity, invoice, etc.)</li>
            <li><strong>Action:</strong> What you want to do with it (create, read, update, delete, approve, etc.)</li>
            <li><strong>Scope (optional):</strong> How broadly it applies (_tree, _all)</li>
          </ul>
        </div>
      </div>

      <USeparator />

      <!-- Permission Examples -->
      <div class="space-y-3">
        <h3 class="text-lg font-semibold flex items-center gap-2">
          <UIcon name="i-lucide-list" class="w-5 h-5 text-primary" />
          Common Examples
        </h3>
        <div class="space-y-3">
          <UCard>
            <div class="space-y-2">
              <code class="text-sm font-mono text-primary">user:create</code>
              <p class="text-xs text-muted">Allows creating new user accounts</p>
            </div>
          </UCard>
          <UCard>
            <div class="space-y-2">
              <code class="text-sm font-mono text-primary">invoice:approve</code>
              <p class="text-xs text-muted">Allows approving invoices for payment</p>
            </div>
          </UCard>
          <UCard>
            <div class="space-y-2">
              <code class="text-sm font-mono text-primary">entity:read_tree</code>
              <p class="text-xs text-muted">Allows viewing entity and all descendants in hierarchy</p>
            </div>
          </UCard>
          <UCard>
            <div class="space-y-2">
              <code class="text-sm font-mono text-primary">*:*</code>
              <p class="text-xs text-muted">Wildcard: Grants all permissions (superuser)</p>
            </div>
          </UCard>
        </div>
      </div>

      <USeparator />

      <!-- Scope Explanation -->
      <div class="space-y-3">
        <h3 class="text-lg font-semibold flex items-center gap-2">
          <UIcon name="i-lucide-layers" class="w-5 h-5 text-primary" />
          Permission Scopes
        </h3>
        <div class="space-y-3">
          <UCard>
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-circle" class="w-4 h-4" />
                <p class="font-semibold text-sm">None (Default)</p>
              </div>
              <p class="text-xs text-muted">
                Permission applies only to resources in the current entity context.
                Example: <code class="text-xs font-mono">user:create</code> can only create users in the current entity.
              </p>
            </div>
          </UCard>
          <UCard>
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-git-branch" class="w-4 h-4 text-green-500" />
                <p class="font-semibold text-sm">Tree Scope</p>
              </div>
              <p class="text-xs text-muted">
                Permission applies to resources in current entity AND all descendant entities.
                Example: <code class="text-xs font-mono">user:create_tree</code> can create users in current entity and all child entities.
              </p>
              <div class="bg-neutral-50 dark:bg-neutral-900 p-2 rounded text-xs font-mono mt-2">
                <div> Company</div>
                <div class="pl-3"> Engineering</div>
                <div class="pl-6"> Backend Team</div>
                <div class="pl-6"> Frontend Team</div>
              </div>
            </div>
          </UCard>
          <UCard>
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-globe" class="w-4 h-4 text-blue-500" />
                <p class="font-semibold text-sm">All Scope</p>
              </div>
              <p class="text-xs text-muted">
                Permission applies globally across all entities. Rarely used except for system-wide operations.
              </p>
            </div>
          </UCard>
        </div>
      </div>

      <USeparator />

      <!-- Best Practices -->
      <div class="space-y-3">
        <h3 class="text-lg font-semibold flex items-center gap-2">
          <UIcon name="i-lucide-check-circle" class="w-5 h-5 text-success" />
          Best Practices
        </h3>
        <ul class="text-sm text-muted space-y-2">
          <li class="flex items-start gap-2">
            <UIcon name="i-lucide-check" class="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
            <span>Use clear, descriptive names that indicate what the permission allows</span>
          </li>
          <li class="flex items-start gap-2">
            <UIcon name="i-lucide-check" class="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
            <span>Follow the resource:action naming convention consistently</span>
          </li>
          <li class="flex items-start gap-2">
            <UIcon name="i-lucide-check" class="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
            <span>Use tags to organize permissions by category (e.g., "user-management", "finance")</span>
          </li>
          <li class="flex items-start gap-2">
            <UIcon name="i-lucide-check" class="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
            <span>Mark dangerous permissions (delete, approve high-value items) with the "dangerous" tag</span>
          </li>
          <li class="flex items-start gap-2">
            <UIcon name="i-lucide-check" class="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
            <span>Use tree scope for hierarchical access control (managers over their departments)</span>
          </li>
          <li class="flex items-start gap-2">
            <UIcon name="i-lucide-check" class="w-4 h-4 text-success mt-0.5 flex-shrink-0" />
            <span>Keep system permissions minimal - only core functionality that should never be removed</span>
          </li>
        </ul>
      </div>

      <USeparator />

      <!-- System vs Custom -->
      <div class="space-y-3">
        <h3 class="text-lg font-semibold flex items-center gap-2">
          <UIcon name="i-lucide-lock" class="w-5 h-5 text-blue-500" />
          System vs Custom Permissions
        </h3>
        <div class="grid grid-cols-2 gap-4">
          <UCard>
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <UBadge color="primary" variant="subtle" size="xs">System</UBadge>
              </div>
              <ul class="text-xs text-muted space-y-1">
                <li>" Built-in permissions</li>
                <li>" Cannot be deleted</li>
                <li>" Core functionality</li>
                <li>" user:*, role:*, entity:*</li>
              </ul>
            </div>
          </UCard>
          <UCard>
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <UBadge color="secondary" variant="subtle" size="xs">Custom</UBadge>
              </div>
              <ul class="text-xs text-muted space-y-1">
                <li>" Application-specific</li>
                <li>" Can be created/deleted</li>
                <li>" Business logic</li>
                <li>" invoice:*, report:*, project:*</li>
              </ul>
            </div>
          </UCard>
        </div>
      </div>

      <USeparator />

      <!-- How Permissions are Used -->
      <div class="space-y-3">
        <h3 class="text-lg font-semibold flex items-center gap-2">
          <UIcon name="i-lucide-workflow" class="w-5 h-5 text-primary" />
          How Permissions Work
        </h3>
        <p class="text-sm text-muted">
          Permissions are assigned to <strong>roles</strong>, and roles are assigned to <strong>users</strong> in specific <strong>entity contexts</strong>.
        </p>
        <div class="bg-neutral-50 dark:bg-neutral-900 p-4 rounded space-y-2">
          <div class="flex items-center gap-2 text-sm">
            <UIcon name="i-lucide-user" class="w-4 h-4" />
            <span class="font-mono">User</span>
            <UIcon name="i-lucide-arrow-right" class="w-4 h-4 text-muted" />
            <span class="font-mono">has role</span>
            <UIcon name="i-lucide-arrow-right" class="w-4 h-4 text-muted" />
            <span class="font-mono">Role</span>
          </div>
          <div class="flex items-center gap-2 text-sm pl-8">
            <UIcon name="i-lucide-arrow-down" class="w-4 h-4 text-muted" />
          </div>
          <div class="flex items-center gap-2 text-sm pl-8">
            <span class="font-mono">Role contains</span>
            <UIcon name="i-lucide-arrow-right" class="w-4 h-4 text-muted" />
            <span class="font-mono">Permissions</span>
          </div>
        </div>
        <p class="text-xs text-muted">
          When a user tries to perform an action, the system checks if any of their roles (in the current entity context)
          contain the required permission.
        </p>
      </div>
      </div>
    </template>
  </USlideover>
</template>
