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
        <UFormField name="role_id" label="Role" required>
          <USelect
            v-model="state.role_id"
            :items="availableRoles"
            placeholder="Select a role"
            :loading="isLoadingRoles"
          />
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
  role_id: z.string().min(1, 'Role is required'),
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
  role_id: '',
  valid_from: '',
  valid_until: ''
})

// Other state
const isSubmitting = ref(false)
const isLoadingUsers = ref(false)
const isLoadingRoles = ref(false)
const userSearchQuery = ref('')
const availableUsers = ref<Array<{ value: string; label: string; email: string }>>([])
const availableRoles = ref<Array<{ value: string; label: string; description: string }>>([])

// Computed
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

const onSubmit = async () => {
  isSubmitting.value = true

  try {
    // Prepare the data
    const memberData: any = {
      user_id: state.user_id,
      role_id: state.role_id
    }

    if (state.valid_from) {
      memberData.valid_from = new Date(state.valid_from).toISOString()
    }

    if (state.valid_until) {
      memberData.valid_until = new Date(state.valid_until).toISOString()
    }

    // Add the member
    await authStore.apiCall(`/v1/entities/${props.entityId}/members`, {
      method: 'POST',
      body: memberData,
      headers: contextStore.getContextHeaders
    })

    toast.add({
      title: 'Member added',
      description: 'User has been added to this entity',
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
  state.role_id = ''
  state.valid_from = ''
  state.valid_until = ''
  userSearchQuery.value = ''
  availableUsers.value = []
  validFromDate.value = null
  validUntilDate.value = null
  validFromPopoverOpen.value = false
  validUntilPopoverOpen.value = false
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