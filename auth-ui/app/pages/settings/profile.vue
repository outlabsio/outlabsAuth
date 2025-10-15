<script setup lang="ts">
const authStore = useAuthStore()
const currentUser = computed(() => authStore.currentUser)

// Form state
const formState = reactive({
  full_name: currentUser.value?.full_name || '',
  username: currentUser.value?.username || '',
  email: currentUser.value?.email || ''
})

const isLoading = ref(false)

const onSubmit = async () => {
  isLoading.value = true
  // Simulate API call
  await new Promise(resolve => setTimeout(resolve, 1000))
  isLoading.value = false
  // Show success toast
  console.log('Profile updated:', formState)
}
</script>

<template>
  <UDashboardPanel id="settings-profile">
    <template #header>
      <UDashboardNavbar title="Edit Profile">
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
      <div class="max-w-2xl">
        <UCard>
          <UForm
            :state="formState"
            class="space-y-6"
            @submit="onSubmit"
          >
            <!-- Avatar Section -->
            <div>
              <label class="block text-sm font-medium mb-2">Profile Picture</label>
              <div class="flex items-center gap-4">
                <UAvatar
                  :src="currentUser?.metadata?.avatar"
                  size="xl"
                  :alt="currentUser?.full_name"
                />
                <div class="flex gap-2">
                  <UButton
                    icon="i-lucide-upload"
                    label="Upload"
                    color="neutral"
                    variant="outline"
                    size="sm"
                  />
                  <UButton
                    icon="i-lucide-trash-2"
                    label="Remove"
                    color="error"
                    variant="ghost"
                    size="sm"
                  />
                </div>
              </div>
            </div>

            <UFormField
              name="full_name"
              label="Full Name"
              required
            >
              <UInput
                v-model="formState.full_name"
                icon="i-lucide-user"
                placeholder="Enter your full name"
                size="lg"
              />
            </UFormField>

            <UFormField
              name="username"
              label="Username"
              required
            >
              <UInput
                v-model="formState.username"
                icon="i-lucide-at-sign"
                placeholder="Enter your username"
                size="lg"
              />
            </UFormField>

            <UFormField
              name="email"
              label="Email Address"
              required
            >
              <UInput
                v-model="formState.email"
                type="email"
                icon="i-lucide-mail"
                placeholder="Enter your email"
                size="lg"
              />
            </UFormField>

            <!-- Additional Fields -->
            <UFormField
              name="department"
              label="Department"
            >
              <UInput
                :model-value="currentUser?.metadata?.department"
                icon="i-lucide-building"
                placeholder="Your department"
                size="lg"
              />
            </UFormField>

            <UFormField
              name="title"
              label="Job Title"
            >
              <UInput
                :model-value="currentUser?.metadata?.title"
                icon="i-lucide-briefcase"
                placeholder="Your job title"
                size="lg"
              />
            </UFormField>

            <div class="flex justify-end gap-3 pt-4">
              <UButton
                to="/settings"
                label="Cancel"
                color="neutral"
                variant="ghost"
              />
              <UButton
                type="submit"
                icon="i-lucide-save"
                label="Save Changes"
                :loading="isLoading"
              />
            </div>
          </UForm>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
