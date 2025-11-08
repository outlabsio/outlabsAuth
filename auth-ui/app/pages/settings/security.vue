<script setup lang="ts">
const authStore = useAuthStore()

// Password change form
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: ''
})

const isChangingPassword = ref(false)

const changePassword = async () => {
  isChangingPassword.value = true
  // Simulate API call
  await new Promise(resolve => setTimeout(resolve, 1000))
  isChangingPassword.value = false
  console.log('Password changed')
  // Reset form
  Object.assign(passwordForm, {
    current_password: '',
    new_password: '',
    confirm_password: ''
  })
}
</script>

<template>
  <UDashboardPanel id="settings-security">
    <template #header>
      <UDashboardNavbar title="Security Settings">
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
      <div class="max-w-2xl space-y-6">
        <!-- Change Password -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-key" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Change Password</h3>
            </div>
          </template>

          <UForm
            :state="passwordForm"
            class="space-y-4"
            @submit="changePassword"
          >
            <UFormField
              name="current_password"
              label="Current Password"
              required
            >
              <UInput
                v-model="passwordForm.current_password"
                type="password"
                icon="i-lucide-lock"
                placeholder="Enter current password"
              />
            </UFormField>

            <UFormField
              name="new_password"
              label="New Password"
              required
            >
              <UInput
                v-model="passwordForm.new_password"
                type="password"
                icon="i-lucide-lock"
                placeholder="Enter new password"
              />
            </UFormField>

            <UFormField
              name="confirm_password"
              label="Confirm New Password"
              required
            >
              <UInput
                v-model="passwordForm.confirm_password"
                type="password"
                icon="i-lucide-lock"
                placeholder="Confirm new password"
              />
            </UFormField>

            <div class="flex justify-end pt-2">
              <UButton
                type="submit"
                icon="i-lucide-save"
                label="Change Password"
                :loading="isChangingPassword"
              />
            </div>
          </UForm>
        </UCard>

        <!-- Two-Factor Authentication -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-shield" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Two-Factor Authentication</h3>
            </div>
          </template>

          <div class="space-y-4">
            <p class="text-sm text-muted">
              Add an extra layer of security to your account by enabling two-factor authentication.
            </p>

            <div class="flex items-center justify-between py-3 border-t border-default">
              <div>
                <p class="font-medium">Authenticator App</p>
                <p class="text-sm text-muted mt-1">Use an authenticator app to generate codes</p>
              </div>
              <UBadge color="neutral" variant="subtle">
                Not Enabled
              </UBadge>
            </div>

            <div class="flex items-center justify-between py-3 border-t border-default">
              <div>
                <p class="font-medium">SMS Authentication</p>
                <p class="text-sm text-muted mt-1">Receive codes via SMS</p>
              </div>
              <UBadge color="neutral" variant="subtle">
                Not Enabled
              </UBadge>
            </div>

            <div class="flex justify-end pt-2">
              <UButton
                icon="i-lucide-shield-plus"
                label="Enable 2FA"
                color="primary"
                variant="outline"
              />
            </div>
          </div>
        </UCard>

        <!-- Active Sessions -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-monitor" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Active Sessions</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div class="flex items-center justify-between py-3 border-b border-default">
              <div class="flex items-center gap-3">
                <UIcon name="i-lucide-monitor" class="w-8 h-8 text-primary" />
                <div>
                  <p class="font-medium">Current Session</p>
                  <p class="text-sm text-muted">Chrome on macOS • San Francisco, US</p>
                </div>
              </div>
              <UBadge color="success" variant="subtle">
                Active Now
              </UBadge>
            </div>

            <div class="flex items-center justify-between py-3">
              <div class="flex items-center gap-3">
                <UIcon name="i-lucide-smartphone" class="w-8 h-8 text-muted" />
                <div>
                  <p class="font-medium">Mobile Device</p>
                  <p class="text-sm text-muted">Safari on iOS • 2 hours ago</p>
                </div>
              </div>
              <UButton
                icon="i-lucide-log-out"
                label="Revoke"
                color="error"
                variant="ghost"
                size="xs"
              />
            </div>

            <div class="flex justify-end pt-2">
              <UButton
                icon="i-lucide-log-out"
                label="Revoke All Sessions"
                color="error"
                variant="outline"
              />
            </div>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
