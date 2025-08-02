<template>
  <UModal v-model:open="isOpen" :title="`Add Member to ${entityName}`" :close-icon="'i-lucide-x'">
    <template #body>

      <UForm 
        :schema="schema" 
        :state="state" 
        @submit="onSubmit"
        class="space-y-4"
      >
        <!-- User Selection -->
        <UFormField name="user_id" label="User" required>
          <div class="space-y-2">
            <UInput
              v-model="userSearchQuery"
              placeholder="Search users by name or email..."
              icon="i-lucide-search"
              :loading="isLoadingUsers"
              @input="debouncedSearchUsers"
            />
            <USelect
              v-model="state.user_id"
              :items="availableUsers"
              placeholder="Select a user from search results"
              :disabled="availableUsers.length === 0"
            >
              <template #label>
                {{ selectedUserLabel }}
              </template>
            </USelect>
          </div>
        </UFormField>

        <!-- Role Selection -->
        <UFormField name="roles" label="Roles" required>
          <div class="space-y-3">
            <!-- Assigned Roles -->
            <div v-if="state.role_ids.length > 0" class="space-y-2">
              <div class="flex flex-wrap gap-2">
                <UBadge 
                  v-for="roleId in state.role_ids" 
                  :key="roleId"
                  size="lg"
                  variant="subtle"
                  class="pr-1"
                >
                  <span class="mr-1">{{ getRoleLabel(roleId) }}</span>
                  <UButton 
                    icon="i-lucide-x" 
                    variant="ghost" 
                    size="2xs"
                    :padded="false"
                    @click="removeRole(roleId)"
                  />
                </UBadge>
              </div>
            </div>
            
            <!-- Role Search and Add -->
            <div ref="roleDropdownRef" class="relative">
              <UInput
                v-model="roleSearchQuery"
                placeholder="Search roles to add..."
                icon="i-lucide-search"
                :loading="isLoadingRoles"
                @focus="showRoleDropdown = true"
                @input="showRoleDropdown = true"
              />
              
              <!-- Available Roles Dropdown -->
              <div 
                v-if="showRoleDropdown && filteredAvailableRoles.length > 0"
                class="absolute z-10 w-full mt-1 bg-background border border-border rounded-lg shadow-lg max-h-60 overflow-y-auto"
              >
                <div class="p-1">
                  <button
                    v-for="role in filteredAvailableRoles"
                    :key="role.value"
                    class="w-full flex items-center justify-between p-2 hover:bg-muted rounded-md transition-colors text-left"
                    @click="addRole(role.value)"
                  >
                    <div class="flex-1">
                      <p class="font-medium">{{ role.label }}</p>
                      <p class="text-sm text-muted-foreground">{{ role.description }}</p>
                    </div>
                    <UIcon name="i-lucide-plus" class="h-4 w-4 text-muted-foreground" />
                  </button>
                </div>
              </div>
            </div>
            
            <!-- Help text -->
            <p v-if="state.role_ids.length === 0" class="text-sm text-muted-foreground">
              Start typing to search and add roles
            </p>
          </div>
        </UFormField>

        <!-- Validity Period (Optional) -->
        <div class="grid grid-cols-2 gap-4">
          <UFormField name="valid_from" label="Valid From (Optional)">
            <div class="flex gap-2">
              <UPopover v-model:open="validFromPopoverOpen" class="flex-1">
                <UButton color="neutral" variant="subtle" icon="i-lucide-calendar" class="w-full justify-start">
                  {{ validFromDate ? df.format(validFromDate.toDate(getLocalTimeZone())) : 'Select start date' }}
                </UButton>

                <template #content>
                  <UCalendar v-model="validFromDate" class="p-2" @update:model-value="validFromPopoverOpen = false" />
                </template>
              </UPopover>
              <UButton 
                v-if="validFromDate" 
                icon="i-lucide-x" 
                variant="ghost" 
                color="neutral"
                size="sm"
                square
                @click="clearValidFrom"
              />
            </div>
          </UFormField>

          <UFormField name="valid_until" label="Valid Until (Optional)">
            <div class="flex gap-2">
              <UPopover v-model:open="validUntilPopoverOpen" class="flex-1">
                <UButton color="neutral" variant="subtle" icon="i-lucide-calendar" class="w-full justify-start">
                  {{ validUntilDate ? df.format(validUntilDate.toDate(getLocalTimeZone())) : 'Select end date' }}
                </UButton>

                <template #content>
                  <UCalendar v-model="validUntilDate" class="p-2" @update:model-value="validUntilPopoverOpen = false" />
                </template>
              </UPopover>
              <UButton 
                v-if="validUntilDate" 
                icon="i-lucide-x" 
                variant="ghost" 
                color="neutral"
                size="sm"
                square
                @click="clearValidUntil"
              />
            </div>
          </UFormField>
        </div>

        <UAlert 
          v-if="validityWarning" 
          color="warning" 
          variant="subtle"
          icon="i-lucide-alert-triangle"
          :title="validityWarning"
        />
      </UForm>
    </template>

    <template #footer>
      <div class="flex justify-end gap-3">
        <UButton 
          variant="outline" 
          @click="isOpen = false"
        >
          Cancel
        </UButton>
        <UButton 
          type="submit"
          :loading="isSubmitting"
          @click="onSubmit"
        >
          Add Member
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { z } from 'zod'
import { CalendarDate, DateFormatter, getLocalTimeZone } from '@internationalized/date'
import type { User, Role } from '~/types/auth.types'

const props = defineProps<{
  open: boolean
  entityId: string
  entityName: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'member-added': []
}>()

// Date formatter
const df = new DateFormatter('en-US', {
  dateStyle: 'medium'
})

// Model binding
const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

// Stores
const authStore = useAuthStore()
const contextStore = useContextStore()
const toast = useToast()

// Date state
const validFromDate = shallowRef<CalendarDate | null>(null)
const validUntilDate = shallowRef<CalendarDate | null>(null)

// Popover state
const validFromPopoverOpen = ref(false)
const validUntilPopoverOpen = ref(false)

// Watch date changes and update form state
watch(validFromDate, (newDate) => {
  if (newDate) {
    state.valid_from = newDate.toDate(getLocalTimeZone()).toISOString()
  } else {
    state.valid_from = ''
  }
})

watch(validUntilDate, (newDate) => {
  if (newDate) {
    state.valid_until = newDate.toDate(getLocalTimeZone()).toISOString()
  } else {
    state.valid_until = ''
  }
})

// Form schema
const schema = z.object({
  user_id: z.string().min(1, 'User is required'),
  role_ids: z.array(z.string()).min(1, 'At least one role is required'),
  valid_from: z.string().optional(),
  valid_until: z.string().optional()
}).refine((data) => {
  if (data.valid_from && data.valid_until) {
    return new Date(data.valid_from) < new Date(data.valid_until)
  }
  return true
}, {
  message: 'Valid until must be after valid from',
  path: ['valid_until']
})

// Form state
const state = reactive({
  user_id: '',
  role_ids: [] as string[],
  valid_from: '',
  valid_until: ''
})

// Other state
const isSubmitting = ref(false)
const isLoadingUsers = ref(false)
const isLoadingRoles = ref(false)
const userSearchQuery = ref('')
const roleSearchQuery = ref('')
const showRoleDropdown = ref(false)
const availableUsers = ref<Array<{ value: string; label: string; email: string }>>([])
const availableRoles = ref<Array<{ value: string; label: string; description: string }>>([])

// Ref for role dropdown container
const roleDropdownRef = ref<HTMLElement>()

// Click outside handler
onClickOutside(roleDropdownRef, () => {
  showRoleDropdown.value = false
})

// Computed
const filteredAvailableRoles = computed(() => {
  const query = roleSearchQuery.value.toLowerCase()
  const assignedRoleIds = new Set(state.role_ids)
  
  return availableRoles.value.filter(role => {
    // Don't show already assigned roles
    if (assignedRoleIds.has(role.value)) return false
    
    // Filter by search query
    if (!query) return true
    return role.label.toLowerCase().includes(query) || 
           role.description.toLowerCase().includes(query)
  })
})

const validityWarning = computed(() => {
  if (state.valid_from && state.valid_until) {
    const from = new Date(state.valid_from)
    const until = new Date(state.valid_until)
    const now = new Date()
    
    if (from >= until) {
      return 'Start date must be before end date'
    }
    if (from < now) {
      return 'Start date is in the past'
    }
    if (until < now) {
      return 'End date is in the past'
    }
  } else if (state.valid_from) {
    const from = new Date(state.valid_from)
    const now = new Date()
    if (from < now) {
      return 'Start date is in the past'
    }
  } else if (state.valid_until) {
    const until = new Date(state.valid_until)
    const now = new Date()
    if (until < now) {
      return 'End date is in the past'
    }
  }
  return null
})

const selectedUserLabel = computed(() => {
  const user = availableUsers.value.find(u => u.value === state.user_id)
  return user ? user.label : ''
})

// Methods
const searchUsers = async () => {
  const query = userSearchQuery.value
  if (!query || query.length < 2) {
    availableUsers.value = []
    return
  }

  isLoadingUsers.value = true
  try {
    const response = await authStore.apiCall<{ items: User[] }>(
      `/v1/users?search=${encodeURIComponent(query)}&page_size=10`,
      { headers: contextStore.getContextHeaders }
    )

    availableUsers.value = response.items.map(user => ({
      value: user.id,
      label: user.profile?.first_name && user.profile?.last_name 
        ? `${user.profile.first_name} ${user.profile.last_name}`
        : user.email,
      email: user.email
    }))
  } catch (error) {
    console.error('Failed to search users:', error)
    availableUsers.value = []
  } finally {
    isLoadingUsers.value = false
  }
}

// Debounced search function
let searchTimeout: NodeJS.Timeout | null = null
const debouncedSearchUsers = () => {
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  searchTimeout = setTimeout(() => {
    searchUsers()
  }, 300)
}

const fetchRoles = async () => {
  isLoadingRoles.value = true
  try {
    // Fetch roles available for this entity
    const response = await authStore.apiCall<{ items: Role[] }>(
      `/v1/entities/${props.entityId}/roles`,
      { headers: contextStore.getContextHeaders }
    )

    availableRoles.value = response.items.map(role => ({
      value: role.id,
      label: role.display_name || role.name,
      description: role.description || 'No description'
    }))
  } catch (error) {
    console.error('Failed to fetch roles:', error)
    // Fallback to some default roles if the endpoint fails
    availableRoles.value = [
      { value: 'default-admin', label: 'Admin', description: 'Full administrative access' },
      { value: 'default-member', label: 'Member', description: 'Standard member access' },
      { value: 'default-viewer', label: 'Viewer', description: 'Read-only access' }
    ]
  } finally {
    isLoadingRoles.value = false
  }
}

const addRole = (roleId: string) => {
  if (!state.role_ids.includes(roleId)) {
    state.role_ids.push(roleId)
  }
  roleSearchQuery.value = ''
  showRoleDropdown.value = false
}

const removeRole = (roleId: string) => {
  const index = state.role_ids.indexOf(roleId)
  if (index > -1) {
    state.role_ids.splice(index, 1)
  }
}

const getRoleLabel = (roleId: string) => {
  const role = availableRoles.value.find(r => r.value === roleId)
  return role?.label || roleId
}

const onSubmit = async () => {
  isSubmitting.value = true

  try {
    // For each role, create a member entry
    const promises = state.role_ids.map(async (roleId) => {
      const memberData: any = {
        user_id: state.user_id,
        role_id: roleId
      }

      if (state.valid_from) {
        memberData.valid_from = new Date(state.valid_from).toISOString()
      }

      if (state.valid_until) {
        memberData.valid_until = new Date(state.valid_until).toISOString()
      }

      return authStore.apiCall(`/v1/entities/${props.entityId}/members`, {
        method: 'POST',
        body: memberData,
        headers: contextStore.getContextHeaders
      })
    })

    // Add all memberships
    await Promise.all(promises)

    toast.add({
      title: 'Member added',
      description: `User has been added with ${state.role_ids.length} role${state.role_ids.length > 1 ? 's' : ''}`,
      color: 'success'
    })

    // Reset form and close modal
    resetForm()
    isOpen.value = false
    emit('member-added')
  } catch (error: any) {
    toast.add({
      title: 'Failed to add member',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

const resetForm = () => {
  state.user_id = ''
  state.role_ids = []
  state.valid_from = ''
  state.valid_until = ''
  userSearchQuery.value = ''
  roleSearchQuery.value = ''
  availableUsers.value = []
  validFromDate.value = null
  validUntilDate.value = null
  validFromPopoverOpen.value = false
  validUntilPopoverOpen.value = false
  showRoleDropdown.value = false
}

const clearValidFrom = () => {
  validFromDate.value = null
  state.valid_from = ''
}

const clearValidUntil = () => {
  validUntilDate.value = null
  state.valid_until = ''
}

const getInitials = (name: string) => {
  return name
    .split(' ')
    .map(part => part.charAt(0))
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

// Fetch roles when modal opens
watch(isOpen, (newValue) => {
  if (newValue) {
    fetchRoles()
  } else {
    resetForm()
  }
})
</script>