<script setup lang="ts">
import type { User } from '~/types/auth.types'

const props = defineProps<{
  user: User | null
  mode: 'view' | 'create' | 'edit'
}>()

const emit = defineEmits<{
  created: []
  updated: []
  deleted: []
}>()

// State
const open = defineModel<boolean>("open", { default: false })
const currentMode = ref(props.mode)

// Store
const usersStore = useUsersStore()
const contextStore = useContextStore()
const toast = useToast()

// State
const activeTab = ref('profile')
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

// Fetch fresh user data when opening in edit mode
watch(
  () => open.value,
  async (isOpen) => {
    if (isOpen && props.mode === 'edit' && props.user) {
      // Fetch fresh user data to ensure we have the latest roles
      try {
        await usersStore.fetchUser(props.user.id)
      } catch (error) {
        console.error('Failed to fetch user details:', error)
      }
    }
  }
)

// Computed
const mode = computed(() => currentMode.value)

const title = computed(() => {
  switch (mode.value) {
    case 'create':
      return 'Create User'
    case 'edit':
      return 'Edit User'
    default:
      return props.user ? usersStore.getUserDisplayName(props.user) : 'User Details'
  }
})

const tabs = computed(() => {
  if (mode.value === 'create') {
    return []
  }
  
  return [
    {
      key: 'profile',
      label: 'Profile',
      icon: 'i-lucide-user'
    },
    {
      key: 'memberships',
      label: 'Memberships',
      icon: 'i-lucide-building'
    },
    {
      key: 'security',
      label: 'Security',
      icon: 'i-lucide-shield'
    },
    {
      key: 'activity',
      label: 'Activity',
      icon: 'i-lucide-activity'
    }
  ]
})

// Methods
async function handleSubmit(data: any) {
  isSubmitting.value = true
  try {
    if (mode.value === 'create') {
      await usersStore.createUser(data)
      toast.add({
        title: "Success",
        description: "User created successfully",
        color: "success"
      })
      emit('created')
      open.value = false
    } else if (mode.value === 'edit' && props.user) {
      await usersStore.updateUser(props.user.id, data)
      toast.add({
        title: "Success",
        description: "User updated successfully",
        color: "success"
      })
      emit('updated')
      open.value = false
    }
  } catch (error: any) {
    console.error('Failed to save user:', error)
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || `Failed to ${mode.value} user`,
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
  if (!props.user || !confirm(`Are you sure you want to deactivate ${usersStore.getUserDisplayName(props.user)}?`)) return
  
  isDeleting.value = true
  try {
    await usersStore.deleteUser(props.user.id, false)
    toast.add({
      title: "Success",
      description: "User deactivated successfully",
      color: "success"
    })
    emit('deleted')
    open.value = false
  } catch (error: any) {
    console.error('Failed to deactivate user:', error)
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || 'Failed to deactivate user',
      color: "error"
    })
  } finally {
    isDeleting.value = false
    showDeleteConfirm.value = false
  }
}

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
        <div v-if="mode === 'view'" class="flex items-center gap-2">
          <UButton
            variant="ghost"
            icon="i-lucide-edit"
            size="sm"
            @click="currentMode = 'edit'"
          >
            Edit
          </UButton>
        </div>
      </div>
    </template>

    <!-- Body -->
    <template #body>
      <div class="p-4">
        <!-- Tabs for view mode -->
        <UTabs 
          v-if="mode === 'view' && user" 
          v-model="activeTab" 
          :items="tabs"
          class="mb-6"
        />

        <!-- Form Content -->
        <div v-if="showForm">
          <UsersForm
            ref="formRef"
            :user="mode === 'edit' ? (usersStore.selectedUser || user) : null"
            :mode="mode"
            @submit="handleSubmit"
            @cancel="open = false"
          />
        </div>

        <!-- View Content -->
        <div v-else-if="mode === 'view' && user">
          <!-- Profile Tab -->
          <div v-if="activeTab === 'profile'">
            <UsersProfile
              :user="user"
              @edit="currentMode = 'edit'"
            />
          </div>

          <!-- Memberships Tab -->
          <div v-else-if="activeTab === 'memberships'">
            <UsersMemberships :user="user" />
          </div>

          <!-- Security Tab -->
          <div v-else-if="activeTab === 'security'">
            <UsersSecurity :user="user" />
          </div>

          <!-- Activity Tab -->
          <div v-else-if="activeTab === 'activity'">
            <UsersActivity :user="user" />
          </div>

          <!-- Delete Section -->
          <div v-if="!user.is_system_user" class="mt-8 border-t pt-6">
            <div v-if="!showDeleteConfirm">
              <UButton
                color="red"
                variant="soft"
                icon="i-lucide-trash"
                @click="showDeleteConfirm = true"
              >
                Deactivate User
              </UButton>
            </div>

            <!-- Delete Confirmation -->
            <UAlert v-else color="error" icon="i-lucide-alert-triangle">
              <template #title>Deactivate User</template>
              <template #description>
                <p class="mb-4">Are you sure you want to deactivate this user? They will lose access to the system.</p>
                <div class="flex gap-2">
                  <UButton
                    size="sm"
                    color="error"
                    :loading="isDeleting"
                    @click="handleDelete"
                  >
                    Yes, Deactivate
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

        <!-- Loading State -->
        <div v-else class="flex items-center justify-center h-64">
          <UIcon name="i-lucide-loader-2" class="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    </template>

    <!-- Footer for Create/Edit Mode -->
    <template v-if="mode === 'create' || mode === 'edit'" #footer>
      <div class="flex flex-col sm:flex-row gap-3 w-full">
        <UButton @click="open = false" color="neutral" variant="outline" class="justify-center flex-1"> 
          Cancel 
        </UButton>
        <UButton @click="submitForm" :loading="isSubmitting" color="primary" class="justify-center flex-1">
          {{ mode === "create" ? "Create User" : "Update User" }}
        </UButton>
      </div>
    </template>
  </UDrawer>
</template>