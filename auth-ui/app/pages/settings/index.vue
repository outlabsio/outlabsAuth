<script setup lang="ts">
const authStore = useAuthStore()
const currentUser = computed(() => authStore.currentUser)
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <UDashboardNavbar title="General Settings">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Account Information -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-user" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Account Information</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div>
              <label class="text-sm font-medium text-muted">Full Name</label>
              <p class="mt-1 text-base">{{ currentUser?.full_name || 'N/A' }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Email</label>
              <p class="mt-1 text-base">{{ currentUser?.email }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Username</label>
              <p class="mt-1 text-base">@{{ currentUser?.username }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Account Status</label>
              <div class="mt-1">
                <UBadge
                  :color="currentUser?.is_active ? 'green' : 'red'"
                  variant="subtle"
                >
                  {{ currentUser?.is_active ? 'Active' : 'Inactive' }}
                </UBadge>
                <UBadge
                  v-if="currentUser?.is_superuser"
                  color="purple"
                  variant="subtle"
                  class="ml-2"
                >
                  Superuser
                </UBadge>
              </div>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Member Since</label>
              <p class="mt-1 text-base text-muted">
                {{ new Date(currentUser?.created_at || '').toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) }}
              </p>
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <UButton
                to="/settings/profile"
                icon="i-lucide-pencil"
                label="Edit Profile"
                color="neutral"
                variant="outline"
              />
            </div>
          </template>
        </UCard>

        <!-- Application Settings -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-settings" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Application Settings</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium">API Mode</label>
                <p class="text-sm text-muted mt-1">Using mock data for development</p>
              </div>
              <UBadge color="warning" variant="subtle">
                Mock Mode
              </UBadge>
            </div>

            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium">Email Notifications</label>
                <p class="text-sm text-muted mt-1">Receive email updates</p>
              </div>
              <UToggle />
            </div>

            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium">Two-Factor Authentication</label>
                <p class="text-sm text-muted mt-1">Add an extra layer of security</p>
              </div>
              <UButton
                icon="i-lucide-shield"
                label="Enable"
                color="neutral"
                variant="outline"
                size="xs"
              />
            </div>
          </div>

          <template #footer>
            <div class="flex justify-end">
              <UButton
                to="/settings/security"
                icon="i-lucide-shield"
                label="Security Settings"
                color="neutral"
                variant="outline"
              />
            </div>
          </template>
        </UCard>

        <!-- System Information -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-info" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">System Information</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div>
              <label class="text-sm font-medium text-muted">Version</label>
              <p class="mt-1 text-base">OutlabsAuth v1.0.0</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Environment</label>
              <UBadge color="blue" variant="subtle" class="mt-1">
                Development
              </UBadge>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">API Endpoint</label>
              <code class="block mt-1 text-xs bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded">
                http://localhost:8000
              </code>
            </div>
          </div>
        </UCard>

        <!-- Danger Zone -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-alert-triangle" class="w-5 h-5 text-error" />
              <h3 class="text-lg font-semibold text-error">Danger Zone</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div>
              <h4 class="text-sm font-medium">Delete Account</h4>
              <p class="text-sm text-muted mt-1">
                Permanently delete your account and all associated data. This action cannot be undone.
              </p>
              <UButton
                icon="i-lucide-trash-2"
                label="Delete Account"
                color="error"
                variant="outline"
                size="sm"
                class="mt-2"
              />
            </div>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
