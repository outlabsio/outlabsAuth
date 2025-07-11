<template>
  <UDrawer
    v-model:open="open"
    direction="right"
    :ui="{
      content: 'w-full max-w-2xl',
      header: 'sticky top-0 z-10',
      body: 'overflow-y-auto',
    }"
  >
    <!-- Header -->
    <template #header>
      <div class="flex justify-between items-center w-full">
        <h3 class="text-xl font-bold">
          {{ mode === 'create' ? 'Create Entity' : mode === 'edit' ? 'Edit Entity' : 'Entity Details' }}
        </h3>
      </div>
    </template>

    <!-- Body -->
    <template #body>
      <div class="p-4">
        <!-- View Mode -->
        <div v-if="mode === 'view' && entity" class="space-y-6">
          <!-- Entity Header -->
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-3">
              <UIcon 
                :name="entity.entity_class === 'STRUCTURAL' ? 'i-lucide-building' : 'i-lucide-users'"
                class="h-8 w-8 text-primary"
              />
              <div>
                <h2 class="text-2xl font-bold">{{ entity.display_name || entity.name }}</h2>
                <p class="text-sm text-gray-600 dark:text-gray-400">
                  {{ entity.entity_type.replace(/_/g, ' ') }}
                </p>
              </div>
            </div>
            <UBadge 
              :color="entity.status === 'active' ? 'green' : 'gray'"
              variant="subtle"
            >
              {{ entity.status }}
            </UBadge>
          </div>

          <!-- Entity Details -->
          <div class="grid grid-cols-1 gap-4">
            <div>
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">System Name</h4>
              <p class="mt-1">{{ entity.name }}</p>
            </div>

            <div v-if="entity.description">
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Description</h4>
              <p class="mt-1">{{ entity.description }}</p>
            </div>

            <div>
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Entity Class</h4>
              <p class="mt-1">{{ entity.entity_class }}</p>
            </div>

            <div>
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Created</h4>
              <p class="mt-1">{{ new Date(entity.created_at).toLocaleString() }}</p>
            </div>

            <div v-if="entity.updated_at">
              <h4 class="text-sm font-medium text-gray-500 dark:text-gray-400">Updated</h4>
              <p class="mt-1">{{ new Date(entity.updated_at).toLocaleString() }}</p>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-3 pt-4 border-t">
            <UButton @click="startEdit" icon="i-lucide-edit">
              Edit Entity
            </UButton>
            <UButton 
              @click="confirmDelete" 
              color="red" 
              variant="outline"
              icon="i-lucide-trash"
            >
              Delete
            </UButton>
          </div>
        </div>

        <!-- Create/Edit Mode -->
        <div v-else-if="mode === 'create' || mode === 'edit'">
          <EntityForm
            :entity="entity"
            :mode="mode"
            @submit="handleSubmit"
            @cancel="handleCancel"
          />
        </div>
      </div>
    </template>
  </UDrawer>
</template>

<script setup lang="ts">
import type { Entity } from '~/types/auth.types'

interface Props {
  entity?: Entity | null
  mode?: 'view' | 'create' | 'edit'
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'view'
})

const emit = defineEmits<{
  created: [entity: Entity]
  updated: [entity: Entity]
  deleted: [id: string]
}>()

// State
const open = defineModel<boolean>('open', { default: false })
const currentMode = ref(props.mode)
const toast = useToast()
const entitiesStore = useEntitiesStore()

// Watch for prop changes
watch(() => props.mode, (newMode) => {
  currentMode.value = newMode
})

watch(() => props.entity, (newEntity) => {
  if (newEntity && currentMode.value === 'view') {
    // Entity changed, ensure we're in view mode
    currentMode.value = 'view'
  }
})

// Computed
const mode = computed(() => currentMode.value)
const entity = computed(() => props.entity)

// Methods
const startEdit = () => {
  currentMode.value = 'edit'
}

const handleCancel = () => {
  if (props.mode === 'create') {
    open.value = false
  } else {
    currentMode.value = 'view'
  }
}

const handleSubmit = async (data: Partial<Entity>) => {
  try {
    if (mode.value === 'create') {
      const newEntity = await entitiesStore.createEntity(data)
      toast.add({
        title: 'Success',
        description: 'Entity created successfully',
        color: 'green'
      })
      emit('created', newEntity)
      open.value = false
    } else if (mode.value === 'edit' && entity.value) {
      const updatedEntity = await entitiesStore.updateEntity(entity.value.id, data)
      toast.add({
        title: 'Success',
        description: 'Entity updated successfully',
        color: 'green'
      })
      emit('updated', updatedEntity)
      currentMode.value = 'view'
    }
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.data?.detail || error.message || 'Operation failed',
      color: 'red'
    })
  }
}

const confirmDelete = () => {
  if (!entity.value) return
  
  // TODO: Add confirmation modal
  deleteEntity()
}

const deleteEntity = async () => {
  if (!entity.value) return
  
  try {
    await entitiesStore.deleteEntity(entity.value.id)
    toast.add({
      title: 'Success',
      description: 'Entity deleted successfully',
      color: 'green'
    })
    emit('deleted', entity.value.id)
    open.value = false
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.data?.detail || error.message || 'Failed to delete entity',
      color: 'red'
    })
  }
}
</script>