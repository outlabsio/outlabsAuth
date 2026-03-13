<script setup lang="ts">
const authStore = useAuthStore()
const currentUser = computed(() => authStore.currentUser)
const runtimeConfig = useRuntimeConfig()

const uiVersion = computed(() => runtimeConfig.public.uiVersion)
const authLibraryVersion = computed(() => runtimeConfig.public.authLibraryVersion)
const releaseStage = computed(() => runtimeConfig.public.releaseStage)
const apiBaseUrl = computed(() => runtimeConfig.public.apiBaseUrl)

const enabledFeatures = computed(() => {
  const featureLabels: Record<string, string> = {
    entity_hierarchy: 'Entity Hierarchy',
    context_aware_roles: 'Context-Aware Roles',
    abac: 'ABAC Conditions',
    tree_permissions: 'Tree Permissions',
    api_keys: 'API Keys',
    user_status: 'User Status Controls',
    activity_tracking: 'Activity Tracking'
  }

  return Object.entries(authStore.features || {})
    .filter(([, enabled]) => Boolean(enabled))
    .map(([key]) => featureLabels[key] || key)
})

const accountDisplayName = computed(() => currentUser.value?.full_name || currentUser.value?.email || 'User')
const authPreset = computed(() => authStore.state.config?.preset || 'Unknown')
const canManageEntityTypes = computed(() => authStore.isEnterpriseRBAC && Boolean(currentUser.value?.is_superuser))

function formatDate(dateString?: string | null): string {
  if (!dateString) return 'Not available'

  return new Date(dateString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
}

function statusColor(status?: string): 'success' | 'warning' | 'error' | 'neutral' {
  if (status === 'active') return 'success'
  if (status === 'suspended') return 'warning'
  if (status === 'banned' || status === 'deleted') return 'error'
  return 'neutral'
}

function releaseStageColor(stage?: string): 'success' | 'warning' | 'error' | 'neutral' | 'primary' {
  if (!stage) return 'neutral'

  const normalized = stage.toLowerCase()
  if (normalized.includes('alpha')) return 'warning'
  if (normalized.includes('beta') || normalized.includes('preview')) return 'primary'
  if (normalized.includes('stable') || normalized.includes('ga')) return 'success'
  return 'neutral'
}
</script>

<template>
  <UDashboardPanel id="settings">
    <template #header>
      <UDashboardNavbar title="Settings">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-user-round" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Account Overview</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div>
              <label class="text-sm font-medium text-muted">Display Name</label>
              <p class="mt-1 text-base">{{ accountDisplayName }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Email</label>
              <p class="mt-1 text-base">{{ currentUser?.email || 'Not available' }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Account Status</label>
              <div class="mt-1 flex items-center gap-2">
                <UBadge
                  :color="statusColor(currentUser?.status)"
                  variant="subtle"
                >
                  {{ currentUser?.status || 'unknown' }}
                </UBadge>
                <UBadge
                  :color="currentUser?.email_verified ? 'success' : 'warning'"
                  variant="subtle"
                >
                  {{ currentUser?.email_verified ? 'Email verified' : 'Verification pending' }}
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

        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-shield-check" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Access &amp; Security</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div>
              <label class="text-sm font-medium text-muted">Last Login</label>
              <p class="mt-1 text-base">{{ formatDate(currentUser?.last_login) }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Last Activity</label>
              <p class="mt-1 text-base">{{ formatDate(currentUser?.last_activity) }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Last Password Change</label>
              <p class="mt-1 text-base">{{ formatDate(currentUser?.last_password_change) }}</p>
            </div>
          </div>

          <template #footer>
            <div class="flex flex-wrap justify-end gap-2">
              <UButton
                to="/settings/security"
                icon="i-lucide-shield"
                label="Security Overview"
                color="neutral"
                variant="outline"
              />
              <UButton
                to="/settings/password"
                icon="i-lucide-key"
                label="Change Password"
                color="neutral"
                variant="outline"
              />
              <UButton
                v-if="canManageEntityTypes"
                to="/settings/entity-types"
                icon="i-lucide-building-2"
                label="Entity Types"
                color="neutral"
                variant="outline"
              />
            </div>
          </template>
        </UCard>

        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-info" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Runtime Details</h3>
            </div>
          </template>

          <div class="space-y-4">
            <div>
              <label class="text-sm font-medium text-muted">Library Version</label>
              <p class="mt-1 text-base">OutlabsAuth {{ authLibraryVersion }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Admin UI Version</label>
              <p class="mt-1 text-base">{{ uiVersion }}</p>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Release Stage</label>
              <div class="mt-1">
                <UBadge
                  :color="releaseStageColor(releaseStage)"
                  variant="subtle"
                >
                  {{ releaseStage }}
                </UBadge>
              </div>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">Auth Preset</label>
              <div class="mt-1">
                <UBadge color="primary" variant="subtle">
                  {{ authPreset }}
                </UBadge>
              </div>
            </div>

            <div>
              <label class="text-sm font-medium text-muted">API Endpoint</label>
              <code class="block mt-1 text-xs bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded">
                {{ apiBaseUrl }}
              </code>
            </div>
          </div>
        </UCard>

        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-layers-3" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Enabled Capabilities</h3>
            </div>
          </template>

          <div class="space-y-4">
            <p class="text-sm text-muted">
              These capabilities are reported by the backend auth configuration and drive which admin surfaces are active.
            </p>

            <div
              v-if="enabledFeatures.length"
              class="flex flex-wrap gap-2"
            >
              <UBadge
                v-for="feature in enabledFeatures"
                :key="feature"
                color="neutral"
                variant="subtle"
              >
                {{ feature }}
              </UBadge>
            </div>

            <p v-else class="text-sm text-muted">
              No optional capabilities are enabled for this preset.
            </p>
          </div>
        </UCard>
      </div>
    </template>
  </UDashboardPanel>
</template>
