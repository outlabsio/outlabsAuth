<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Entity } from '~/types/auth.types'

interface Props {
  entity?: Entity | null
  mode: 'create' | 'edit'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  submit: [data: Partial<Entity>]
  cancel: []
}>()

// Schema
const schema = z.object({
  name: z.string()
    .min(1, 'Name is required')
    .regex(/^[a-z0-9_]+$/, 'Name must be lowercase with underscores only'),
  display_name: z.string().min(1, 'Display name is required'),
  entity_class: z.enum(['STRUCTURAL', 'ACCESS_GROUP']),
  entity_type: z.string().min(1, 'Entity type is required'),
  description: z.string().optional(),
  status: z.enum(['active', 'inactive'])
})

type Schema = z.output<typeof schema>

// State
const state = reactive<Partial<Schema>>({
  name: props.entity?.name || '',
  display_name: props.entity?.display_name || '',
  entity_class: props.entity?.entity_class || 'STRUCTURAL',
  entity_type: props.entity?.entity_type || '',
  description: props.entity?.description || '',
  status: props.entity?.status || 'active'
})

// Fetch entity types for autocomplete
const entitiesStore = useEntitiesStore()
const { data: entityTypes } = await useAsyncData('entity-types', () => entitiesStore.fetchEntityTypes())

// Entity class options
const entityClassOptions = [
  { 
    label: 'Structural', 
    value: 'STRUCTURAL',
    description: 'Forms organizational hierarchy',
    icon: 'i-lucide-building'
  },
  { 
    label: 'Access Group', 
    value: 'ACCESS_GROUP',
    description: 'Cross-cutting permission groups',
    icon: 'i-lucide-users'
  }
]

// Status options
const statusOptions = [
  { label: 'Active', value: 'active', color: 'green' },
  { label: 'Inactive', value: 'inactive', color: 'gray' }
]

// Computed
const entityTypeOptions = computed(() => {
  if (!entityTypes.value || !Array.isArray(entityTypes.value)) return []
  return entityTypes.value.map(type => ({
    label: type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' '),
    value: type
  }))
})

// Watch for entity changes
watch(() => props.entity, (newEntity) => {
  if (newEntity) {
    state.name = newEntity.name
    state.display_name = newEntity.display_name
    state.entity_class = newEntity.entity_class
    state.entity_type = newEntity.entity_type
    state.description = newEntity.description || ''
    state.status = newEntity.status
  }
}, { immediate: true })

// Methods
async function onSubmit(event: FormSubmitEvent<Schema>) {
  emit('submit', event.data)
}
</script>

<template>
  <UForm :schema="schema" :state="state" @submit="onSubmit" class="space-y-6">
    <!-- Entity Class -->
    <UFormField label="Entity Class" name="entity_class" required>
      <URadioGroup 
        v-model="state.entity_class"
        :options="entityClassOptions"
        :disabled="mode === 'edit'"
      >
        <template #label="{ option }">
          <div class="flex items-center gap-2">
            <UIcon :name="option.icon" class="h-4 w-4" />
            <span>{{ option.label }}</span>
          </div>
        </template>
        <template #description="{ option }">
          <span class="text-xs">{{ option.description }}</span>
        </template>
      </URadioGroup>
    </UFormField>

    <!-- System Name -->
    <UFormField 
      label="System Name" 
      name="name" 
      description="Lowercase with underscores (e.g., 'my_entity')"
      required
    >
      <UInput 
        v-model="state.name" 
        placeholder="system_name"
        :disabled="mode === 'edit'"
      />
    </UFormField>

    <!-- Display Name -->
    <UFormField 
      label="Display Name" 
      name="display_name"
      required
    >
      <UInput 
        v-model="state.display_name" 
        placeholder="Human-friendly name"
      />
    </UFormField>

    <!-- Entity Type -->
    <UFormField 
      label="Entity Type" 
      name="entity_type"
      description="Use existing types for consistency or create a new one"
      required
    >
      <UInputMenu
        v-model="state.entity_type"
        :options="entityTypeOptions"
        placeholder="Select or type entity type..."
        :popper="{ placement: 'bottom-start' }"
      />
    </UFormField>

    <!-- Description -->
    <UFormField 
      label="Description" 
      name="description"
    >
      <UTextarea 
        v-model="state.description" 
        placeholder="Optional description"
        :rows="3"
      />
    </UFormField>

    <!-- Status -->
    <UFormField 
      label="Status" 
      name="status"
      required
    >
      <USelectMenu 
        v-model="state.status"
        :options="statusOptions"
        value-attribute="value"
        option-attribute="label"
      >
        <template #option="{ option }">
          <UBadge :color="option.color" variant="subtle" size="xs">
            {{ option.label }}
          </UBadge>
        </template>
      </USelectMenu>
    </UFormField>

    <!-- Actions -->
    <div class="flex justify-end gap-3 pt-4">
      <UButton 
        @click="emit('cancel')"
        variant="outline"
        type="button"
      >
        Cancel
      </UButton>
      <UButton type="submit">
        {{ mode === 'create' ? 'Create' : 'Update' }} Entity
      </UButton>
    </div>
  </UForm>
</template>