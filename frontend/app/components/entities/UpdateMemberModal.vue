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
          <UFormField name="role_id" label="Role">
            <USelect
              v-model="state.role_id"
              :items="availableRoles"
              placeholder="Select a role"
              :loading="isLoadingRoles"
            />
            <template #hint>
              <span v-if="member && member.roles && member.roles.length > 1" class="text-xs text-muted-foreground">
                User has {{ member.roles.length }} roles. Updating will replace all roles with the selected one.
              </span>
            </template>
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
              <UInput 
                v-model="state.valid_from" 
                type="datetime-local"
                placeholder="Start date"
              />
            </UFormField>

            <UFormField name="valid_until" label="Valid Until">
              <UInput 
                v-model="state.valid_until" 
                type="datetime-local"
                placeholder="End date"
              />
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

// Model binding
const isOpen = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

// Stores
const authStore = useAuthStore()
const contextStore = useContextStore()
const toast = useToast()

// Form schema
const schema = z.object({
  role_id: z.string().optional(),
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
  role_id: '',
  status: 'active' as 'active' | 'suspended' | 'revoked',
  valid_from: '',
  valid_until: ''
})

// Other state
const isSubmitting = ref(false)
const isLoadingRoles = ref(false)
const availableRoles = ref<Array<{ value: string; label: string; description: string }>>([])

// Status options
const statusOptions = [
  { value: 'active', label: 'Active' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'revoked', label: 'Revoked' }
]

// Computed
const validityWarning = computed(() => {
  if (state.valid_from && state.valid_until) {
    const from = new Date(state.valid_from)
    const until = new Date(state.valid_until)
    if (from >= until) {
      return 'Valid until must be after valid from'
    }
  }
  return null
})

// Methods
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
    // Prepare the update data - only include changed fields
    const updateData: any = {}

    // For now, we only support updating to a single role through the API
    if (state.role_id) {
      updateData.role_id = state.role_id
    }

    if (state.status && state.status !== props.member.status) {
      updateData.status = state.status
    }

    if (state.valid_from) {
      updateData.valid_from = new Date(state.valid_from).toISOString()
    }

    if (state.valid_until) {
      updateData.valid_until = new Date(state.valid_until).toISOString()
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

    toast.add({
      title: 'Member updated',
      description: 'Member details have been updated',
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

const getInitials = (name: string) => {
  return name
    .split(' ')
    .map(part => part.charAt(0))
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

// Format date for input
const formatDateForInput = (dateString: string | null | undefined) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  // Format as YYYY-MM-DDTHH:mm for datetime-local input
  return date.toISOString().slice(0, 16)
}

// Initialize form when member changes
watch(() => props.member, (newMember) => {
  if (newMember) {
    // Use the first role's ID for now (API only supports single role update)
    state.role_id = newMember.roles && newMember.roles.length > 0 ? newMember.roles[0].id : ''
    state.status = newMember.status as 'active' | 'suspended' | 'revoked'
    state.valid_from = formatDateForInput(newMember.valid_from)
    state.valid_until = formatDateForInput(newMember.valid_until)
  }
}, { immediate: true })

// Fetch roles when modal opens
watch(isOpen, (newValue) => {
  if (newValue) {
    fetchRoles()
  }
})
</script>