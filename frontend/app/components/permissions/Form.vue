<script setup lang="ts">
import * as z from 'zod'
import type { FormSubmitEvent } from '@nuxt/ui'
import type { Permission, Condition } from '~/types/auth.types'

const props = defineProps<{
  mode: 'create' | 'edit'
  permission?: Permission | null
}>()

const emit = defineEmits<{
  submit: [data: any]
  cancel: []
  delete: []
}>()

// Stores
const contextStore = useContextStore()
const permissionsStore = usePermissionsStore()

// State
const isLoading = ref(false)
const showConditions = ref(false)
const formRef = ref()

// Form validation schema
const schema = z.object({
  display_name: z.string()
    .min(3, 'Display name must be at least 3 characters')
    .max(200, 'Display name must be less than 200 characters'),
  description: z.string().max(500, 'Description must be less than 500 characters').optional(),
  resource: z.string()
    .min(1, 'Resource is required')
    .regex(/^[a-zA-Z0-9_-]+$/, 'Resource can only contain letters, numbers, underscores, and hyphens'),
  action: z.string()
    .min(1, 'Action is required')
    .regex(/^[a-zA-Z0-9_-]+$/, 'Action can only contain letters, numbers, underscores, and hyphens'),
  is_active: z.boolean().default(true),
  tags: z.array(z.string()).default([]),
  conditions: z.array(z.object({
    attribute: z.string().min(1, 'Attribute is required'),
    operator: z.string().min(1, 'Operator is required'),
    value: z.any()
  })).default([])
})

type Schema = z.output<typeof schema>

// Define the state type properly
interface FormState {
  display_name: string
  description?: string
  resource: string
  action: string
  is_active: boolean
  tags: string[]
  conditions: Condition[]
}

// Create reactive state initialized from props or store
const state = reactive<FormState>({
  display_name: '',
  description: '',
  resource: '',
  action: '',
  is_active: true,
  tags: [],
  conditions: []
})

// Initialize state when component mounts or props change
watchEffect(() => {
  if (props.mode === 'edit' && props.permission) {
    // Load from permission prop
    state.display_name = props.permission.display_name || ''
    state.description = props.permission.description || ''
    state.resource = props.permission.resource || ''
    state.action = props.permission.action || ''
    state.is_active = props.permission.is_active ?? true
    state.tags = [...(props.permission.tags || [])]
    state.conditions = [...(props.permission.conditions || [])]
    
    // Also update conditions visibility
    if (props.permission.conditions && props.permission.conditions.length > 0) {
      showConditions.value = true
    }
  } else if (props.mode === 'create') {
    // Reset to defaults for create mode
    state.display_name = ''
    state.description = ''
    state.resource = ''
    state.action = ''
    state.is_active = true
    state.tags = []
    state.conditions = []
    showConditions.value = false
  }
})

// Watch form state changes for debugging
watch(() => state.resource, (newVal) => {
  console.log('[Form] Resource in form state changed to:', newVal)
})
watch(() => state.action, (newVal) => {
  console.log('[Form] Action in form state changed to:', newVal)
})

// Computed
const isActive = computed({
  get: () => state.is_active ?? true,
  set: (value: boolean) => {
    state.is_active = value
  }
})

// Generate permission name from resource and action
const generatedName = computed(() => {
  if (state.resource && state.action) {
    return `${state.resource}:${state.action}`.toLowerCase()
  }
  return ''
})

// Handle form submission
async function onSubmit(event: FormSubmitEvent<Schema>) {
  isLoading.value = true

  try {
    const data: any = {
      name: generatedName.value,
      display_name: event.data.display_name,
      description: event.data.description,
      tags: event.data.tags,
      conditions: event.data.conditions,
      is_active: event.data.is_active
    }

    emit('submit', data)
  } finally {
    isLoading.value = false
  }
}

// Tag management
const tagInput = ref('')

function addTag() {
  if (tagInput.value && !state.tags?.includes(tagInput.value)) {
    state.tags = [...(state.tags || []), tagInput.value.toLowerCase()]
    tagInput.value = ''
  }
}

function removeTag(tag: string) {
  state.tags = state.tags?.filter(t => t !== tag) || []
}

// Condition management
function addCondition() {
  state.conditions = [...(state.conditions || []), {
    attribute: '',
    operator: 'EQUALS',
    value: ''
  }]
}

function removeCondition(index: number) {
  state.conditions = state.conditions?.filter((_, i) => i !== index) || []
}
</script>

<template>
  <UForm
    ref="formRef"
    :schema="schema"
    :state="state"
    :validate-on="[]"
    class="space-y-8"
    @submit="onSubmit"
  >
    <!-- Basic Information Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">
        Basic Information
      </h5>

      <!-- Display Name -->
      <UFormField
        label="Display Name"
        name="display_name"
        required
        class="w-full"
      >
        <UInput
          v-model="state.display_name"
          placeholder="e.g., Approve Invoices, Create Projects"
          size="lg"
          class="w-full"
        />
        <template #description>
          <span class="text-xs text-muted-foreground">A user-friendly name for this permission</span>
        </template>
      </UFormField>

      <!-- Resource & Action -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <UFormField
          label="Resource"
          name="resource"
          required
          class="w-full"
        >
          <PermissionsFieldCombobox
            v-model="state.resource"
            field-type="resource"
            placeholder="Select or type resource..."
          />
          <template #description>
            <span class="text-xs text-muted-foreground">The resource this permission applies to (lowercase, no spaces)</span>
          </template>
        </UFormField>

        <UFormField
          label="Action"
          name="action"
          required
          class="w-full"
        >
          <PermissionsFieldCombobox
            v-model="state.action"
            field-type="action"
            :selected-resource="state.resource"
            placeholder="Select or type action..."
          />
          <template #description>
            <span class="text-xs text-muted-foreground">The action allowed on the resource (lowercase, no spaces)</span>
          </template>
        </UFormField>
      </div>

      <!-- Generated Permission Name -->
      <div v-if="generatedName">
        <label class="text-sm font-medium text-muted-foreground">Generated Permission Name</label>
        <div class="mt-1 px-3 py-2 bg-neutral-100 dark:bg-neutral-800 rounded-md">
          <code class="text-sm font-mono">{{ generatedName }}</code>
        </div>
      </div>

      <!-- Description -->
      <UFormField label="Description" name="description" class="w-full">
        <UTextarea
          v-model="state.description"
          placeholder="Describe what this permission allows and when it should be used"
          :rows="3"
          class="w-full"
        />
      </UFormField>

      <!-- Tags -->
      <div>
        <label class="text-sm font-medium mb-2 block">Tags</label>
        <div class="space-y-2">
          <div class="flex gap-2">
            <UInput
              v-model="tagInput"
              placeholder="Add a tag..."
              size="sm"
              @keyup.enter="addTag"
            />
            <UButton
              size="sm"
              variant="outline"
              :disabled="!tagInput"
              @click="addTag"
            >
              Add
            </UButton>
          </div>
          <div v-if="state.tags && state.tags.length > 0" class="flex flex-wrap gap-2">
            <UBadge
              v-for="tag in state.tags"
              :key="tag"
              color="neutral"
              variant="subtle"
              size="sm"
              class="pr-1"
            >
              {{ tag }}
              <UButton
                size="2xs"
                variant="link"
                icon="i-lucide-x"
                class="ml-1"
                @click="removeTag(tag)"
              />
            </UBadge>
          </div>
        </div>
      </div>
    </div>

    <USeparator />

    <!-- Configuration Section -->
    <div class="space-y-6 w-full">
      <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">
        Configuration
      </h5>

      <!-- Status -->
      <UFormField name="is_active" class="w-full">
        <div class="flex items-center gap-3">
          <USwitch v-model="isActive" :color="isActive ? 'success' : 'neutral'" />
          <div>
            <span class="text-sm font-medium">Active</span>
            <p class="text-xs text-muted-foreground">
              {{ isActive ? 'Permission can be assigned to roles' : 'Permission is disabled and cannot be used' }}
            </p>
          </div>
        </div>
      </UFormField>

      <!-- Entity Scope (shown in context) -->
      <div v-if="!contextStore.isSystemContext && mode === 'create'">
        <label class="text-sm font-medium text-muted-foreground">Entity Scope</label>
        <p class="mt-1 text-sm">
          This permission will be created for: <strong>{{ contextStore.selectedOrganization?.name }}</strong>
        </p>
      </div>
    </div>

    <USeparator />

    <!-- Access Conditions Section -->
    <div class="space-y-6 w-full">
      <div class="flex items-center justify-between">
        <h5 class="text-sm font-medium uppercase tracking-wider text-primary-600 dark:text-primary-400">
          Access Conditions
          <span class="text-xs font-normal text-muted-foreground ml-2">(Optional)</span>
        </h5>
        <UButton
          v-if="!showConditions"
          size="sm"
          variant="outline"
          icon="i-lucide-plus"
          @click="showConditions = true"
        >
          Add Conditions
        </UButton>
      </div>

      <div v-if="showConditions" class="space-y-4">
        <p class="text-sm text-muted-foreground">
          Conditions allow you to set rules for when this permission is granted. All conditions must be true.
        </p>

        <!-- Conditions List -->
        <div v-if="state.conditions && state.conditions.length > 0" class="space-y-3">
          <PermissionsConditionBuilder
            v-for="(condition, index) in state.conditions"
            :key="index"
            :model-value="state.conditions[index]"
            :index="index"
            @update:model-value="(val) => {
              const newConditions = [...state.conditions]
              newConditions[index] = val
              state.conditions = newConditions
            }"
            @remove="removeCondition(index)"
          />
        </div>

        <!-- Add Condition Button -->
        <UButton
          variant="outline"
          icon="i-lucide-plus"
          size="sm"
          @click="addCondition"
        >
          Add Condition
        </UButton>
      </div>
    </div>

    <!-- Danger Zone - Only show in edit mode for custom permissions -->
    <div v-if="mode === 'edit' && props.permission && !props.permission.is_system" class="space-y-6 w-full">
      <USeparator />

      <div class="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-6">
        <div class="flex items-center gap-3 mb-4">
          <UIcon name="i-lucide-alert-triangle" class="h-5 w-5 text-red-600 dark:text-red-400" />
          <h3 class="font-semibold text-red-600 dark:text-red-400">
            Danger Zone
          </h3>
        </div>

        <div class="space-y-4">
          <div>
            <h4 class="font-medium">
              Delete this permission
            </h4>
            <p class="text-sm text-muted-foreground mt-1">
              Deleting a permission will remove it from all roles. This action cannot be undone.
            </p>
          </div>

          <UButton
            color="error"
            icon="i-lucide-trash"
            class="w-full"
            @click="emit('delete')"
          >
            Delete Permission
          </UButton>
        </div>
      </div>
    </div>
  </UForm>
</template>
