<script setup lang="ts">
const authStore = useAuthStore()
const toast = useToast()

const currentUser = computed(() => authStore.currentUser)
const isLoading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const formState = reactive({
  first_name: '',
  last_name: '',
  email: ''
})

watch(currentUser, (user) => {
  formState.first_name = user?.first_name || ''
  formState.last_name = user?.last_name || ''
  formState.email = user?.email || ''
}, { immediate: true })

const accountDisplayName = computed(() => currentUser.value?.full_name || currentUser.value?.email || 'User')

const hasChanges = computed(() => {
  return (
    formState.first_name !== (currentUser.value?.first_name || '') ||
    formState.last_name !== (currentUser.value?.last_name || '') ||
    formState.email !== (currentUser.value?.email || '')
  )
})

const isFormValid = computed(() => formState.email.trim().length > 0)

function formatDate(dateString?: string | null): string {
  if (!dateString) return 'Not available'

  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

function statusColor(status?: string): 'success' | 'warning' | 'error' | 'neutral' {
  if (status === 'active') return 'success'
  if (status === 'suspended') return 'warning'
  if (status === 'banned' || status === 'deleted') return 'error'
  return 'neutral'
}

function resetForm() {
  formState.first_name = currentUser.value?.first_name || ''
  formState.last_name = currentUser.value?.last_name || ''
  formState.email = currentUser.value?.email || ''
  errorMessage.value = ''
  successMessage.value = ''
}

async function onSubmit() {
  if (!isFormValid.value || !hasChanges.value) return

  isLoading.value = true
  errorMessage.value = ''
  successMessage.value = ''

  try {
    await authStore.apiCall('/v1/users/me', {
      method: 'PATCH',
      body: {
        first_name: formState.first_name.trim() || undefined,
        last_name: formState.last_name.trim() || undefined,
        email: formState.email.trim() || undefined
      }
    })

    await authStore.fetchCurrentUser()

    successMessage.value = 'Profile updated successfully.'
    toast.add({
      title: 'Profile updated',
      description: 'Your account profile was saved successfully.',
      color: 'success'
    })
  } catch (error: any) {
    if (Array.isArray(error?.data?.detail)) {
      errorMessage.value = error.data.detail
        .map((detail: { msg?: string }) => detail.msg || 'Invalid request')
        .join(', ')
    } else if (typeof error?.data?.detail === 'string') {
      errorMessage.value = error.data.detail
    } else if (error?.message) {
      errorMessage.value = error.message
    } else {
      errorMessage.value = 'Failed to update your profile.'
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <UDashboardPanel id="settings-profile">
    <template #header>
      <UDashboardNavbar title="Profile">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            to="/settings"
            icon="i-lucide-arrow-left"
            label="Back to Settings"
            color="neutral"
            variant="ghost"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_20rem] gap-6">
        <UCard>
          <template #header>
            <div class="flex items-center gap-4">
              <UAvatar
                :src="currentUser?.avatar_url || undefined"
                :alt="accountDisplayName"
                size="xl"
                icon="i-lucide-user"
              />
              <div class="space-y-1">
                <h2 class="text-lg font-semibold">{{ accountDisplayName }}</h2>
                <p class="text-sm text-muted">
                  Update the identity details used across the auth admin UI.
                </p>
              </div>
            </div>
          </template>

          <form class="space-y-6" @submit.prevent="onSubmit">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <UFormField
                name="first_name"
                label="First Name"
              >
                <UInput
                  v-model="formState.first_name"
                  icon="i-lucide-user"
                  placeholder="Jane"
                  size="lg"
                  :disabled="isLoading"
                />
              </UFormField>

              <UFormField
                name="last_name"
                label="Last Name"
              >
                <UInput
                  v-model="formState.last_name"
                  icon="i-lucide-user-round"
                  placeholder="Doe"
                  size="lg"
                  :disabled="isLoading"
                />
              </UFormField>
            </div>

            <UFormField
              name="email"
              label="Email Address"
              required
            >
              <UInput
                v-model="formState.email"
                type="email"
                icon="i-lucide-mail"
                placeholder="jane@example.com"
                size="lg"
                :disabled="isLoading"
              />
            </UFormField>

            <UAlert
              v-if="successMessage"
              color="success"
              variant="subtle"
              icon="i-lucide-check-circle"
              :title="successMessage"
            />

            <UAlert
              v-if="errorMessage"
              color="error"
              variant="subtle"
              icon="i-lucide-alert-circle"
              :title="errorMessage"
            />

            <div class="flex justify-end gap-3 pt-2">
              <UButton
                type="button"
                label="Reset"
                color="neutral"
                variant="outline"
                :disabled="isLoading || !hasChanges"
                @click="resetForm"
              />
              <UButton
                type="submit"
                icon="i-lucide-save"
                label="Save Profile"
                :loading="isLoading"
                :disabled="!isFormValid || !hasChanges"
              />
            </div>
          </form>
        </UCard>

        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-badge-info" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Account Context</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div>
              <label class="text-sm font-medium text-muted">Account Status</label>
              <div class="mt-1">
                <UBadge
                  :color="statusColor(currentUser?.status)"
                  variant="subtle"
                >
                  {{ currentUser?.status || 'unknown' }}
                </UBadge>
              </div>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Email Verification</label>
              <div class="mt-1">
                <UBadge
                  :color="currentUser?.email_verified ? 'success' : 'warning'"
                  variant="subtle"
                >
                  {{ currentUser?.email_verified ? 'Verified' : 'Pending' }}
                </UBadge>
              </div>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Root Entity</label>
              <p class="mt-1 text-base">
                {{ currentUser?.root_entity_name || currentUser?.root_entity_id || 'Unassigned' }}
              </p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Member Since</label>
              <p class="mt-1 text-base">{{ formatDate(currentUser?.created_at) }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Last Updated</label>
              <p class="mt-1 text-base">{{ formatDate(currentUser?.updated_at) }}</p>
            </div>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
