<script setup lang="ts">
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

// Auto-parse permission name
watch(() => state.name, (newName) => {
  if (newName && newName.includes(':')) {
    const parts = newName.split(':')
    if (parts.length >= 2) {
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
const isSubmitting = ref(false)

async function handleSubmit() {
  if (!canSubmit.value) {
    toast.add({
      title: 'Validation Error',
      description: validationMessage.value,
      color: 'error'
    })
    return
  }

  isSubmitting.value = true
  try {
    // In mock mode, just simulate success
    await new Promise(resolve => setTimeout(resolve, 500))

    toast.add({
      title: 'Permission created',
      description: `Permission "${state.name}" has been created successfully`,
      color: 'success'
    })

    closeModal()
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.message || 'Failed to create permission',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
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
              color="blue"
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
