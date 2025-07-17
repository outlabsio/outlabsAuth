<script setup lang="ts">
import type { Role } from '~/types/auth.types'

const props = defineProps<{
  role: Role | null
  mode: 'view' | 'create' | 'edit'
  defaultEntityId?: string | null
}>()

const emit = defineEmits<{
  created: [role: Role]
  updated: [role: Role]
  deleted: []
}>()

// State
const open = defineModel<boolean>("open", { default: false })
const currentMode = ref(props.mode)

// Stores
const rolesStore = useRolesStore()
const toast = useToast()

// Other state
const isDeleting = ref(false)
const isSubmitting = ref(false)
const showDeleteConfirm = ref(false)
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
      const newRole = await rolesStore.createRole(data)
      toast.add({
        title: "Success",
        description: "Role created successfully",
        color: "success"
      })
      emit('created', newRole)
      open.value = false
    } else if (mode.value === 'edit' && props.role) {
      const updatedRole = await rolesStore.updateRole(props.role.id, data)
      toast.add({
        title: "Success",
        description: "Role updated successfully",
        color: "success"
      })
      emit('updated', updatedRole)
      open.value = false
    }
  } catch (error: any) {
    console.error('Failed to save role:', error)
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || `Failed to ${mode.value} role`,
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

async function handleDelete() {
  if (!props.role) return
  
  isDeleting.value = true
  try {
    await rolesStore.deleteRole(props.role.id)
    toast.add({
      title: "Success",
      description: "Role deleted successfully",
      color: "success"
    })
    emit('deleted')
    open.value = false
  } catch (error: any) {
    console.error('Failed to delete role:', error)
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || 'Failed to delete role',
      color: "error"
    })
  } finally {
    isDeleting.value = false
    showDeleteConfirm.value = false
  }
}

// Computed
const title = computed(() => {
  switch (mode.value) {
    case 'create':
      return 'Create New Role'
    case 'edit':
      return 'Edit Role'
    case 'view':
      return 'Role Details'
    default:
      return 'Role'
  }
})

const showForm = computed(() => mode.value === 'create' || mode.value === 'edit')
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
          <RolesForm
            ref="formRef"
            :mode="mode"
            :role="role"
            :default-entity-id="defaultEntityId"
            @submit="handleSubmit"
            @cancel="open = false"
            @delete="showDeleteConfirm = true"
          />
        </div>

        <!-- View Content -->
        <div v-else-if="mode === 'view' && role" class="space-y-6">
            <!-- Basic Information -->
            <div>
              <h3 class="text-lg font-semibold mb-4">Basic Information</h3>
              <div class="space-y-4">
                <div>
                  <label class="text-sm font-medium text-muted-foreground">System Name</label>
                  <p class="mt-1 font-mono text-sm bg-elevated px-2 py-1 rounded">{{ role.name }}</p>
                </div>
                <div>
                  <label class="text-sm font-medium text-muted-foreground">Display Name</label>
                  <p class="mt-1">{{ role.display_name }}</p>
                </div>
                <div v-if="role.description">
                  <label class="text-sm font-medium text-muted-foreground">Description</label>
                  <p class="mt-1 text-sm">{{ role.description }}</p>
                </div>
              </div>
            </div>

            <!-- Scope Information -->
            <div>
              <h3 class="text-lg font-semibold mb-4">Scope</h3>
              <div class="space-y-4">
                <div>
                  <label class="text-sm font-medium text-muted-foreground">Type</label>
                  <p class="mt-1">
                    <UBadge :label="role.is_global ? 'Global' : 'Entity'" :color="role.is_global ? 'primary' : 'neutral'" variant="subtle" />
                  </p>
                </div>
                <div v-if="role.entity_name">
                  <label class="text-sm font-medium text-muted-foreground">Owner Entity</label>
                  <p class="mt-1">{{ role.entity_name }}</p>
                </div>
                <div v-if="role.assignable_at_types && role.assignable_at_types.length > 0">
                  <label class="text-sm font-medium text-muted-foreground">Can Be Assigned At</label>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <UBadge 
                      v-for="type in role.assignable_at_types" 
                      :key="type"
                      :label="type"
                      color="primary"
                      variant="subtle"
                      size="sm"
                    />
                  </div>
                </div>
              </div>
            </div>

            <!-- Permissions -->
            <div>
              <h3 class="text-lg font-semibold mb-4">Permissions ({{ role.permissions.length }})</h3>
              <div class="space-y-2 max-h-64 overflow-y-auto">
                <div v-for="permission in role.permissions" :key="permission" class="flex items-center gap-2 py-1">
                  <UIcon name="i-lucide-check" class="h-4 w-4 text-success" />
                  <span class="font-mono text-sm">{{ permission }}</span>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex gap-2 pt-4">
              <UButton
                v-if="!role.is_system_role"
                icon="i-lucide-pencil"
                @click="currentMode = 'edit'"
              >
                Edit Role
              </UButton>
              <UButton
                v-if="!role.is_system_role"
                icon="i-lucide-trash"
                color="error"
                variant="outline"
                @click="showDeleteConfirm = true"
              >
                Delete
              </UButton>
            </div>

            <!-- Delete Confirmation -->
            <UAlert v-if="showDeleteConfirm" color="error" icon="i-lucide-alert-triangle" class="mt-4">
              <template #title>Delete Role</template>
              <template #description>
                <p class="mb-4">Are you sure you want to delete this role? This action cannot be undone.</p>
                <div class="flex gap-2">
                  <UButton
                    size="sm"
                    color="error"
                    :loading="isDeleting"
                    @click="handleDelete"
                  >
                    Yes, Delete
                  </UButton>
                  <UButton
                    size="sm"
                    variant="outline"
                    @click="showDeleteConfirm = false"
                  >
                    Cancel
                  </UButton>
                </div>
              </template>
            </UAlert>
        </div>
      </div>
    </template>

    <!-- Footer for Create/Edit Mode -->
    <template v-if="mode === 'create' || mode === 'edit'" #footer>
      <div class="flex flex-col sm:flex-row gap-3 w-full">
        <UButton @click="open = false" color="neutral" variant="outline" class="justify-center flex-1"> Cancel </UButton>
        <UButton @click="submitForm" :loading="isSubmitting" color="primary" class="justify-center flex-1">
          {{ mode === "create" ? "Create Role" : "Update Role" }}
        </UButton>
      </div>
    </template>
  </UDrawer>
</template>