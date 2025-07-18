<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { User, UserCreateRequest, UserUpdateRequest, UserEntityAssignment } from '~/types/auth.types'

const props = defineProps<{
  mode: 'create' | 'edit'
  user?: User | null
}>()

const emit = defineEmits<{
  submit: [data: UserCreateRequest | UserUpdateRequest]
  cancel: []
}>()

// Stores
const usersStore = useUsersStore()
const entitiesStore = useEntitiesStore()
const rolesStore = useRolesStore()
const contextStore = useContextStore()

// State
const isLoading = ref(false)
const showPassword = ref(false)
const entityAssignments = ref<UserEntityAssignment[]>([])

// Load entities and roles
onMounted(async () => {
  await Promise.all([
    entitiesStore.fetchEntities(),
    rolesStore.fetchRoles()
  ])
  
  // Initialize entity assignments from user data
  if (props.mode === 'edit' && props.user) {
    entityAssignments.value = props.user.entities.map(entity => ({
      entity_id: entity.id,
      role_ids: entity.roles.map(r => r.id),
      status: entity.status,
      valid_from: null,
      valid_until: null
    }))
  }
})

// Form validation schema
const schema = z.object({
  email: z.string().email('Invalid email address'),
  password: props.mode === 'create' 
    ? z.string().min(8, 'Password must be at least 8 characters').optional()
    : z.string().optional(),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  phone: z.string().optional(),
  is_active: z.boolean().default(true),
  send_welcome_email: z.boolean().default(true),
})

type Schema = z.output<typeof schema>

// Form state
const state = reactive<Partial<Schema>>({
  email: props.user?.email || '',
  password: undefined,
  first_name: props.user?.profile.first_name || '',
  last_name: props.user?.profile.last_name || '',
  phone: props.user?.profile.phone || '',
  is_active: props.user?.is_active ?? true,
  send_welcome_email: true,
})

// Computed
const availableEntities = computed(() => {
  // Filter out already assigned entities
  const assignedIds = entityAssignments.value.map(a => a.entity_id)
  return entitiesStore.entities.filter(e => !assignedIds.includes(e.id))
})

const getRolesForEntity = (entityId: string) => {
  const entity = entitiesStore.entities.find(e => e.id === entityId)
  if (!entity) return []
  
  // Get roles that can be assigned at this entity type
  return rolesStore.roles.filter(role => {
    // Global roles or roles for this entity
    if (role.is_global || role.entity_id === entityId) return true
    
    // Roles assignable at this entity type
    if (role.assignable_at_types?.includes(entity.entity_type)) return true
    
    return false
  })
}

// Methods
function addEntityAssignment() {
  entityAssignments.value.push({
    entity_id: '',
    role_ids: [],
    status: 'active'
  })
}

function removeEntityAssignment(index: number) {
  entityAssignments.value.splice(index, 1)
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  const data = props.mode === 'create' ? {
    email: event.data.email,
    password: event.data.password,
    first_name: event.data.first_name,
    last_name: event.data.last_name,
    phone: event.data.phone,
    entity_assignments: entityAssignments.value.filter(a => a.entity_id),
    is_active: event.data.is_active,
    send_welcome_email: event.data.send_welcome_email,
  } : {
    email: event.data.email !== props.user?.email ? event.data.email : undefined,
    first_name: event.data.first_name,
    last_name: event.data.last_name,
    phone: event.data.phone,
    is_active: event.data.is_active,
    entity_assignments: entityAssignments.value.filter(a => a.entity_id),
  }
  
  emit('submit', data)
}
</script>

<template>
  <UForm :schema="schema" :state="state" @submit="onSubmit" class="space-y-8">
    <!-- Basic Information Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">
        Basic Information
      </h5>
      
      <!-- Email -->
      <UFormField label="Email Address" name="email" required class="w-full">
        <UInput 
          v-model="state.email" 
          type="email"
          placeholder="user@example.com" 
          icon="i-lucide-mail"
          size="lg"
          class="w-full"
        />
        <template #description>
          <span class="text-xs text-muted-foreground">
            The email address will be used for login and notifications
          </span>
        </template>
      </UFormField>

      <!-- Password (Create Mode Only) -->
      <div v-if="mode === 'create'" class="space-y-6">
        <UFormField label="Password" name="password" class="w-full">
          <UInput 
            v-model="state.password" 
            :type="showPassword ? 'text' : 'password'"
            placeholder="Leave blank to auto-generate" 
            icon="i-lucide-lock"
            size="lg"
            class="w-full"
          >
            <template #trailing>
              <UButton
                variant="ghost"
                size="xs"
                :icon="showPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
                @click="showPassword = !showPassword"
              />
            </template>
          </UInput>
          <template #description>
            <span class="text-xs text-muted-foreground">
              If blank, a temporary password will be generated and sent via email
            </span>
          </template>
        </UFormField>

        <!-- Send Welcome Email -->
        <UFormField name="send_welcome_email" class="w-full">
          <div class="flex items-center gap-3">
            <UCheckbox v-model="state.send_welcome_email" />
            <div>
              <span class="text-sm font-medium">Send Welcome Email</span>
              <p class="text-xs text-muted-foreground">
                Send login instructions and welcome message to the new user
              </p>
            </div>
          </div>
        </UFormField>
      </div>

      <!-- Name Fields -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <UFormField label="First Name" name="first_name" class="w-full">
          <UInput 
            v-model="state.first_name" 
            placeholder="John" 
            icon="i-lucide-user"
            size="lg"
            class="w-full"
          />
        </UFormField>

        <UFormField label="Last Name" name="last_name" class="w-full">
          <UInput 
            v-model="state.last_name" 
            placeholder="Doe" 
            size="lg"
            class="w-full"
          />
        </UFormField>
      </div>

      <!-- Phone -->
      <UFormField label="Phone Number" name="phone" class="w-full">
        <UInput 
          v-model="state.phone" 
          placeholder="+1 (555) 123-4567" 
          icon="i-lucide-phone"
          size="lg"
          class="w-full"
        />
        <template #description>
          <span class="text-xs text-muted-foreground">
            Used for two-factor authentication and account recovery
          </span>
        </template>
      </UFormField>
    </div>

    <USeparator />

    <!-- Configuration Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">
        Configuration
      </h5>

      <!-- Active Status -->
      <UFormField name="is_active" class="w-full">
        <div class="flex items-center gap-3">
          <USwitch v-model="state.is_active" :color="state.is_active ? 'success' : 'neutral'" />
          <div>
            <span class="text-sm font-medium">Active</span>
            <p class="text-xs text-muted-foreground">
              {{ state.is_active ? 'User can log in and access the system' : 'User is blocked from accessing the system' }}
            </p>
          </div>
        </div>
      </UFormField>
    </div>

    <USeparator />

    <!-- Entity Memberships Section -->
    <div class="space-y-6 w-full">
      <div class="flex items-center justify-between">
        <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">
          Entity Memberships
          <span class="text-xs font-normal text-muted-foreground ml-2">
            ({{ entityAssignments.length }})
          </span>
        </h5>
        <UButton
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          @click="addEntityAssignment"
          :disabled="availableEntities.length === 0"
        >
          Add Membership
        </UButton>
      </div>

      <p class="text-sm text-muted-foreground">
        Assign the user to entities and specify their roles. Users inherit permissions based on their roles within each entity.
      </p>

      <!-- Entity Assignments List -->
      <div v-if="entityAssignments.length > 0" class="space-y-4">
        <UCard v-for="(assignment, index) in entityAssignments" :key="index" class="p-4">
          <div class="space-y-4">
            <!-- Entity Selection -->
            <UFormField label="Entity" required class="w-full">
              <USelectMenu
                v-model="assignment.entity_id"
                :options="[
                  { label: 'Select entity...', value: '', disabled: true },
                  ...availableEntities.map(e => ({
                    label: `${e.display_name} (${e.entity_type})`,
                    value: e.id
                  }))
                ]"
                value-attribute="value"
                option-attribute="label"
                class="w-full"
              />
            </UFormField>

            <!-- Role Selection -->
            <UFormField v-if="assignment.entity_id" label="Roles" required class="w-full">
              <USelectMenu
                v-model="assignment.role_ids"
                :options="getRolesForEntity(assignment.entity_id).map(r => ({
                  label: r.display_name,
                  value: r.id
                }))"
                multiple
                placeholder="Select roles..."
                value-attribute="value"
                option-attribute="label"
                class="w-full"
              >
                <template #label>
                  <span v-if="assignment.role_ids.length === 0">Select roles...</span>
                  <span v-else>{{ assignment.role_ids.length }} role(s) selected</span>
                </template>
              </USelectMenu>
              <template #description>
                <span class="text-xs text-muted-foreground">
                  Select one or more roles for this entity membership
                </span>
              </template>
            </UFormField>

            <!-- Membership Status -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <UCheckbox v-model="assignment.status" true-value="active" false-value="inactive" />
                <span class="text-sm">Active membership</span>
              </div>
              
              <UButton
                variant="ghost"
                size="sm"
                icon="i-lucide-trash"
                color="error"
                @click="removeEntityAssignment(index)"
              >
                Remove
              </UButton>
            </div>
          </div>
        </UCard>
      </div>

      <!-- Empty State -->
      <div v-else class="text-center py-8 border-2 border-dashed border-neutral-200 dark:border-neutral-800 rounded-lg">
        <UIcon name="i-lucide-building" class="h-8 w-8 mb-2 text-muted-foreground" />
        <p class="text-sm text-muted-foreground">No entity memberships assigned</p>
        <p class="text-xs text-muted-foreground mt-1">
          Add memberships to grant access to entities
        </p>
        <UButton
          variant="outline"
          size="sm"
          icon="i-lucide-plus"
          class="mt-4"
          @click="addEntityAssignment"
          :disabled="availableEntities.length === 0"
        >
          Add First Membership
        </UButton>
      </div>
    </div>
  </UForm>
</template>