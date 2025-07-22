<template>
  <UModal v-model="isOpen" :ui="{ width: 'max-w-4xl' }">
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold">
            {{ mode === 'create' ? 'Create User' : 'Edit User' }}
          </h3>
          <UButton 
            icon="i-lucide-x" 
            variant="ghost" 
            square
            size="sm"
            @click="isOpen = false"
          />
        </div>
      </template>

      <div class="px-1">
        <UserForm
          :mode="mode"
          :user="user"
          @submit="handleSubmit"
          @cancel="isOpen = false"
        />
      </div>

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
            @click="submitForm"
          >
            {{ mode === 'create' ? 'Create User' : 'Update User' }}
          </UButton>
        </div>
      </template>
    </UCard>
  </UModal>
</template>

<script setup lang="ts">
import type { User, UserCreateRequest, UserUpdateRequest } from '~/types/auth.types'

const props = defineProps<{
  modelValue: boolean
  mode: 'create' | 'edit'
  user?: User | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'saved': []
}>()

// Model binding
const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Stores
const authStore = useAuthStore()
const contextStore = useContextStore()
const toast = useToast()

// State
const isSubmitting = ref(false)
const formRef = ref<any>(null)

// Methods
const handleSubmit = async (data: UserCreateRequest | UserUpdateRequest) => {
  isSubmitting.value = true

  try {
    if (props.mode === 'create') {
      await authStore.apiCall('/v1/users', {
        method: 'POST',
        body: data,
        headers: contextStore.getContextHeaders
      })

      toast.add({
        title: 'User created',
        description: 'User has been successfully created',
        color: 'success'
      })
    } else if (props.user) {
      await authStore.apiCall(`/v1/users/${props.user.id}`, {
        method: 'PUT',
        body: data,
        headers: contextStore.getContextHeaders
      })

      toast.add({
        title: 'User updated',
        description: 'User has been successfully updated',
        color: 'success'
      })
    }

    emit('saved')
    isOpen.value = false
  } catch (error: any) {
    toast.add({
      title: `Failed to ${props.mode} user`,
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

// Submit form programmatically
const submitForm = () => {
  // Find the form submit button and click it
  const form = document.querySelector('form')
  if (form) {
    const submitEvent = new Event('submit', { bubbles: true, cancelable: true })
    form.dispatchEvent(submitEvent)
  }
}
</script>