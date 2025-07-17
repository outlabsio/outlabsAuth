<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Role } from '~/types/auth.types'

const props = defineProps<{
  mode: 'create' | 'edit'
  role?: Role | null
  defaultEntityId?: string | null
}>()

const emit = defineEmits<{
  submit: [data: any]
  cancel: []
}>()

// Get context store for entity suggestions
const contextStore = useContextStore()
const entitiesStore = useEntitiesStore()

// State for entity search
const entitySearch = ref('')
const entityOptions = ref<Array<{ value: string; label: string }>>([])
const loadingEntities = ref(false)

// Assignable types options
const assignableTypeOptions = [
  { value: 'platform', label: 'Platform' },
  { value: 'organization', label: 'Organization' },
  { value: 'division', label: 'Division' },
  { value: 'branch', label: 'Branch' },
  { value: 'team', label: 'Team' },
  { value: 'access_group', label: 'Access Group' },
]

// Form validation schema
const schema = z.object({
  name: z.string()
    .min(1, 'Name is required')
    .max(50, 'Name must be less than 50 characters')
    .regex(/^[a-zA-Z0-9_-]+$/, 'Name can only contain letters, numbers, underscores, and hyphens'),
  display_name: z.string()
    .min(1, 'Display name is required')
    .max(100, 'Display name must be less than 100 characters'),
  description: z.string().max(500, 'Description must be less than 500 characters').optional().nullable(),
  entity_id: z.string().optional().nullable(),
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

// Handle form submission
async function onSubmit(event: FormSubmitEvent<Schema>) {
  emit('submit', event.data)
}

// Search entities for entity selection
const searchEntities = async (query: string) => {
  if (!query) {
    entityOptions.value = []
    return
  }

  loadingEntities.value = true
  try {
    // Set filters for search
    entitiesStore.setFilters({ search: query })
    await entitiesStore.fetchEntities()
    
    entityOptions.value = entitiesStore.entities.map(entity => ({
      value: entity.id,
      label: `${entity.display_name} (${entity.entity_type})`
    }))
  } catch (error) {
    console.error('Failed to search entities:', error)
    entityOptions.value = []
  } finally {
    loadingEntities.value = false
  }
}

// Watch entity search input
watchDebounced(entitySearch, (value) => {
  searchEntities(value)
}, { debounce: 300 })

// Watch is_global to clear entity_id when global is selected
watch(() => state.is_global, (isGlobal) => {
  if (isGlobal) {
    state.entity_id = ''
  }
})
</script>

<template>
  <UForm :schema="schema" :state="state" class="space-y-6" @submit="onSubmit">
    <!-- Basic Information -->
    <div class="space-y-4">
      <h3 class="text-lg font-semibold">Basic Information</h3>
      
      <!-- Name -->
      <UFormField name="name" :label="mode === 'edit' ? 'System Name (Read-only)' : 'System Name'" :description="mode === 'create' ? 'Unique identifier for the role (cannot be changed later)' : ''" :required="mode === 'create'">
        <UInput 
          v-model="state.name" 
          placeholder="admin_role"
          :disabled="mode === 'edit'"
          pattern="[a-zA-Z0-9_-]+"
        />
      </UFormField>

      <!-- Display Name -->
      <UFormField name="display_name" label="Display Name" required>
        <UInput 
          v-model="state.display_name" 
          placeholder="Administrator Role"
        />
      </UFormField>

      <!-- Description -->
      <UFormField name="description" label="Description">
        <UTextarea 
          v-model="state.description" 
          placeholder="Describe what this role is for..."
          rows="3"
        />
      </UFormField>
    </div>

    <!-- Scope Configuration -->
    <div class="space-y-4">
      <h3 class="text-lg font-semibold">Scope Configuration</h3>

      <!-- Is Global -->
      <UFormField name="is_global">
        <div class="flex items-center gap-3">
          <UCheckbox 
            v-model="state.is_global"
          />
          <div>
            <label class="font-medium">Global Role</label>
            <p class="text-sm text-muted-foreground">This role can be used across all entities</p>
          </div>
        </div>
      </UFormField>

      <!-- Entity Selection (if not global) -->
      <UFormField v-if="!state.is_global" name="entity_id" label="Owner Entity" description="The entity that owns this role">
        <USelectMenu
          v-model="state.entity_id"
          :options="entityOptions"
          :loading="loadingEntities"
          searchable
          @update:search="entitySearch = $event"
          placeholder="Select an entity..."
          value-attribute="value"
          option-attribute="label"
        >
          <template #empty>
            <div class="text-center py-2 text-sm text-muted-foreground">
              {{ entitySearch ? 'No entities found' : 'Type to search entities' }}
            </div>
          </template>
        </USelectMenu>
      </UFormField>

      <!-- Assignable At Types -->
      <UFormField name="assignable_at_types" label="Can Be Assigned At" description="Select entity types where this role can be assigned" required>
        <div class="space-y-2">
          <div v-for="option in assignableTypeOptions" :key="option.value" class="flex items-center gap-2">
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
            <label class="text-sm">{{ option.label }}</label>
          </div>
        </div>
      </UFormField>
    </div>

    <!-- Permissions -->
    <div class="space-y-4">
      <h3 class="text-lg font-semibold">Permissions</h3>
      
      <UFormField name="permissions" label="Permissions" description="Select permissions to grant with this role" required>
        <RolesPermissionSelector
          v-model="state.permissions"
          :entity-id="state.entity_id"
        />
      </UFormField>
    </div>

    <!-- Form Actions -->
    <div class="flex justify-end gap-2 pt-4">
      <UButton
        variant="outline"
        @click="emit('cancel')"
      >
        Cancel
      </UButton>
      <UButton
        type="submit"
      >
        {{ mode === 'create' ? 'Create Role' : 'Update Role' }}
      </UButton>
    </div>
  </UForm>
</template>