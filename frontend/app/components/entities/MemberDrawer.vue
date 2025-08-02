<script setup lang="ts">
import type { EntityMember } from '~/types/auth.types'

const props = defineProps<{
  member: EntityMember | null
  mode: 'create' | 'edit'
}>()

const emit = defineEmits<{
  created: []
  updated: []
}>()

// State
const open = defineModel<boolean>("open", { default: false })

// Store
const entityMembersStore = useEntityMembersStore()
const toast = useToast()

// State
const isSubmitting = ref(false)
const formRef = ref()
const isUpdatingStatus = ref(false)

// Computed
const title = computed(() => {
  switch (props.mode) {
    case 'create':
      return `Add Member to ${entityMembersStore.entityName}`
    case 'edit':
      return 'Update Member'
    default:
      return 'Member Details'
  }
})

// Methods
async function handleSubmit(data: any) {
  isSubmitting.value = true
  try {
    if (props.mode === 'create') {
      await entityMembersStore.createMember(data)
      emit('created')
      open.value = false
    } else if (props.mode === 'edit' && props.member) {
      await entityMembersStore.updateMember(props.member.user_id, data)
      emit('updated')
      open.value = false
    }
  } catch (error: any) {
    console.error('Failed to save member:', error)
    toast.add({
      title: "Error",
      description: error.data?.detail || error.message || `Failed to ${props.mode} member`,
      color: "error"
    })
  } finally {
    isSubmitting.value = false
  }
}

const submitForm = () => {
  // Trigger form submission
  if (formRef.value) {
    formRef.value.$el.dispatchEvent(new Event("submit", { bubbles: true }))
  }
}

const handleCancel = () => {
  open.value = false
}

const handleStatusToggle = async (newStatus: boolean) => {
  if (!props.member) return
  
  isUpdatingStatus.value = true
  try {
    await entityMembersStore.updateMember(props.member.user_id, {
      is_active: newStatus
    })
    // No need to show toast as the store handles it
  } catch (error: any) {
    console.error('Failed to update member status:', error)
    // Error toast is already handled by the store
  } finally {
    isUpdatingStatus.value = false
  }
}
</script>

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
        <div class="flex items-center gap-4">
          <h3 class="text-xl font-bold">
            {{ title }}
          </h3>
          <div v-if="mode === 'edit' && member" class="flex items-center gap-2">
            <USwitch 
              :model-value="member.is_active"
              @update:model-value="handleStatusToggle"
              :loading="isUpdatingStatus"
            />
            <span class="text-sm text-muted-foreground">
              {{ member.is_active ? 'Active' : 'Inactive' }}
            </span>
          </div>
        </div>
      </div>
    </template>

    <!-- Body -->
    <template #body>
      <div class="p-4">
        <!-- Form Content -->
        <EntitiesMemberForm
          ref="formRef"
          :member="props.member"
          :mode="props.mode"
          @submit="handleSubmit"
          @cancel="handleCancel"
        />
      </div>
    </template>

    <!-- Footer -->
    <template #footer>
      <div class="flex flex-col sm:flex-row gap-3 w-full">
        <UButton @click="handleCancel" color="neutral" variant="outline" class="justify-center flex-1"> 
          Cancel 
        </UButton>
        <UButton @click="submitForm" :loading="isSubmitting" color="primary" class="justify-center flex-1">
          {{ mode === "create" ? "Add Member" : "Update Member" }}
        </UButton>
      </div>
    </template>
  </UDrawer>
</template>