<template>
  <UModal v-model:open="isOpen" title="Update Member" :close-icon="'i-lucide-x'">
    <template #body>

      <div v-if="member" class="space-y-4">
        <!-- Member Info -->
        <div class="bg-muted/50 rounded-lg p-4">
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

        <UForm 
          :schema="schema" 
          :state="state" 
          @submit="onSubmit"
          class="space-y-4"
        >
          <!-- Role Selection -->
          <UFormField name="roles" label="Roles">
            <div class="space-y-3">
              <!-- Current Roles -->
              <div v-if="state.role_ids.length > 0" class="space-y-2">
                <p class="text-sm text-muted-foreground">Current roles:</p>
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
                No roles assigned. Start typing to search and add roles.
              </p>
            </div>
          </UFormField>

          <!-- Status -->
          <UFormField name="status" label="Status">
            <USelect
              v-model="state.status"
              :items="statusOptions"
            />
          </UFormField>

          <!-- Validity Period -->
          <div class="grid grid-cols-2 gap-4">
            <UFormField name="valid_from" label="Valid From">
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

            <UFormField name="valid_until" label="Valid Until">
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
      </div>
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
          Update Member
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { z } from 'zod'
import { CalendarDate, DateFormatter, getLocalTimeZone, parseDate } from '@internationalized/date'
import type { EntityMember, Role } from '~/types/auth.types'

const props = defineProps<{
  open: boolean
  member: EntityMember | null
  entityId: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'member-updated': []
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

// Form state
const state = reactive({
  role_ids: [] as string[],
  status: 'active' as 'active' | 'suspended' | 'revoked',
  valid_from: '',
  valid_until: ''
})

// Other state
const isSubmitting = ref(false)
const isLoadingRoles = ref(false)
const roleSearchQuery = ref('')
const showRoleDropdown = ref(false)
const availableRoles = ref<Array<{ value: string; label: string; description: string }>>([])

// Ref for role dropdown container
const roleDropdownRef = ref<HTMLElement>()

// Click outside handler
onClickOutside(roleDropdownRef, () => {
  showRoleDropdown.value = false
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
    
    if (from >= until) {
      return 'Start date must be before end date'
    }
  }
  return null
})

// Methods
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
  if (!props.member) return

  isSubmitting.value = true

  try {
    // Check what has changed
    const currentRoleIds = props.member.roles?.map(r => r.id) || []
    const rolesChanged = !arraysEqual(currentRoleIds, state.role_ids)
    
    // If roles have changed, we need to handle them differently
    if (rolesChanged) {
      // First, remove the user from the entity completely
      await authStore.apiCall(`/v1/entities/${props.entityId}/members/${props.member.user_id}`, {
        method: 'DELETE',
        headers: contextStore.getContextHeaders
      })
      
      // Then add them back with the new roles
      const promises = state.role_ids.map(async (roleId) => {
        const memberData: any = {
          user_id: props.member.user_id,
          role_id: roleId,
          status: state.status
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

      await Promise.all(promises)
    } else {
      // If only status or dates changed, update normally
      const updateData: any = {}

      if (state.status && state.status !== props.member.status) {
        updateData.status = state.status
      }

      // Handle date updates - explicitly set to null if cleared
      if (state.valid_from) {
        updateData.valid_from = new Date(state.valid_from).toISOString()
      } else if (props.member?.valid_from && !state.valid_from) {
        updateData.valid_from = null
      }

      if (state.valid_until) {
        updateData.valid_until = new Date(state.valid_until).toISOString()
      } else if (props.member?.valid_until && !state.valid_until) {
        updateData.valid_until = null
      }

      // Only proceed if there are changes
      if (Object.keys(updateData).length === 0) {
        toast.add({
          title: 'No changes',
          description: 'No changes were made to the member',
          color: 'info'
        })
        isOpen.value = false
        return
      }

      // Update the member
      await authStore.apiCall(`/v1/entities/${props.entityId}/members/${props.member.user_id}`, {
        method: 'PUT',
        body: updateData,
        headers: contextStore.getContextHeaders
      })
    }

    toast.add({
      title: 'Member updated',
      description: rolesChanged ? `User roles updated to ${state.role_ids.length} role${state.role_ids.length > 1 ? 's' : ''}` : 'Member details have been updated',
      color: 'success'
    })

    // Close modal and emit event
    isOpen.value = false
    emit('member-updated')
  } catch (error: any) {
    toast.add({
      title: 'Failed to update member',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

// Helper function to compare arrays
const arraysEqual = (a: string[], b: string[]) => {
  if (a.length !== b.length) return false
  const sortedA = [...a].sort()
  const sortedB = [...b].sort()
  return sortedA.every((val, index) => val === sortedB[index])
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

// Convert date string to CalendarDate
const dateStringToCalendarDate = (dateString: string | null | undefined) => {
  if (!dateString) return null
  const date = new Date(dateString)
  return new CalendarDate(date.getFullYear(), date.getMonth() + 1, date.getDate())
}

// Initialize form when member changes
watch(() => props.member, (newMember) => {
  if (newMember) {
    // Set all role IDs
    state.role_ids = newMember.roles?.map(r => r.id) || []
    state.status = newMember.status as 'active' | 'suspended' | 'revoked'
    
    // Set dates
    validFromDate.value = dateStringToCalendarDate(newMember.valid_from)
    validUntilDate.value = dateStringToCalendarDate(newMember.valid_until)
    
    // This will trigger the watchers to update state.valid_from and state.valid_until
  } else {
    // Reset when no member
    state.role_ids = []
    roleSearchQuery.value = ''
    showRoleDropdown.value = false
    validFromDate.value = null
    validUntilDate.value = null
    validFromPopoverOpen.value = false
    validUntilPopoverOpen.value = false
  }
}, { immediate: true })

// Fetch roles when modal opens
watch(isOpen, (newValue) => {
  if (newValue) {
    fetchRoles()
  }
})
</script>