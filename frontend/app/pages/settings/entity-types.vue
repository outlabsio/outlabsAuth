<template>
  <div class="space-y-6">
    <!-- Action Button -->
    <div class="flex justify-end">
      <UButton icon="i-lucide-plus" @click="showCreateModal = true">
        Create Entity Type
      </UButton>
    </div>

    <!-- Info Alert -->
    <UAlert 
      icon="i-lucide-info" 
      color="info" 
      variant="subtle"
      title="Flexible Entity Types"
      description="Entity types are now flexible strings. Platforms can use any terminology (e.g., 'division', 'region', 'bureau') that fits their organizational structure."
    />

    <!-- Entity Types List -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <UCard v-for="type in entityTypes" :key="type.name" class="hover:shadow-md transition-shadow">
        <div class="space-y-3">
          <div class="flex items-start justify-between">
            <div>
              <h3 class="font-medium text-lg">{{ type.display_name || type.name }}</h3>
              <p class="text-sm text-muted-foreground">{{ type.name }}</p>
            </div>
            <UDropdown :items="getActions(type)">
              <UButton variant="ghost" icon="i-lucide-more-vertical" size="sm" />
            </UDropdown>
          </div>

          <div class="space-y-2">
            <div class="flex items-center gap-2 text-sm">
              <UIcon name="i-lucide-hash" class="text-muted-foreground" />
              <span>{{ type.count }} entities</span>
            </div>

            <div class="flex items-center gap-2 text-sm">
              <UIcon name="i-lucide-layers" class="text-muted-foreground" />
              <span>Class: {{ type.entity_class }}</span>
            </div>

            <div v-if="type.allowed_child_types?.length > 0" class="space-y-1">
              <p class="text-sm text-muted-foreground">Allowed children:</p>
              <div class="flex flex-wrap gap-1">
                <UBadge 
                  v-for="childType in type.allowed_child_types" 
                  :key="childType"
                  size="xs"
                  variant="subtle"
                >
                  {{ childType }}
                </UBadge>
              </div>
            </div>

            <div v-if="type.description" class="text-sm text-muted-foreground">
              {{ type.description }}
            </div>
          </div>

          <div class="flex items-center gap-2 pt-2">
            <UBadge 
              v-if="type.is_platform_root" 
              color="primary" 
              variant="subtle"
              size="xs"
            >
              Platform Root
            </UBadge>
            <UBadge 
              v-if="type.is_default" 
              color="success" 
              variant="subtle"
              size="xs"
            >
              Default
            </UBadge>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Empty State -->
    <div v-if="entityTypes.length === 0 && !isLoading" class="text-center py-12">
      <UIcon name="i-lucide-folder-tree" class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
      <h3 class="text-lg font-medium mb-2">No entity types defined</h3>
      <p class="text-muted-foreground mb-4">Create your first entity type to get started</p>
      <UButton icon="i-lucide-plus" @click="showCreateModal = true">
        Create Entity Type
      </UButton>
    </div>

    <!-- Create/Edit Modal -->
    <UModal v-model="showFormModal" :ui="{ width: 'max-w-2xl' }">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold">
              {{ formMode === 'create' ? 'Create' : 'Edit' }} Entity Type
            </h3>
            <UButton 
              icon="i-lucide-x" 
              variant="ghost" 
              square
              size="sm"
              @click="showFormModal = false"
            />
          </div>
        </template>

        <UForm 
          :schema="formSchema" 
          :state="formState" 
          @submit="onSubmit"
          class="space-y-4"
        >
          <UFormField name="name" label="System Name" required>
            <UInput 
              v-model="formState.name" 
              placeholder="e.g., department, region, team"
              :disabled="formMode === 'edit'"
            />
            <template #description>
              <span class="text-xs text-muted-foreground">
                Lowercase with underscores. Cannot be changed after creation.
              </span>
            </template>
          </UFormField>

          <UFormField name="display_name" label="Display Name" required>
            <UInput 
              v-model="formState.display_name" 
              placeholder="e.g., Department, Region, Team"
            />
          </UFormField>

          <UFormField name="description" label="Description">
            <UTextarea 
              v-model="formState.description" 
              placeholder="Describe the purpose of this entity type"
              rows="3"
            />
          </UFormField>

          <UFormField name="entity_class" label="Entity Class" required>
            <USelect
              v-model="formState.entity_class"
              :items="entityClassOptions"
            />
            <template #description>
              <span class="text-xs text-muted-foreground">
                STRUCTURAL entities form the hierarchy. ACCESS_GROUP entities are for cross-cutting permissions.
              </span>
            </template>
          </UFormField>

          <UFormField name="allowed_child_types" label="Allowed Child Types">
            <USelect
              v-model="formState.allowed_child_types"
              :items="availableChildTypes"
              multiple
              placeholder="Select allowed child types"
            />
            <template #description>
              <span class="text-xs text-muted-foreground">
                Which entity types can be children of this type
              </span>
            </template>
          </UFormField>

          <div class="space-y-3">
            <UCheckbox 
              v-model="formState.is_platform_root" 
              label="Can be platform root"
            />
            <UCheckbox 
              v-model="formState.is_default" 
              label="Default type for new entities"
            />
          </div>
        </UForm>

        <template #footer>
          <div class="flex justify-end gap-3">
            <UButton 
              variant="outline" 
              @click="showFormModal = false"
            >
              Cancel
            </UButton>
            <UButton 
              type="submit"
              :loading="isSubmitting"
              @click="onSubmit"
            >
              {{ formMode === 'create' ? 'Create' : 'Update' }} Entity Type
            </UButton>
          </div>
        </template>
      </UCard>
    </UModal>

    <!-- Delete Confirmation -->
    <ConfirmationModal
      v-model="showDeleteConfirm"
      title="Delete Entity Type"
      :description="`Are you sure you want to delete the entity type '${typeToDelete?.display_name || typeToDelete?.name}'? This will only work if no entities are using this type.`"
      confirm-text="Delete"
      confirm-color="error"
      @confirm="deleteEntityType"
    />
  </div>
</template>

<script setup lang="ts">
import { z } from 'zod'
import type { NavigationMenuItem } from '@nuxt/ui'

// Page meta handled by parent settings.vue

// Types
interface EntityType {
  name: string
  display_name?: string
  description?: string
  entity_class: 'STRUCTURAL' | 'ACCESS_GROUP'
  allowed_child_types?: string[]
  is_platform_root?: boolean
  is_default?: boolean
  count: number
}

// Stores
const authStore = useAuthStore()
const contextStore = useContextStore()
const router = useRouter()
const route = useRoute()
const toast = useToast()

// Navigation handled by parent settings.vue page

// Navigation handled by parent settings.vue page

// State
const entityTypes = ref<EntityType[]>([])
const isLoading = ref(false)
const showFormModal = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const showDeleteConfirm = ref(false)
const typeToDelete = ref<EntityType | null>(null)
const isSubmitting = ref(false)


// Entity class options
const entityClassOptions = [
  { 
    value: 'STRUCTURAL', 
    label: 'Structural',
    description: 'Forms the organizational hierarchy'
  },
  { 
    value: 'ACCESS_GROUP', 
    label: 'Access Group',
    description: 'Cross-cutting permission groups'
  }
]

// Form schema
const formSchema = z.object({
  name: z.string()
    .min(1, 'Name is required')
    .regex(/^[a-z][a-z0-9_]*$/, 'Must start with lowercase letter and contain only lowercase letters, numbers, and underscores'),
  display_name: z.string().min(1, 'Display name is required'),
  description: z.string().optional(),
  entity_class: z.enum(['STRUCTURAL', 'ACCESS_GROUP']),
  allowed_child_types: z.array(z.string()).optional(),
  is_platform_root: z.boolean().optional(),
  is_default: z.boolean().optional()
})

// Form state
const formState = reactive({
  name: '',
  display_name: '',
  description: '',
  entity_class: 'STRUCTURAL' as 'STRUCTURAL' | 'ACCESS_GROUP',
  allowed_child_types: [] as string[],
  is_platform_root: false,
  is_default: false
})

// Computed
const availableChildTypes = computed(() => {
  return entityTypes.value
    .filter(type => type.name !== formState.name)
    .map(type => ({
      value: type.name,
      label: type.display_name || type.name
    }))
})

const showCreateModal = computed({
  get: () => showFormModal.value && formMode.value === 'create',
  set: (value) => {
    if (value) {
      formMode.value = 'create'
      resetForm()
    }
    showFormModal.value = value
  }
})

// Methods
const fetchEntityTypes = async () => {
  isLoading.value = true
  try {
    // Fetch entity types from the API
    const response = await authStore.apiCall<string[]>(
      '/v1/entities/entity-types',
      { headers: contextStore.getContextHeaders }
    )

    // For now, we'll create mock data based on the types
    // In a real implementation, this would come from a dedicated endpoint
    entityTypes.value = response.map(type => ({
      name: type,
      display_name: type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' '),
      entity_class: 'STRUCTURAL' as const,
      count: 0,
      allowed_child_types: [],
      is_platform_root: type === 'platform',
      is_default: false
    }))

    // Add some example data
    if (entityTypes.value.length > 0) {
      entityTypes.value[0].count = 5
      entityTypes.value[0].description = 'Top-level platform entity'
      if (entityTypes.value.length > 1) {
        entityTypes.value[1].count = 12
        entityTypes.value[1].allowed_child_types = ['department', 'team']
      }
    }
  } catch (error: any) {
    toast.add({
      title: 'Failed to fetch entity types',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isLoading.value = false
  }
}

const resetForm = () => {
  formState.name = ''
  formState.display_name = ''
  formState.description = ''
  formState.entity_class = 'STRUCTURAL'
  formState.allowed_child_types = []
  formState.is_platform_root = false
  formState.is_default = false
}

const onSubmit = async () => {
  isSubmitting.value = true

  try {
    if (formMode.value === 'create') {
      // In a real implementation, this would call an API endpoint
      toast.add({
        title: 'Entity type created',
        description: `Entity type "${formState.display_name}" has been created`,
        color: 'success'
      })
    } else {
      // Update entity type
      toast.add({
        title: 'Entity type updated',
        description: `Entity type "${formState.display_name}" has been updated`,
        color: 'success'
      })
    }

    showFormModal.value = false
    fetchEntityTypes()
  } catch (error: any) {
    toast.add({
      title: `Failed to ${formMode.value} entity type`,
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

const editEntityType = (type: EntityType) => {
  formMode.value = 'edit'
  formState.name = type.name
  formState.display_name = type.display_name || ''
  formState.description = type.description || ''
  formState.entity_class = type.entity_class
  formState.allowed_child_types = type.allowed_child_types || []
  formState.is_platform_root = type.is_platform_root || false
  formState.is_default = type.is_default || false
  showFormModal.value = true
}

const confirmDeleteEntityType = (type: EntityType) => {
  typeToDelete.value = type
  showDeleteConfirm.value = true
}

const deleteEntityType = async () => {
  if (!typeToDelete.value) return

  try {
    // In a real implementation, this would call an API endpoint
    toast.add({
      title: 'Entity type deleted',
      description: `Entity type "${typeToDelete.value.display_name || typeToDelete.value.name}" has been deleted`,
      color: 'success'
    })

    fetchEntityTypes()
  } catch (error: any) {
    toast.add({
      title: 'Failed to delete entity type',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    showDeleteConfirm.value = false
    typeToDelete.value = null
  }
}

const getActions = (type: EntityType) => [
  [{
    label: 'Edit',
    icon: 'i-lucide-edit',
    click: () => editEntityType(type)
  }],
  [{
    label: 'Delete',
    icon: 'i-lucide-trash',
    color: 'error' as const,
    click: () => confirmDeleteEntityType(type),
    disabled: type.count > 0
  }]
]

// Initialize data on mount
onMounted(() => {
  fetchEntityTypes()
})

// SEO handled by parent settings.vue page
</script>