<script setup lang="ts">
import { useInviteUserMutation } from '~/queries/users'

const open = defineModel<boolean>('open', { default: false })

// Form state
const state = reactive({
  email: '',
  first_name: '',
  last_name: '',
})

// Mutation for inviting users
const { mutate: inviteUser, isLoading: isSubmitting } = useInviteUserMutation()

// Submit handler
async function handleSubmit() {
  try {
    await inviteUser(state)
    // Close modal and reset form on success
    open.value = false
    Object.assign(state, {
      email: '',
      first_name: '',
      last_name: '',
    })
  } catch (error) {
    // Error handling is done by the mutation
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    title="Invite User"
    description="Send an invitation to join your organization"
  >
    <template #body>
      <div class="space-y-4">
        <UAlert
          color="info"
          variant="subtle"
          icon="i-lucide-mail"
          title="They'll receive a link to set their password"
        />

        <!-- Email -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Email <span class="text-error">*</span></label>
          <UInput
            v-model="state.email"
            type="email"
            placeholder="jane@example.com"
            icon="i-lucide-mail"
            required
          />
        </div>

        <!-- Grid layout for names -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="block text-sm font-medium">First Name</label>
            <UInput
              v-model="state.first_name"
              placeholder="Jane"
              icon="i-lucide-user"
            />
          </div>

          <div class="space-y-2">
            <label class="block text-sm font-medium">Last Name</label>
            <UInput
              v-model="state.last_name"
              placeholder="Smith"
              icon="i-lucide-user"
            />
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          label="Cancel"
          color="neutral"
          variant="outline"
          @click="open = false"
          :disabled="isSubmitting"
        />
        <UButton
          label="Send Invite"
          icon="i-lucide-send"
          :loading="isSubmitting"
          :disabled="!state.email"
          @click="handleSubmit"
        />
      </div>
    </template>
  </UModal>
</template>
