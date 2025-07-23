<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Role, Entity } from '~/types/auth.types'

const props = defineProps<{
  mode: 'create' | 'edit'
  role?: Role | null
  defaultEntityId?: string | null
}>()

const emit = defineEmits<{
  submit: [data: any]
  cancel: []
  delete: []
}>()

// Get context store for entity suggestions
const contextStore = useContextStore()
const entitiesStore = useEntitiesStore()

// State for entity search
const entitySearch = ref('')
const entityOptions = ref<Array<{ value: string; label: string }>([])
const loadingEntities = ref(false)
const isLoading = ref(false)

// Fetch all entities for parent selection
const { data: allEntities } = await useAsyncData(
  "all-entities-for-roles",
  async () => {
    const authStore = useAuthStore()
    const response = await authStore.apiCall<{ items: Entity[] }>("/v1/entities?page_size=100")
    return response.items || []
  },
  {
    lazy: true,
    default: () => [],
  }
)

// Computed entity options
const entitySelectOptions = computed(() => {
  const options = []
  if (allEntities.value && Array.isArray(allEntities.value)) {
    allEntities.value.forEach((entity) => {
      options.push({
        label: `${entity.display_name || entity.name} (${entity.entity_type})`,
        value: entity.id,
      })
    })
  }
  return options
})

// Assignable types - dynamic based on entities
const assignableTypeOptions = computed(() => {
  const types = new Set<string>()
  
  // Add common types
  types.add('platform')
  types.add('organization')
  types.add('access_group')
  
  // Add types from entities
  if (allEntities.value) {
    allEntities.value.forEach(entity => {
      if (entity.entity_type) {
        types.add(entity.entity_type)
      }
    })
  }
  
  return Array.from(types).sort().map(type => ({
    value: type,
    label: type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' ')
  }))
})

// Form validation schema
const schema = z.object({
  name: z.string()
    .min(1, 'Role name is required')
    .max(50, 'Role name must be less than 50 characters')
    .regex(/^[a-zA-Z0-9_-]+$/, 'Role name can only contain letters, numbers, underscores, and hyphens'),
  display_name: z.string()
    .min(1, 'Display name is required')
    .max(100, 'Display name must be less than 100 characters'),
  description: z.string().max(500, 'Description must be less than 500 characters').optional(),
  entity_id: z.string().optional(),
  assignable_at_types: z.array(z.string()).min(1, 'Select at least one assignable type'),
  is_global: z.boolean().default(false),
  permissions: z.array(z.string()).min(1, 'Select at least one permission'),
})

type Schema = z.output<typeof schema>

// Form state
const state = reactive<Partial<Schema>>({
  name: props.role?.name || '',
  display_name: props.role?.display_name || '',
  description: props.role?.description || '',
  entity_id: props.role?.entity_id || props.defaultEntityId || '',
  assignable_at_types: props.role?.assignable_at_types || [],
  is_global: props.role?.is_global || false,
  permissions: props.role?.permissions || [],
})

// Computed for global toggle
const isGlobal = computed({
  get: () => state.is_global || false,
  set: (value: boolean) => {
    state.is_global = value
    if (value) {
      state.entity_id = ''
    }
  }
})

// Generate system name from display name
const generateSystemName = (displayName: string) => {
  return displayName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
}

// Watch display name to auto-generate system name
watch(() => state.display_name, (newDisplayName) => {
  if (props.mode === 'create' && newDisplayName) {
    state.name = generateSystemName(newDisplayName)
  }
})

// Handle form submission
async function onSubmit(event: FormSubmitEvent<Schema>) {
  isLoading.value = true
  
  try {
    const data: any = {
      name: event.data.name,
      display_name: event.data.display_name,
      description: event.data.description,
      permissions: event.data.permissions,
      assignable_at_types: event.data.assignable_at_types,
      is_global: event.data.is_global,
    }
    
    if (!event.data.is_global && event.data.entity_id) {
      data.entity_id = event.data.entity_id
    }
    
    emit('submit', data)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <UForm :schema="schema" :state="state" @submit="onSubmit" class="space-y-8">
    <!-- Basic Information Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">Basic Information</h5>

      <!-- Display Name -->
      <UFormField label="Role Name" name="display_name" required class="w-full">
        <UInput 
          v-model="state.display_name" 
          placeholder="e.g., Administrator, Content Editor, Viewer" 
          size="lg" 
          class="w-full" 
        />
        <template #description>
          <span class="text-xs text-muted-foreground">A user-friendly name for this role</span>
        </template>
      </UFormField>

      <!-- System Name (auto-generated) -->
      <UFormField v-if="mode === 'create'" label="System Name" name="name" required class="w-full">
        <UInput 
          v-model="state.name" 
          placeholder="admin_role" 
          size="lg"
          class="w-full font-mono"
          :disabled="mode === 'edit'"
        />
        <template #description>
          <span class="text-xs text-muted-foreground">
            {{ mode === 'create' ? 'Unique identifier (auto-generated, can be customized)' : 'System identifier (cannot be changed)' }}
          </span>
        </template>
      </UFormField>

      <!-- Description -->
      <UFormField label="Description" name="description" class="w-full">
        <UTextarea 
          v-model="state.description" 
          placeholder="Describe the purpose and permissions of this role" 
          :rows="3" 
          class="w-full" 
        />
      </UFormField>
    </div>

    <USeparator />

    <!-- Scope Configuration Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">Scope Configuration</h5>

      <!-- Global Toggle -->
      <UFormField name="is_global" class="w-full">
        <div class="flex items-center gap-3">
          <USwitch v-model="isGlobal" :color="isGlobal ? 'primary' : 'neutral'" />
          <div>
            <span class="text-sm font-medium">Global Role</span>
            <p class="text-xs text-muted-foreground">
              {{ isGlobal ? 'This role can be used across all entities in the system' : 'This role is scoped to a specific entity and its children' }}
            </p>
          </div>
        </div>
      </UFormField>

      <!-- Entity Selection (if not global) -->
      <UFormField v-if="!isGlobal" label="Owner Entity" name="entity_id" required class="w-full">
        <USelectMenu
          v-model="state.entity_id"
          :options="entitySelectOptions"
          searchable
          placeholder="Select the entity that owns this role..."
          value-attribute="value"
          option-attribute="label"
          class="w-full"
        >
          <template #empty>
            <div class="text-center py-2 text-sm text-muted-foreground">
              No entities found
            </div>
          </template>
        </USelectMenu>
        <template #description>
          <span class="text-xs text-muted-foreground">The entity that owns and manages this role</span>
        </template>
      </UFormField>

      <!-- Assignable At Types -->
      <UFormField label="Can Be Assigned At" name="assignable_at_types" required class="w-full">
        <div class="p-4  rounded-lg bg-neutral-50 dark:bg-neutral-800/50 space-y-3">
          <p class="text-sm text-muted-foreground mb-3">
            Select the entity types where users can be assigned this role:
          </p>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
            <label
              v-for="option in assignableTypeOptions"
              :key="option.value"
              class="flex items-center gap-2 p-2 rounded hover:bg-neutral-100 dark:hover:bg-neutral-800 cursor-pointer"
            >
              <UCheckbox
                :model-value="state.assignable_at_types?.includes(option.value)"
                @update:model-value="(checked) => {
                  if (!state.assignable_at_types) state.assignable_at_types = []
                  if (checked) {
                    state.assignable_at_types = [...state.assignable_at_types, option.value]
                  } else {
                    state.assignable_at_types = state.assignable_at_types.filter(v => v !== option.value)
                  }
                }"
              />
              <span class="text-sm">{{ option.label }}</span>
            </label>
          </div>
        </div>
      </UFormField>
    </div>

    <USeparator />

    <!-- Permissions Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">Permissions</h5>

      <UFormField name="permissions" required class="w-full">
        <RolesPermissionSelector
          v-model="state.permissions"
          :entity-id="state.entity_id"
        />
        <template #description>
          <span class="text-xs text-muted-foreground">Select the permissions to grant when this role is assigned</span>
        </template>
      </UFormField>
    </div>

    <!-- Danger Zone - Only show in edit mode -->
    <div v-if="mode === 'edit' && props.role && !props.role.is_system_role" class="space-y-6 w-full">
      <USeparator />

      <div class="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-6">
        <div class="flex items-center gap-3 mb-4">
          <UIcon name="i-lucide-alert-triangle" class="h-5 w-5 text-red-600 dark:text-red-400" />
          <h3 class="font-semibold text-red-600 dark:text-red-400">Danger Zone</h3>
        </div>

        <div class="space-y-4">
          <div>
            <h4 class="font-medium">Delete this role</h4>
            <p class="text-sm text-muted-foreground mt-1">
              Deleting a role will remove it from all users who have been assigned this role. This action cannot be undone.
            </p>
          </div>

          <UButton 
            color="error" 
            @click="emit('delete')" 
            class="w-full" 
            icon="i-lucide-trash"
          >
            Delete Role
          </UButton>
        </div>
      </div>
    </div>
  </UForm>
</template>