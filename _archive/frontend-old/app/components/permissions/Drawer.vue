<script setup lang="ts">
import type { Permission } from '~/types/auth.types'

const props = defineProps<{
  permission: Permission | null
  mode: 'view' | 'create' | 'edit'
}>()

const emit = defineEmits<{
  created: [permission: Permission]
  updated: [permission: Permission]
  deleted: []
}>()

// State
const open = defineModel<boolean>("open", { default: false })
const currentMode = ref(props.mode)

// Stores
const permissionsStore = usePermissionsStore()
const contextStore = useContextStore()
const toast = useToast()

// Other state
const isDeleting = ref(false)
const isSubmitting = ref(false)
const showDeleteDialog = ref(false)
const formRef = ref()

// Watch for mode changes
watch(
  () => props.mode,
  (newMode) => {
    currentMode.value = newMode
  }
)

// Computed
const mode = computed(() => currentMode.value)

// Methods
async function handleSubmit(data: any) {
  isSubmitting.value = true
  try {
    if (mode.value === 'create') {
      const newPermission = await permissionsStore.createPermission(data)
      toast.add({
        title: "Success",
        description: "Permission created successfully",
        color: "success"
      })
      emit('created', newPermission)
      open.value = false
    } else if (mode.value === 'edit' && props.permission) {
      const updatedPermission = await permissionsStore.updatePermission(props.permission.id!, data)
      toast.add({
        title: "Success",
        description: "Permission updated successfully",
        color: "success"
      })
      emit('updated', updatedPermission)
      open.value = false
    }
  } catch (error: any) {
    console.error('Failed to save permission:', error)
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || `Failed to ${mode.value} permission`,
      color: "error"
    })
  } finally {
    isSubmitting.value = false
  }
}

const submitForm = () => {
  // Trigger form submission
  if (formRef.value) {
    formRef.value.$el.dispatchEvent(new Event("submit", { bubbles: true }))
  }
}

const confirmDelete = () => {
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!props.permission || !props.permission.id) return
  
  isDeleting.value = true
  try {
    await permissionsStore.deletePermission(props.permission.id)
    toast.add({
      title: "Success",
      description: "Permission deleted successfully",
      color: "success"
    })
    emit('deleted')
    open.value = false
  } catch (error: any) {
    console.error('Failed to delete permission:', error)
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || 'Failed to delete permission',
      color: "error"
    })
  } finally {
    isDeleting.value = false
    showDeleteDialog.value = false
  }
}

// Computed
const title = computed(() => {
  switch (mode.value) {
    case 'create':
      return 'Create New Permission'
    case 'edit':
      return 'Edit Permission'
    case 'view':
      return 'Permission Details'
    default:
      return 'Permission'
  }
})

const showForm = computed(() => mode.value === 'create' || mode.value === 'edit')

// Can edit check
const canEdit = computed(() => {
  if (!props.permission) return false
  // Cannot edit system permissions
  if (props.permission.is_system) return false
  // In entity context, can only edit permissions created in that context
  if (!contextStore.isSystemContext && props.permission.entity_id !== contextStore.selectedOrganization?.id) {
    return false
  }
  return true
})
</script>

<template>
  <UDrawer
    v-model:open="open"
    direction="right"
    :ui="{
      content: 'w-full max-w-2xl',
      header: 'sticky top-0 z-10',
      body: 'overflow-y-auto',
    }"
  >
    <!-- Header -->
    <template #header>
      <div class="flex justify-between items-center w-full">
        <h3 class="text-xl font-bold">
          {{ title }}
        </h3>
      </div>
    </template>

    <!-- Body -->
    <template #body>
      <div class="p-4">
        <!-- Form Content -->
        <div v-if="showForm">
          <PermissionsForm
            ref="formRef"
            :mode="mode"
            :permission="permission"
            @submit="handleSubmit"
            @cancel="open = false"
            @delete="confirmDelete"
          />
        </div>

        <!-- View Content -->
        <div v-else-if="mode === 'view' && permission" class="space-y-6">
          <!-- Basic Information -->
          <div>
            <h3 class="text-lg font-semibold mb-4">Basic Information</h3>
            <div class="space-y-4">
              <div>
                <label class="text-sm font-medium text-muted-foreground">Permission Name</label>
                <p class="mt-1 font-mono text-sm bg-elevated px-2 py-1 rounded">{{ permission.name }}</p>
              </div>
              <div>
                <label class="text-sm font-medium text-muted-foreground">Display Name</label>
                <p class="mt-1">{{ permission.display_name }}</p>
              </div>
              <div v-if="permission.description">
                <label class="text-sm font-medium text-muted-foreground">Description</label>
                <p class="mt-1 text-sm">{{ permission.description }}</p>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="text-sm font-medium text-muted-foreground">Resource</label>
                  <p class="mt-1">{{ permission.resource }}</p>
                </div>
                <div>
                  <label class="text-sm font-medium text-muted-foreground">Action</label>
                  <p class="mt-1">{{ permission.action }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Properties -->
          <div>
            <h3 class="text-lg font-semibold mb-4">Properties</h3>
            <div class="space-y-4">
              <div class="flex items-center gap-4">
                <div>
                  <label class="text-sm font-medium text-muted-foreground">Type</label>
                  <p class="mt-1">
                    <UBadge :label="permission.is_system ? 'System' : 'Custom'" :color="permission.is_system ? 'blue' : 'green'" variant="subtle" />
                  </p>
                </div>
                <div>
                  <label class="text-sm font-medium text-muted-foreground">Status</label>
                  <p class="mt-1">
                    <UBadge :label="permission.is_active ? 'Active' : 'Inactive'" :color="permission.is_active ? 'success' : 'neutral'" variant="subtle" />
                  </p>
                </div>
              </div>
              <div v-if="permission.entity_id">
                <label class="text-sm font-medium text-muted-foreground">Entity Scope</label>
                <p class="mt-1">{{ permission.entity_id }}</p>
              </div>
              <div v-if="permission.tags && permission.tags.length > 0">
                <label class="text-sm font-medium text-muted-foreground">Tags</label>
                <div class="mt-2 flex flex-wrap gap-2">
                  <UBadge 
                    v-for="tag in permission.tags" 
                    :key="tag"
                    :label="tag"
                    color="neutral"
                    variant="subtle"
                    size="sm"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Access Conditions -->
          <div v-if="permission.conditions && permission.conditions.length > 0">
            <h3 class="text-lg font-semibold mb-4">Access Conditions ({{ permission.conditions.length }})</h3>
            <div class="space-y-3">
              <UCard v-for="(condition, index) in permission.conditions" :key="index" class="p-4">
                <div class="space-y-2">
                  <div class="flex items-center gap-2">
                    <UIcon name="i-lucide-filter" class="h-4 w-4 text-primary" />
                    <span class="font-medium">Condition {{ index + 1 }}</span>
                  </div>
                  <div class="grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <span class="text-muted-foreground">Attribute:</span>
                      <p class="font-mono">{{ condition.attribute }}</p>
                    </div>
                    <div>
                      <span class="text-muted-foreground">Operator:</span>
                      <p>{{ condition.operator }}</p>
                    </div>
                    <div>
                      <span class="text-muted-foreground">Value:</span>
                      <p class="font-mono">{{ JSON.stringify(condition.value) }}</p>
                    </div>
                  </div>
                </div>
              </UCard>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 pt-4">
            <UButton
              v-if="canEdit"
              icon="i-lucide-pencil"
              @click="currentMode = 'edit'"
            >
              Edit Permission
            </UButton>
            <UButton
              v-if="canEdit"
              icon="i-lucide-trash"
              color="error"
              variant="outline"
              @click="confirmDelete"
            >
              Delete
            </UButton>
          </div>
        </div>
      </div>
    </template>

    <!-- Footer for Create/Edit Mode -->
    <template v-if="mode === 'create' || mode === 'edit'" #footer>
      <div class="flex flex-col sm:flex-row gap-3 w-full">
        <UButton @click="open = false" color="neutral" variant="outline" class="justify-center flex-1"> Cancel </UButton>
        <UButton @click="submitForm" :loading="isSubmitting" color="primary" class="justify-center flex-1">
          {{ mode === "create" ? "Create Permission" : "Update Permission" }}
        </UButton>
      </div>
    </template>
  </UDrawer>

  <!-- Delete Confirmation Modal -->
  <UModal v-model:open="showDeleteDialog">
    <template #header>
      <h3 class="text-lg font-semibold">Delete Permission</h3>
    </template>
    
    <template #body>
      <div class="space-y-4">
        <p class="text-sm">
          Are you sure you want to delete the permission
          <span class="font-semibold">"{{ permission?.display_name }}"</span>?
        </p>

        <UAlert color="error" variant="subtle" icon="i-lucide-alert-triangle">
          <template #title>This action cannot be undone</template>
          <template #description>
            <p class="text-sm">Deleting this permission will remove it from all roles that currently have it assigned.</p>
          </template>
        </UAlert>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-3">
        <UButton 
          color="neutral" 
          variant="outline" 
          @click="showDeleteDialog = false"
        >
          Cancel
        </UButton>
        <UButton 
          color="error" 
          :loading="isDeleting"
          @click="handleDelete"
        >
          Delete Permission
        </UButton>
      </div>
    </template>
  </UModal>
</template>