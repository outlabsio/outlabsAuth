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
  is_active: true,
  valid_from: '',
  valid_until: ''
})

// Keep track of selected user separately
const selectedUserId = ref('')

// Other state
const userSearchQuery = ref('')
const isSearchingUsers = ref(false)



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

// Keep track of the selected user object
const selectedUserItem = ref<{ value: string; label: string; email: string } | null>(null)

const selectedUser = computed(() => {
  return selectedUserItem.value || entityMembersStore.availableUsers.find(u => u.value === state.user_id) || null
})

// Methods
const searchUsers = async (query: string) => {
  if (!query || query.length < 2) {
    entityMembersStore.clearAvailableUsers()
    return
  }
  
  isSearchingUsers.value = true
  try {
    await entityMembersStore.searchUsers(query)
  } finally {
    isSearchingUsers.value = false
  }
}

// Watch for search query changes with debouncing
const debouncedSearchUsers = useDebounceFn((query: string) => {
  searchUsers(query)
}, 300)

watch(userSearchQuery, (query) => {
  debouncedSearchUsers(query)
})

// Watch for user selection
watch(() => state.user_id, (newUserId) => {
  if (newUserId) {
    // When a user is selected, store their details
    const user = entityMembersStore.availableUsers.find(u => u.value === newUserId)
    if (user) {
      selectedUserItem.value = user
    }
  } else {
    selectedUserItem.value = null
  }
})



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
    is_active: state.is_active,
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
    state.is_active = newMember.is_active
    
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
    state.is_active = true
    state.valid_from = ''
    state.valid_until = ''
    userSearchQuery.value = ''
    validFromDate.value = null
    validUntilDate.value = null
    selectedUserItem.value = null
    entityMembersStore.clearAvailableUsers()
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
      <USelectMenu
        v-model="state.user_id"
        v-model:search-term="userSearchQuery"
        :items="selectedUserItem && !entityMembersStore.availableUsers.length ? [selectedUserItem] : entityMembersStore.availableUsers"
        placeholder="Search users by name or email..."
        :loading="entityMembersStore.isLoadingUsers"
        searchable
        searchable-placeholder="Type at least 2 characters to search..."
        value-key="value"
        label-key="label"
        ignore-filter
        :search-input="{ 
          placeholder: 'Type at least 2 characters to search...',
          loading: entityMembersStore.isLoadingUsers
        }"
      >
        <template #item="{ item }">
          <div class="flex items-center gap-3">
            <UAvatar 
              :label="getInitials(item.label)" 
              size="2xs"
            />
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium truncate">{{ item.label }}</p>
              <p class="text-xs text-muted-foreground truncate">{{ item.email }}</p>
            </div>
          </div>
        </template>
        <template #leading>
          <div v-if="selectedUser" class="flex items-center gap-2">
            <UAvatar 
              :label="getInitials(selectedUser.label)" 
              size="2xs"
            />
          </div>
        </template>
        <template #empty>
          <div class="px-3 py-2 text-sm text-muted-foreground">
            {{ userSearchQuery.length < 2 ? 'Type at least 2 characters to search' : 'No users found' }}
          </div>
        </template>
      </USelectMenu>
    </UFormField>

    <!-- Role Selection -->
    <UFormField name="roles" label="Roles" required>
      <USelectMenu
        v-model="state.role_ids"
        :items="entityMembersStore.availableRoles"
        placeholder="Search and select roles..."
        :loading="entityMembersStore.isLoadingRoles"
        multiple
        searchable
        value-key="value"
        label-key="label"
      >
        <template #item="{ item }">
          <div class="flex-1">
            <p class="font-medium">{{ item.label }}</p>
            <p class="text-sm text-muted-foreground">{{ item.description }}</p>
          </div>
        </template>
      </USelectMenu>
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