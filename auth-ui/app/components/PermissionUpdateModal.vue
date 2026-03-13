<script setup lang="ts">
import { useUpdatePermissionMutation } from '~/queries/permissions'
import type { UpdatePermissionData } from '~/api/permissions'
import type { Permission } from '~/types/role'

const open = defineModel<boolean>('open', { default: false })

// Permission to edit (passed from parent)
const props = defineProps<{
  permission: Permission | null
}>()

const toast = useToast()

// Show help slideover
const showPermissionHelp = ref(false)

// Form state
const state = reactive({
  display_name: '',
  description: '',
  is_active: true,
  tags: [] as string[],
  metadata: {} as Record<string, any>
})

// Update mutation
const { mutate: updatePermission, isLoading: isSubmitting } = useUpdatePermissionMutation()

// Initialize form when permission changes
watch(() => props.permission, (permission) => {
  if (permission) {
    state.display_name = permission.display_name
    state.description = permission.description || ''
    state.is_active = permission.is_active
    state.tags = permission.tags || []
    state.metadata = permission.metadata || {}
  }
}, { immediate: true })

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

// Form validation
const canSubmit = computed(() => {
  return state.display_name.trim() !== ''
})

// Validation message
const validationMessage = computed(() => {
  if (!state.display_name.trim()) return 'Display name is required'
  return ''
})

// Submit handler
async function handleSubmit() {
  if (!canSubmit.value || !props.permission) {
    toast.add({
      title: 'Validation Error',
      description: validationMessage.value || 'No permission selected',
      color: 'error'
    })
    return
  }

  // Prepare data for API
  const permissionData: UpdatePermissionData = {
    display_name: state.display_name,
    description: state.description || undefined,
    is_active: state.is_active,
    tags: state.tags.length > 0 ? state.tags : undefined,
    metadata: Object.keys(state.metadata).length > 0 ? state.metadata : undefined
  }

  console.log('[UPDATE PERMISSION] Sending data:', {
    id: props.permission.id,
    data: permissionData
  })

  // Call mutation - toasts handled by mutation callbacks
  await updatePermission({ id: props.permission.id, data: permissionData })

  // Close modal on success
  closeModal()
}

// Close and reset
function closeModal() {
  open.value = false
}

// Toggle tag
function toggleTag(tag: string) {
  const index = state.tags.indexOf(tag)
  if (index > -1) {
    state.tags.splice(index, 1)
  } else {
    state.tags.push(tag)
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Update Permission"
    description="Modify permission settings and metadata"
    fullscreen
  >
    <template #description>
      <div class="flex items-center justify-between w-full">
        <p class="text-sm text-muted">Modify permission settings and metadata</p>
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
      <!-- Body with two columns -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Left Column: Basic Information -->
        <div class="space-y-4">
          <div>
            <h3 class="text-sm font-semibold text-foreground mb-4">Permission Information</h3>

            <!-- Permission Name (Read-only) -->
            <div class="mb-4">
              <div class="flex items-center justify-between mb-1.5">
                <label class="text-sm font-medium text-foreground">Permission Name</label>
                <UTooltip text="Permission name cannot be changed">
                  <UButton icon="i-lucide-info" color="neutral" variant="ghost" size="xs" />
                </UTooltip>
              </div>
              <UInput
                :model-value="permission?.name || ''"
                placeholder="resource:action"
                disabled
                readonly
              />
              <p class="mt-1.5 text-xs text-muted">
                Resource: <code class="px-1 py-0.5 bg-muted rounded">{{ permission?.resource }}</code>
                &nbsp;&nbsp;
                Action: <code class="px-1 py-0.5 bg-muted rounded">{{ permission?.action }}</code>
              </p>
            </div>

            <!-- Display Name -->
            <div class="mb-4">
              <div class="flex items-center justify-between mb-1.5">
                <label class="text-sm font-medium text-foreground">Display Name</label>
                <UTooltip text="Human-readable name shown in the UI">
                  <UButton icon="i-lucide-info" color="neutral" variant="ghost" size="xs" />
                </UTooltip>
              </div>
              <UInput
                v-model="state.display_name"
                placeholder="Create Users"
              />
            </div>

            <!-- Description -->
            <div>
              <div class="flex items-center justify-between mb-1.5">
                <label class="text-sm font-medium text-foreground">Description</label>
                <UTooltip text="Detailed description of what this permission allows">
                  <UButton icon="i-lucide-info" color="neutral" variant="ghost" size="xs" />
                </UTooltip>
              </div>
              <UTextarea
                v-model="state.description"
                placeholder="Describe what this permission allows..."
                :rows="3"
              />
            </div>
          </div>
        </div>

        <!-- Right Column: Settings & Tags -->
        <div class="space-y-4">
          <!-- Settings -->
          <div>
            <h3 class="text-sm font-semibold text-foreground mb-4">Settings</h3>

            <div class="space-y-3">
              <!-- System Permission Badge (Read-only) -->
              <div class="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                <div class="flex items-center gap-2">
                  <UIcon name="i-lucide-shield-check" class="w-4 h-4 text-muted" />
                  <span class="text-sm font-medium text-foreground">System Permission</span>
                  <UTooltip text="System permissions cannot be deleted">
                    <UButton icon="i-lucide-info" color="neutral" variant="ghost" size="xs" />
                  </UTooltip>
                </div>
                <UBadge v-if="permission?.is_system" color="info" variant="subtle">System</UBadge>
                <UBadge v-else color="neutral" variant="subtle">Custom</UBadge>
              </div>

              <!-- Active Toggle -->
              <div class="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                <div>
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-foreground">Active</span>
                    <UTooltip text="Active permissions are enforced by the system">
                      <UButton icon="i-lucide-info" color="neutral" variant="ghost" size="xs" />
                    </UTooltip>
                  </div>
                  <p class="text-xs text-muted mt-1">
                    {{ state.is_active ? 'Permission is active and will be checked' : 'Permission is inactive' }}
                  </p>
                </div>
                <USwitch v-model="state.is_active" />
              </div>
            </div>
          </div>

          <!-- Tags & Categories -->
          <div>
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-foreground">Tags & Categories</h3>
              <UTooltip text="Tags help organize and filter permissions">
                <UButton icon="i-lucide-info" color="neutral" variant="ghost" size="xs" />
              </UTooltip>
            </div>

            <div>
              <p class="text-xs text-muted mb-2">Select tags to categorize this permission</p>
              <div class="flex flex-wrap gap-2">
                <UBadge
                  v-for="tag in availableTags"
                  :key="tag"
                  :color="state.tags.includes(tag) ? 'primary' : 'neutral'"
                  :variant="state.tags.includes(tag) ? 'solid' : 'outline'"
                  class="cursor-pointer"
                  @click="toggleTag(tag)"
                >
                  {{ tag }}
                </UBadge>
              </div>
            </div>
          </div>

          <!-- Help Link -->
          <UButton
            icon="i-lucide-book-open"
            color="neutral"
            variant="outline"
            block
            @click="showPermissionHelp = true"
          >
            Learn about Permissions
          </UButton>
        </div>
      </div>

    </template>

    <!-- Footer -->
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
            label="Update Permission"
            icon="i-lucide-shield-check"
            :loading="isSubmitting"
            :disabled="!canSubmit"
            @click="handleSubmit"
          />
        </div>
      </div>
    </template>
  </UModal>

  <!-- Help Slideover (placeholder) -->
  <!-- <PermissionHelpSlideover v-model:open="showPermissionHelp" /> -->
</template>
