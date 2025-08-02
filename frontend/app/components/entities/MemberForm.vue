<script setup lang="ts">
import { z } from 'zod'
import { CalendarDate, DateFormatter, getLocalTimeZone, parseDate } from '@internationalized/date'
import type { EntityMember } from '~/types/auth.types'

const props = defineProps<{
  member: EntityMember | null
  mode: 'create' | 'edit'
}>()

const emit = defineEmits<{
  submit: [data: any]
  cancel: []
}>()

// Date formatter
const df = new DateFormatter('en-US', {
  dateStyle: 'medium'
})

// Store
const entityMembersStore = useEntityMembersStore()

// Date state
const validFromDate = shallowRef<CalendarDate | null>(null)
const validUntilDate = shallowRef<CalendarDate | null>(null)

// Popover state
const validFromPopoverOpen = ref(false)
const validUntilPopoverOpen = ref(false)

// Form schema
const schema = computed(() => {
  if (props.mode === 'create') {
    return z.object({
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
  } else {
    return z.object({
      role_ids: z.array(z.string()).min(1, 'At least one role is required'),
      status: z.enum(['active', 'suspended', 'revoked']).optional(),
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
  }
})

// Form state
const state = reactive({
  user_id: '',
  role_ids: [] as string[],
  status: 'active' as 'active' | 'suspended' | 'revoked',
  valid_from: '',
  valid_until: ''
})

// Other state
const userSearchQuery = ref('')
const roleSearchQuery = ref('')
const showRoleDropdown = ref(false)

// Ref for role dropdown container
const roleDropdownRef = ref<HTMLElement>()

// Click outside handler
onClickOutside(roleDropdownRef, () => {
  showRoleDropdown.value = false
})

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

// Status options
const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'revoked', label: 'Revoked' }
]

// Computed
const filteredAvailableRoles = computed(() => {
  const query = roleSearchQuery.value.toLowerCase()
  const assignedRoleIds = new Set(state.role_ids)
  
  return entityMembersStore.availableRoles.filter(role => {
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
    if (props.mode === 'create') {
      if (from < now) {
        return 'Start date is in the past'
      }
      if (until < now) {
        return 'End date is in the past'
      }
    }
  } else if (props.mode === 'create') {
    if (state.valid_from) {
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
  }
  return null
})

const selectedUserLabel = computed(() => {
  const user = entityMembersStore.availableUsers.find(u => u.value === state.user_id)
  return user ? user.label : ''
})

// Methods
const searchUsers = async () => {
  const query = userSearchQuery.value
  if (!query || query.length < 2) {
    return
  }
  await entityMembersStore.searchUsers(query)
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
  const role = entityMembersStore.availableRoles.find(r => r.value === roleId)
  return role?.label || roleId
}

const clearValidFrom = () => {
  validFromDate.value = null
  state.valid_from = ''
}

const clearValidUntil = () => {
  validUntilDate.value = null
  state.valid_until = ''
}

const onSubmit = () => {
  emit('submit', {
    user_id: state.user_id,
    role_ids: state.role_ids,
    status: state.status,
    valid_from: state.valid_from || null,
    valid_until: state.valid_until || null
  })
}

const getInitials = (name: string) => {
  return name
    .split(' ')
    .map(part => part.charAt(0))
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

// Convert date string to CalendarDate
const dateStringToCalendarDate = (dateString: string | null | undefined) => {
  if (!dateString) return null
  const date = new Date(dateString)
  return new CalendarDate(date.getFullYear(), date.getMonth() + 1, date.getDate())
}

// Initialize form when member changes (edit mode)
watch(() => props.member, (newMember) => {
  if (newMember && props.mode === 'edit') {
    // Set all role IDs
    state.role_ids = newMember.roles?.map(r => r.id) || []
    state.status = newMember.status as 'active' | 'suspended' | 'revoked'
    
    // Set dates
    validFromDate.value = dateStringToCalendarDate(newMember.valid_from)
    validUntilDate.value = dateStringToCalendarDate(newMember.valid_until)
  }
}, { immediate: true })

// Reset form when mode changes to create
watch(() => props.mode, (newMode) => {
  if (newMode === 'create') {
    state.user_id = ''
    state.role_ids = []
    state.status = 'active'
    state.valid_from = ''
    state.valid_until = ''
    userSearchQuery.value = ''
    roleSearchQuery.value = ''
    validFromDate.value = null
    validUntilDate.value = null
  }
}, { immediate: true })
</script>

<template>
  <UForm 
    :schema="schema" 
    :state="state" 
    @submit="onSubmit"
    class="space-y-4"
  >
    <!-- Member Info (Edit Mode) -->
    <div v-if="mode === 'edit' && member" class="bg-muted/50 rounded-lg p-4">
      <div class="flex items-center gap-3">
        <UAvatar 
          :label="getInitials(member.user_name)" 
          size="md"
        />
        <div>
          <h4 class="font-medium">{{ member.user_name }}</h4>
          <p class="text-sm text-muted-foreground">{{ member.user_email }}</p>
        </div>
      </div>
    </div>

    <!-- User Selection (Create Mode) -->
    <UFormField v-if="mode === 'create'" name="user_id" label="User" required>
      <div class="space-y-2">
        <UInput
          v-model="userSearchQuery"
          placeholder="Search users by name or email..."
          icon="i-lucide-search"
          :loading="entityMembersStore.isLoadingUsers"
          @input="debouncedSearchUsers"
        />
        <USelect
          v-model="state.user_id"
          :items="entityMembersStore.availableUsers"
          placeholder="Select a user from search results"
          :disabled="entityMembersStore.availableUsers.length === 0"
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
          <p v-if="mode === 'edit'" class="text-sm text-muted-foreground">Current roles:</p>
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
            :loading="entityMembersStore.isLoadingRoles"
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
                type="button"
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

    <!-- Status (Edit Mode) -->
    <UFormField v-if="mode === 'edit'" name="status" label="Status">
      <USelect
        v-model="state.status"
        :items="statusOptions"
      />
    </UFormField>

    <!-- Validity Period -->
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