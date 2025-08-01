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

// Local type for entity assignments in the form
interface FormEntityAssignment {
  entity_id: string | undefined;
  role_ids: string[];
  status?: string;
  valid_from?: string | null;
  valid_until?: string | null;
}

const entityAssignments = ref<FormEntityAssignment[]>([])
const isLoadingMemberships = ref(false)

// Load entities and roles
onMounted(async () => {
  await Promise.all([
    entitiesStore.fetchEntities(),
    rolesStore.fetchRoles()
  ])

  // Initialize entity assignments from user data
  if (props.mode === 'edit' && props.user) {
    // Fetch ALL memberships including inactive ones
    isLoadingMemberships.value = true
    try {
      const membershipData = await usersStore.fetchUserMemberships(props.user.id, true)
      
      // Convert membership response to entity assignments
      entityAssignments.value = membershipData.memberships.map((membership: any) => ({
        entity_id: membership.entity.id,
        role_ids: membership.roles.map((r: any) => r.id),
        status: membership.status,
        valid_from: membership.valid_from,
        valid_until: membership.valid_until
      }))
    } catch (error) {
      console.error('Failed to fetch user memberships:', error)
      // Fallback to user entities if fetch fails
      entityAssignments.value = props.user.entities.map(entity => ({
        entity_id: entity.id,
        role_ids: entity.roles.map(r => r.id),
        status: entity.status,
        valid_from: null,
        valid_until: null
      }))
    } finally {
      isLoadingMemberships.value = false
    }
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

// Computed property to check if there are any entities left to assign.
// This is used to disable the "Add Membership" button.
const unassignedEntitiesCount = computed(() => {
  if (!entitiesStore.entities) return 0
  const assignedIds = entityAssignments.value.map(a => a.entity_id).filter(Boolean)
  return entitiesStore.entities.filter(e => !assignedIds.includes(e.id)).length
})

// Generates the list of available entities for a specific assignment dropdown.
// It includes all unassigned entities PLUS the entity currently selected in this specific row.
const getAvailableEntitiesForAssignment = (assignmentIndex: number) => {
  // Get IDs of entities assigned in OTHER rows.
  const assignedIdsInOtherRows = entityAssignments.value
      .filter((_, index) => index !== assignmentIndex)
      .map(a => a.entity_id)
      .filter(Boolean)

  // Filter the master list of entities.
  return entitiesStore.entities
      .filter(e => !assignedIdsInOtherRows.includes(e.id))
      .map(e => ({
        label: `${e.display_name} (${e.entity_type})`,
        value: e.id
      }))
}

const getRolesForEntity = (entityId: string) => {
  const entity = entitiesStore.entities.find(e => e.id === entityId)
  if (!entity) {
    return []
  }

  // Get roles that can be assigned at this entity type
  const assignableRoles = rolesStore.roles.filter(role => {
    // Global roles or roles for this entity
    if (role.is_global || role.entity_id === entityId) return true

    // Roles assignable at this entity type
    if (role.assignable_at_types?.includes(entity.entity_type)) return true

    return false
  })

  // In edit mode, also include the user's existing roles for this entity
  // This ensures we can display roles even if they're no longer assignable
  if (props.mode === 'edit' && props.user) {
    const userEntity = props.user.entities.find(e => e.id === entityId)
    if (userEntity) {
      userEntity.roles.forEach(userRole => {
        // Check if this role is already in the assignable list
        const roleExists = assignableRoles.some(r => r.id === userRole.id)
        if (!roleExists) {
          // Add the user's existing role to the list
          // We need to create a role object that matches the expected format
          assignableRoles.push({
            id: userRole.id,
            name: userRole.name,
            display_name: userRole.display_name,
            permissions: userRole.permissions,
            is_global: false,
            entity_id: entityId
          } as any)
        }
      })
    }
  }

  return assignableRoles
}

// Methods
function addEntityAssignment() {
  entityAssignments.value.push({
    entity_id: undefined,
    role_ids: [],
    status: 'active'
  })
}


function removeEntityAssignment(index: number) {
  entityAssignments.value.splice(index, 1)
}

async function onSubmit(event: FormSubmitEvent<Schema>) {
  // Filter and convert assignments to ensure entity_id is string
  const validAssignments = entityAssignments.value
      .filter(a => a.entity_id)
      .map(a => ({
        entity_id: a.entity_id as string,
        role_ids: a.role_ids,
        status: a.status,
        valid_from: a.valid_from,
        valid_until: a.valid_until
      }))

  const data = props.mode === 'create' ? {
    email: event.data.email,
    password: event.data.password,
    first_name: event.data.first_name,
    last_name: event.data.last_name,
    phone: event.data.phone,
    entity_assignments: validAssignments,
    is_active: event.data.is_active,
    send_welcome_email: event.data.send_welcome_email,
  } : {
    email: event.data.email !== props.user?.email ? event.data.email : undefined,
    first_name: event.data.first_name,
    last_name: event.data.last_name,
    phone: event.data.phone,
    is_active: event.data.is_active,
    entity_assignments: validAssignments,
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
            <USwitch v-model="state.send_welcome_email" />
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
            :disabled="unassignedEntitiesCount === 0"
        >
          Add Membership
        </UButton>
      </div>

      <p class="text-sm text-muted-foreground">
        Assign the user to entities and specify their roles. Users inherit permissions based on their roles within each entity.
      </p>

      <!-- Loading State -->
      <div v-if="isLoadingMemberships" class="text-center py-8">
        <UIcon name="i-lucide-loader-2" class="h-6 w-6 animate-spin text-primary mb-2" />
        <p class="text-sm text-muted-foreground">Loading memberships...</p>
      </div>

      <!-- Entity Assignments List -->
      <div v-else-if="entityAssignments.length > 0" class="space-y-4">
        <UCard v-for="(assignment, index) in entityAssignments" :key="index" class="p-4">
          <div class="space-y-4">
            <!-- Entity Selection -->
            <UFormField label="Entity" required class="w-full">
              <USelect
                  v-if="entitiesStore.entities.length > 0"
                  v-model="assignment.entity_id"
                  :items="getAvailableEntitiesForAssignment(index)"
                  placeholder="Select entity..."
                  class="w-full"
              />
              <div v-else class="text-sm text-gray-500">Loading entities...</div>
            </UFormField>

            <!-- Role Selection -->
            <UFormField v-if="assignment.entity_id" label="Roles" required class="w-full">
              <USelect
                  v-model="assignment.role_ids"
                  :items="getRolesForEntity(assignment.entity_id).map(r => ({
                  label: r.display_name,
                  value: r.id
                }))"
                  multiple
                  placeholder="Select roles..."
                  class="w-full"
              />
              <template #description>
                <span class="text-xs text-muted-foreground">
                  Select one or more roles for this entity membership
                </span>
              </template>
            </UFormField>

            <!-- Membership Status -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <USwitch 
                  :model-value="assignment.status === 'active'"
                  @update:model-value="assignment.status = $event ? 'active' : 'inactive'"
                />
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
      <div v-else-if="!isLoadingMemberships" class="text-center py-8 border-2 border-dashed border-neutral-200 dark:border-neutral-800 rounded-lg">
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
            :disabled="unassignedEntitiesCount === 0"
        >
          Add First Membership
        </UButton>
      </div>
    </div>
  </UForm>
</template>