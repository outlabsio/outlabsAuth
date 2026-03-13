<script setup lang="ts">
import { useCreatePermissionMutation } from '~/queries/permissions'
import type { CreatePermissionData } from '~/api/permissions'

const open = defineModel<boolean>('open', { default: false })

const toast = useToast()

// Show help slideover
const showPermissionHelp = ref(false)

// Common resources and actions for quick selection
const commonResources = ['user', 'role', 'permission', 'entity', 'apikey', 'post', 'comment', 'invoice', 'report', 'project']
const commonActions = ['create', 'read', 'update', 'delete', 'list', 'approve', 'export', 'manage']

// Form state
const state = reactive({
  resource: '',
  action: '',
  scope: null as string | null,
  display_name: '',
  description: '',
  is_system: false,
  is_active: true,
  tags: [] as string[],
})

// Assembled permission name (resource:action with optional scope suffix)
const assembledName = computed(() => {
  if (!state.resource || !state.action) return ''
  const base = `${state.resource}:${state.action}`
  if (state.scope) return `${base}_${state.scope}`
  return base
})

// Auto-generate display name from resource + action
const autoDisplayName = computed(() => {
  if (!state.resource || !state.action) return ''
  const resource = state.resource.charAt(0).toUpperCase() + state.resource.slice(1)
  const action = state.action.charAt(0).toUpperCase() + state.action.slice(1)
  const scopeLabel = state.scope === 'tree' ? ' (Tree)' : state.scope === 'all' ? ' (All)' : ''
  return `${action} ${resource}s${scopeLabel}`
})

// Sync auto display name when user hasn't customized it
const displayNameManuallyEdited = ref(false)
watch(autoDisplayName, (newVal) => {
  if (!displayNameManuallyEdited.value) {
    state.display_name = newVal
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
  'system',
  'admin',
]

// Create mutation
const { mutate: createPermission, isLoading: isSubmitting } = useCreatePermissionMutation()

// Form validation
const canSubmit = computed(() => {
  return state.resource.trim() !== '' &&
         state.action.trim() !== '' &&
         state.display_name.trim() !== ''
})

// Submit handler
async function handleSubmit() {
  if (!canSubmit.value) return

  const permissionData: CreatePermissionData = {
    name: assembledName.value,
    display_name: state.display_name,
    description: state.description || undefined,
    is_system: state.is_system,
    is_active: state.is_active,
    tags: state.tags.length > 0 ? state.tags : undefined,
  }

  await createPermission(permissionData)
  closeModal()
}

// Close and reset
function closeModal() {
  open.value = false
  setTimeout(() => {
    Object.assign(state, {
      resource: '',
      action: '',
      scope: null,
      display_name: '',
      description: '',
      is_system: false,
      is_active: true,
      tags: [],
    })
    displayNameManuallyEdited.value = false
  }, 300)
}

function toggleTag(tag: string) {
  const idx = state.tags.indexOf(tag)
  if (idx >= 0) {
    state.tags.splice(idx, 1)
  } else {
    state.tags.push(tag)
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Create Permission"
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
      <div class="max-w-4xl mx-auto">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">

          <!-- Left Column: Builder + Preview -->
          <div class="space-y-6">
            <!-- Permission Builder -->
            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-wand-2" class="size-5 text-primary" />
                <h3 class="text-lg font-semibold">Permission Builder</h3>
              </div>

              <UFormField label="Resource" required>
                <UInputMenu
                  v-model="state.resource"
                  :items="commonResources.filter(r => r.includes(state.resource.toLowerCase()))"
                  placeholder="e.g. user, invoice, report"
                  icon="i-lucide-database"
                  class="w-full"
                />
                <template #description>The thing being accessed</template>
              </UFormField>

              <UFormField label="Action" required>
                <UInputMenu
                  v-model="state.action"
                  :items="commonActions.filter(a => a.includes(state.action.toLowerCase()))"
                  placeholder="e.g. create, read, delete"
                  icon="i-lucide-zap"
                  class="w-full"
                />
                <template #description>What you can do with it</template>
              </UFormField>

              <!-- Scope -->
              <div class="space-y-2">
                <label class="block text-sm font-medium">Scope</label>
                <div class="grid grid-cols-3 gap-3">
                  <!-- None -->
                  <button
                    type="button"
                    class="p-3 rounded-lg text-left transition-all ring ring-inset"
                    :class="!state.scope
                      ? 'ring-primary bg-primary/5'
                      : 'ring-accented hover:bg-elevated/50'"
                    @click="state.scope = null"
                  >
                    <div class="flex items-center gap-1.5 mb-2">
                      <UIcon name="i-lucide-box" class="size-4" :class="!state.scope ? 'text-primary' : 'text-muted'" />
                      <span class="text-sm font-semibold">None</span>
                    </div>
                    <div class="font-mono text-[10px] leading-relaxed space-y-px">
                      <div class="flex items-center gap-1">
                        <span class="size-1.5 rounded-full bg-primary inline-block" />
                        <span :class="!state.scope ? '' : 'text-muted'">Company</span>
                      </div>
                      <div class="flex items-center gap-1 pl-3">
                        <span class="size-1.5 rounded-full bg-muted inline-block" />
                        <span class="text-muted">Engineering</span>
                      </div>
                      <div class="flex items-center gap-1 pl-3">
                        <span class="size-1.5 rounded-full bg-muted inline-block" />
                        <span class="text-muted">Sales</span>
                      </div>
                    </div>
                    <p class="text-[10px] text-muted mt-2">This entity only</p>
                  </button>

                  <!-- Tree -->
                  <button
                    type="button"
                    class="p-3 rounded-lg text-left transition-all ring ring-inset"
                    :class="state.scope === 'tree'
                      ? 'ring-success bg-success/5'
                      : 'ring-accented hover:bg-elevated/50'"
                    @click="state.scope = 'tree'"
                  >
                    <div class="flex items-center gap-1.5 mb-2">
                      <UIcon name="i-lucide-git-branch" class="size-4" :class="state.scope === 'tree' ? 'text-success' : 'text-muted'" />
                      <span class="text-sm font-semibold">Tree</span>
                    </div>
                    <div class="font-mono text-[10px] leading-relaxed space-y-px">
                      <div class="flex items-center gap-1">
                        <span class="size-1.5 rounded-full bg-success inline-block" />
                        <span :class="state.scope === 'tree' ? 'text-success' : 'text-muted'">Company</span>
                      </div>
                      <div class="flex items-center gap-1 pl-3">
                        <span class="size-1.5 rounded-full bg-success inline-block" />
                        <span :class="state.scope === 'tree' ? 'text-success' : 'text-muted'">Engineering</span>
                      </div>
                      <div class="flex items-center gap-1 pl-3">
                        <span class="size-1.5 rounded-full bg-success inline-block" />
                        <span :class="state.scope === 'tree' ? 'text-success' : 'text-muted'">Sales</span>
                      </div>
                    </div>
                    <p class="text-[10px] text-muted mt-2">Entity + descendants</p>
                  </button>

                  <!-- All -->
                  <button
                    type="button"
                    class="p-3 rounded-lg text-left transition-all ring ring-inset"
                    :class="state.scope === 'all'
                      ? 'ring-info bg-info/5'
                      : 'ring-accented hover:bg-elevated/50'"
                    @click="state.scope = 'all'"
                  >
                    <div class="flex items-center gap-1.5 mb-2">
                      <UIcon name="i-lucide-globe" class="size-4" :class="state.scope === 'all' ? 'text-info' : 'text-muted'" />
                      <span class="text-sm font-semibold">All</span>
                    </div>
                    <div class="font-mono text-[10px] leading-relaxed space-y-px">
                      <div class="flex items-center gap-1">
                        <span class="size-1.5 rounded-full bg-info inline-block" />
                        <span :class="state.scope === 'all' ? 'text-info' : 'text-muted'">Company</span>
                      </div>
                      <div class="flex items-center gap-1">
                        <span class="size-1.5 rounded-full bg-info inline-block" />
                        <span :class="state.scope === 'all' ? 'text-info' : 'text-muted'">Other Org</span>
                      </div>
                      <div class="flex items-center gap-1">
                        <span class="size-1.5 rounded-full bg-info inline-block" />
                        <span :class="state.scope === 'all' ? 'text-info' : 'text-muted'">Partner Co</span>
                      </div>
                    </div>
                    <p class="text-[10px] text-muted mt-2">Every entity globally</p>
                  </button>
                </div>
              </div>
            </div>

            <!-- Live Preview -->
            <div
              class="flex items-center gap-3 p-4 rounded-lg ring ring-inset ring-accented"
              :class="assembledName ? 'bg-primary/5' : 'bg-elevated'"
            >
              <div class="p-2 rounded-lg" :class="assembledName ? 'bg-primary/10' : 'bg-elevated'">
                <UIcon name="i-lucide-key" class="size-5" :class="assembledName ? 'text-primary' : 'text-muted'" />
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-xs text-muted uppercase tracking-wide font-medium">Permission Name</p>
                <p class="text-lg font-mono font-semibold truncate" :class="assembledName ? '' : 'text-muted'">
                  {{ assembledName || 'resource:action' }}
                </p>
              </div>
              <UBadge v-if="state.scope === 'tree'" color="success" variant="subtle" size="sm">Tree</UBadge>
              <UBadge v-else-if="state.scope === 'all'" color="info" variant="subtle" size="sm">Global</UBadge>
            </div>
          </div>

          <!-- Right Column: Details + Settings + Tags -->
          <div class="space-y-6">
            <!-- Details -->
            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-info" class="size-5 text-primary" />
                <h3 class="text-lg font-semibold">Details</h3>
              </div>

              <UFormField label="Display Name" required>
                <UInput
                  v-model="state.display_name"
                  placeholder="Create Users"
                  icon="i-lucide-tag"
                  class="w-full"
                  @input="displayNameManuallyEdited = true"
                />
                <template #description>
                  <span v-if="!displayNameManuallyEdited && autoDisplayName" class="text-success">Auto-generated from resource + action</span>
                  <span v-else>Human-friendly name shown in the UI</span>
                </template>
              </UFormField>

              <UFormField label="Description" hint="Optional">
                <UTextarea
                  v-model="state.description"
                  placeholder="Describe what this permission allows..."
                  :rows="3"
                  class="w-full"
                />
              </UFormField>
            </div>

            <!-- Settings -->
            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-settings" class="size-5 text-primary" />
                <h3 class="text-lg font-semibold">Settings</h3>
              </div>

              <div class="space-y-3">
                <div class="flex items-center justify-between p-3 rounded-lg ring ring-inset ring-accented">
                  <div class="space-y-0.5">
                    <p class="text-sm font-medium">Active</p>
                    <p class="text-xs text-muted">
                      {{ state.is_active ? 'Will be checked during authorization' : 'Disabled — will be ignored' }}
                    </p>
                  </div>
                  <USwitch v-model="state.is_active" />
                </div>

                <div class="flex items-center justify-between p-3 rounded-lg ring ring-inset ring-accented">
                  <div class="space-y-0.5">
                    <p class="text-sm font-medium">System Permission</p>
                    <p class="text-xs text-muted">
                      {{ state.is_system ? 'Built-in — cannot be deleted' : 'Custom — can be managed freely' }}
                    </p>
                  </div>
                  <USwitch v-model="state.is_system" />
                </div>
              </div>
            </div>

            <!-- Tags -->
            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-tags" class="size-5 text-primary" />
                <h3 class="text-lg font-semibold">Tags</h3>
                <span class="text-xs text-muted">Optional</span>
              </div>

              <div class="flex flex-wrap gap-2">
                <button
                  v-for="tag in availableTags"
                  :key="tag"
                  type="button"
                  class="px-3 py-1.5 text-sm rounded-full transition-colors"
                  :class="state.tags.includes(tag)
                    ? 'bg-primary text-inverted'
                    : 'bg-elevated text-muted hover:text-default ring ring-inset ring-accented'"
                  @click="toggleTag(tag)"
                >
                  {{ tag }}
                </button>
              </div>
              <p v-if="state.tags.length > 0" class="text-xs text-muted">
                {{ state.tags.length }} tag(s) selected
              </p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-between items-center w-full">
        <div>
          <p v-if="!canSubmit && (state.resource || state.action)" class="text-sm text-error">
            <span v-if="!state.resource">Resource is required</span>
            <span v-else-if="!state.action">Action is required</span>
            <span v-else-if="!state.display_name">Display name is required</span>
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
            <UIcon name="i-lucide-shield-check" class="size-5 text-primary" />
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
            <UIcon name="i-lucide-code" class="size-5 text-primary" />
            Permission Format
          </h3>
          <p class="text-sm text-muted">
            All permissions follow the format: <code class="text-xs bg-elevated px-2 py-1 rounded font-mono">resource:action</code>
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
            <UIcon name="i-lucide-list" class="size-5 text-primary" />
            Common Examples
          </h3>
          <div class="space-y-2">
            <div class="p-3 rounded-lg bg-elevated">
              <code class="text-sm font-mono text-primary">user:create</code>
              <p class="text-xs text-muted mt-1">Allows creating new user accounts</p>
            </div>
            <div class="p-3 rounded-lg bg-elevated">
              <code class="text-sm font-mono text-primary">invoice:approve</code>
              <p class="text-xs text-muted mt-1">Allows approving invoices for payment</p>
            </div>
            <div class="p-3 rounded-lg bg-elevated">
              <code class="text-sm font-mono text-primary">entity:read_tree</code>
              <p class="text-xs text-muted mt-1">Allows viewing entity and all descendants in hierarchy</p>
            </div>
            <div class="p-3 rounded-lg bg-elevated">
              <code class="text-sm font-mono text-primary">*:*</code>
              <p class="text-xs text-muted mt-1">Wildcard: Grants all permissions (superuser)</p>
            </div>
          </div>
        </div>

        <USeparator />

        <!-- Scope Explanation -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold flex items-center gap-2">
            <UIcon name="i-lucide-layers" class="size-5 text-primary" />
            Permission Scopes
          </h3>
          <div class="space-y-2">
            <div class="p-3 rounded-lg bg-elevated">
              <p class="font-medium text-sm flex items-center gap-2">
                <UIcon name="i-lucide-circle" class="size-4" />
                None (Default)
              </p>
              <p class="text-xs text-muted mt-1">Permission applies only to resources in the current entity context.</p>
            </div>
            <div class="p-3 rounded-lg bg-elevated">
              <p class="font-medium text-sm flex items-center gap-2">
                <UIcon name="i-lucide-git-branch" class="size-4 text-success" />
                Tree Scope
              </p>
              <p class="text-xs text-muted mt-1">Permission applies to resources in current entity AND all descendant entities.</p>
            </div>
            <div class="p-3 rounded-lg bg-elevated">
              <p class="font-medium text-sm flex items-center gap-2">
                <UIcon name="i-lucide-globe" class="size-4 text-info" />
                All Scope
              </p>
              <p class="text-xs text-muted mt-1">Permission applies globally across all entities. Rarely used.</p>
            </div>
          </div>
        </div>

        <USeparator />

        <!-- How Permissions Work -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold flex items-center gap-2">
            <UIcon name="i-lucide-workflow" class="size-5 text-primary" />
            How Permissions Work
          </h3>
          <p class="text-sm text-muted">
            Permissions are assigned to <strong>roles</strong>, and roles are assigned to <strong>users</strong> in specific <strong>entity contexts</strong>.
          </p>
          <div class="bg-elevated p-4 rounded-lg space-y-2">
            <div class="flex items-center gap-2 text-sm">
              <UIcon name="i-lucide-user" class="size-4" />
              <span class="font-mono">User</span>
              <UIcon name="i-lucide-arrow-right" class="size-4 text-muted" />
              <span class="font-mono">has Role</span>
              <UIcon name="i-lucide-arrow-right" class="size-4 text-muted" />
              <span class="font-mono">contains Permissions</span>
            </div>
          </div>
        </div>

        <USeparator />

        <!-- Best Practices -->
        <div class="space-y-3">
          <h3 class="text-lg font-semibold flex items-center gap-2">
            <UIcon name="i-lucide-check-circle" class="size-5 text-success" />
            Best Practices
          </h3>
          <ul class="text-sm text-muted space-y-2">
            <li class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="size-4 text-success mt-0.5 flex-shrink-0" />
              <span>Use clear, descriptive names that indicate what the permission allows</span>
            </li>
            <li class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="size-4 text-success mt-0.5 flex-shrink-0" />
              <span>Follow the resource:action naming convention consistently</span>
            </li>
            <li class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="size-4 text-success mt-0.5 flex-shrink-0" />
              <span>Use tags to organize permissions by category</span>
            </li>
            <li class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="size-4 text-success mt-0.5 flex-shrink-0" />
              <span>Use tree scope for hierarchical access control</span>
            </li>
            <li class="flex items-start gap-2">
              <UIcon name="i-lucide-check" class="size-4 text-success mt-0.5 flex-shrink-0" />
              <span>Grant minimum permissions needed (least privilege)</span>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </USlideover>
</template>
