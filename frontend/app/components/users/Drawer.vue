<script setup lang="ts">
import type { User } from '~/types/auth.types'
import { UserStatus } from '~/types/auth.types'

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
const isSubmitting = ref(false)
const formRef = ref()

// Watch for mode changes
watch(
  () => props.mode,
  (newMode) => {
    currentMode.value = newMode
  }
)

// Handle drawer open/close
watch(
  () => open.value,
  async (isOpen) => {
    if (isOpen) {
      // Reset to original mode when opening
      currentMode.value = props.mode
      
      // Fetch fresh user data when opening in edit mode
      if (props.mode === 'edit' && props.user) {
        try {
          await usersStore.fetchUser(props.user.id)
        } catch (error) {
          console.error('Failed to fetch user details:', error)
        }
      }
    } else {
      // Reset to original mode when closing
      currentMode.value = props.mode
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

// Removed handleDelete function - now using status toggle in header

const handleCancel = () => {
  if (mode.value === 'create') {
    // For create mode, just close the drawer
    open.value = false
  } else {
    // For edit mode, revert back to view mode
    currentMode.value = 'view'
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
        <div class="flex items-center gap-4">
          <h3 class="text-xl font-bold">
            {{ title }}
          </h3>
          <div v-if="mode === 'view' && user && !user.is_system_user" class="flex items-center gap-2">
            <UBadge 
              :color="usersStore.getUserStatusColor(user)" 
              variant="subtle"
            >
              {{ usersStore.getUserStatusLabel(user) }}
            </UBadge>
          </div>
        </div>
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
        <!-- Form Content -->
        <div v-if="showForm">
          <UsersForm
            ref="formRef"
            :user="mode === 'edit' ? (usersStore.selectedUser || user) : null"
            :mode="mode"
            @submit="handleSubmit"
            @cancel="handleCancel"
          />
        </div>

        <!-- View Content with Tabs -->
        <div v-else-if="mode === 'view' && user">
          <!-- Use UTabs with slot-based content -->
          <UTabs :items="tabs" class="w-full">
            <template #content="{ item }">
              <!-- Profile Tab -->
              <div v-if="item.key === 'profile'">
                <UsersProfile
                  :user="user"
                  @edit="currentMode = 'edit'"
                />
              </div>

              <!-- Memberships Tab -->
              <div v-else-if="item.key === 'memberships'">
                <UsersMemberships :user="user" />
              </div>

              <!-- Security Tab -->
              <div v-else-if="item.key === 'security'">
                <UsersSecurity :user="user" />
              </div>

              <!-- Activity Tab -->
              <div v-else-if="item.key === 'activity'">
                <UsersActivity :user="user" />
              </div>
            </template>
          </UTabs>
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
        <UButton @click="handleCancel" color="neutral" variant="outline" class="justify-center flex-1"> 
          Cancel 
        </UButton>
        <UButton @click="submitForm" :loading="isSubmitting" color="primary" class="justify-center flex-1">
          {{ mode === "create" ? "Create User" : "Update User" }}
        </UButton>
      </div>
    </template>
  </UDrawer>
</template>