<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { permissionsQueries } from '~/queries/permissions'
import { apiKeysQueries, useUpdateApiKeyMutation } from '~/queries/api-keys'
import { ApiKeyStatus } from '~/types/api-key'
import type { UpdateApiKeyRequest } from '~/types/api-key'
import type { UiColor } from '~/types/ui'

const props = defineProps<{
  keyId: string
}>()

const open = defineModel<boolean>('open', { default: false })

// Fetch available permissions dynamically
const { data: permissions, isLoading: loadingPermissions } = useQuery(permissionsQueries.available())

// Fetch existing API key data when modal opens
const { data: existingKey, isLoading: isLoadingKey } = useQuery(() => ({
  ...apiKeysQueries.detail(props.keyId),
  enabled: open.value && !!props.keyId
}))

// Available scopes computed from permissions
const availableScopes = computed(() => {
  if (!permissions.value) return []

  // Add "All Permissions" option
  const allPermissions = {
    value: '*:*',
    label: 'All Permissions',
    description: '⚠️ Full access to all resources - use with caution'
  }

  // Map permissions to scope options
  const scopeOptions = permissions.value.map(p => ({
    value: p.name,
    label: p.display_name || p.name,
    description: p.description || ''
  }))

  return [allPermissions, ...scopeOptions]
})

// Status options
const statusOptions: { value: ApiKeyStatus; label: string; description: string; color: UiColor }[] = [
  { value: ApiKeyStatus.ACTIVE, label: 'Active', description: 'Key is operational', color: 'success' },
  { value: ApiKeyStatus.SUSPENDED, label: 'Suspended', description: 'Temporarily disabled', color: 'warning' },
  { value: ApiKeyStatus.REVOKED, label: 'Revoked', description: 'Permanently disabled (cannot be reversed)', color: 'error' }
]

interface ApiKeyUpdateForm {
  name: string
  description: string
  scopes: string[]
  ip_whitelist: string[]
  ip_whitelist_raw: string
  rate_limit_per_minute: number
  status: ApiKeyStatus
}

function buildInitialState(): ApiKeyUpdateForm {
  return {
    name: '',
    description: '',
    scopes: [],
    ip_whitelist: [],
    ip_whitelist_raw: '',
    rate_limit_per_minute: 60,
    status: ApiKeyStatus.ACTIVE
  }
}

// Form state
const state = reactive<ApiKeyUpdateForm>(buildInitialState())

// Pre-populate form when key data loads
watch(existingKey, (key) => {
  if (key) {
    state.name = key.name
    state.description = key.description || ''
    state.scopes = key.scopes || []
    state.ip_whitelist = key.ip_whitelist || []
    state.ip_whitelist_raw = (key.ip_whitelist || []).join('\n')
    state.rate_limit_per_minute = key.rate_limit_per_minute
    state.status = key.status
  } else {
    Object.assign(state, buildInitialState())
  }
}, { immediate: true })

// Watch IP whitelist raw input
watch(() => state.ip_whitelist_raw, (raw) => {
  if (raw.trim()) {
    state.ip_whitelist = raw
      .split(/[\n,]+/)
      .map(ip => ip.trim())
      .filter(ip => ip.length > 0)
  } else {
    state.ip_whitelist = []
  }
})

// Update mutation
const { mutateAsync: updateKey, isLoading: isSubmitting } = useUpdateApiKeyMutation()

// Submit handler
async function handleSubmit() {
  try {
    // Build update payload (only send changed fields)
    const payload: UpdateApiKeyRequest = {
      name: state.name,
      description: state.description || undefined,
      scopes: state.scopes.length > 0 ? [...state.scopes] : undefined,
      ip_whitelist: state.ip_whitelist.length > 0 ? [...state.ip_whitelist] : undefined,
      rate_limit_per_minute: state.rate_limit_per_minute,
      status: state.status,
    }

    await updateKey({ id: props.keyId, data: payload })

    // Close modal on success
    open.value = false
  } catch (error) {
    // Error handling is done by the mutation
    console.error('Failed to update API key:', error)
  }
}

</script>

<template>
  <UModal
    v-model:open="open"
    title="Update API Key"
    :description="`Update settings for ${existingKey?.name || 'API key'} (${existingKey?.prefix || '...'})`"
    size="xl"
    fullscreen
  >
    <template #body>
      <div v-if="isLoadingKey" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
      </div>

      <div v-else class="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
        <!-- Name & Description -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Name <span class="text-error">*</span></label>
          <UInput
            v-model="state.name"
            placeholder="Production API Key"
            icon="i-lucide-key"
            required
          />
          <p class="text-xs text-muted">A memorable name for this API key</p>
        </div>

        <div class="space-y-2">
          <label class="block text-sm font-medium">Description</label>
          <UTextarea
            v-model="state.description"
            placeholder="Used for production server integration..."
            :rows="2"
          />
        </div>

        <USeparator label="Status" />

        <!-- Status Selection -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Key Status</label>
          <div class="grid grid-cols-3 gap-2">
            <div
              v-for="statusOption in statusOptions"
              :key="statusOption.value"
              class="flex items-start gap-2 p-3 border rounded-lg cursor-pointer transition-colors"
              :class="state.status === statusOption.value ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'"
              @click="state.status = statusOption.value"
            >
              <div class="mt-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center" :class="state.status === statusOption.value ? 'border-primary' : 'border-muted'">
                <div v-if="state.status === statusOption.value" class="w-2 h-2 rounded-full bg-primary"></div>
              </div>
              <div class="flex-1">
                <p class="text-sm font-medium">{{ statusOption.label }}</p>
                <p class="text-xs text-muted">{{ statusOption.description }}</p>
              </div>
            </div>
          </div>
          <UAlert
            v-if="state.status === ApiKeyStatus.REVOKED"
            icon="i-lucide-alert-triangle"
            color="error"
            variant="subtle"
            title="Warning: Revoking is permanent"
            description="Once revoked, an API key cannot be re-activated. Consider suspending instead if you may need to re-enable it later."
          />
        </div>

        <USeparator label="Permissions" />

        <!-- Scopes Selection -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Scopes (Permissions)</label>
          <p class="text-xs text-muted mb-2">
            {{ loadingPermissions ? 'Loading permissions...' : `Select which permissions this API key can access (${state.scopes.length} selected)` }}
          </p>
          <div class="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3">
            <div v-for="scope in availableScopes" :key="scope.value" class="flex items-start gap-2 p-2 hover:bg-muted/30 rounded transition-colors">
              <UCheckbox
                :model-value="state.scopes.includes(scope.value)"
                @update:model-value="(checked) => {
                  if (checked) {
                    state.scopes = [...state.scopes, scope.value]
                  } else {
                    state.scopes = state.scopes.filter(s => s !== scope.value)
                  }
                }"
              />
              <div class="flex-1">
                <p class="text-sm font-medium">{{ scope.label }}</p>
                <p class="text-xs text-muted">{{ scope.description }}</p>
              </div>
            </div>
          </div>
        </div>

        <USeparator label="Rate Limits" />

        <!-- Rate Limiting -->
        <div class="space-y-3">
          <div class="space-y-2">
            <label class="block text-sm font-medium">Requests per minute</label>
            <UInput
              v-model.number="state.rate_limit_per_minute"
              type="number"
              min="1"
              placeholder="60"
              icon="i-lucide-gauge"
            />
            <p class="text-xs text-muted">Current: {{ state.rate_limit_per_minute }} requests/minute</p>
          </div>
        </div>

        <USeparator label="Security" />

        <!-- IP Whitelist -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">IP Whitelist (optional)</label>
          <UTextarea
            v-model="state.ip_whitelist_raw"
            placeholder="192.168.1.1&#10;10.0.0.0/24&#10;203.0.113.0"
            :rows="3"
          />
          <p class="text-xs text-muted">
            One IP address or CIDR per line. Leave empty to allow all IPs.
            {{ state.ip_whitelist.length > 0 ? `(${state.ip_whitelist.length} IPs configured)` : '' }}
          </p>
        </div>

        <!-- Expiration is read-only after creation -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Expiration</label>
          <p class="text-sm">
            {{ existingKey?.expires_at ? new Date(existingKey.expires_at).toLocaleString() : 'Never expires' }}
          </p>
          <p class="text-xs text-muted">Expiration is set when the key is created.</p>
        </div>

        <!-- Usage Stats (read-only) -->
        <USeparator label="Usage Statistics" />

        <div class="grid grid-cols-2 gap-4">
          <UCard>
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-muted">Total Uses</p>
                <p class="text-2xl font-bold mt-1">{{ existingKey?.usage_count || 0 }}</p>
              </div>
              <UIcon name="i-lucide-activity" class="w-8 h-8 text-primary" />
            </div>
          </UCard>

          <UCard>
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-muted">Last Used</p>
                <p class="text-sm font-medium mt-1">
                  {{ existingKey?.last_used_at ? new Date(existingKey.last_used_at).toLocaleDateString() : 'Never' }}
                </p>
              </div>
              <UIcon name="i-lucide-clock" class="w-8 h-8 text-muted" />
            </div>
          </UCard>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex items-center justify-between w-full">
        <div class="text-sm text-muted">
          Prefix: <code class="px-1.5 py-0.5 bg-elevated rounded text-xs">{{ existingKey?.prefix }}</code>
        </div>
        <div class="flex justify-end gap-2">
          <UButton
            label="Cancel"
            color="neutral"
            variant="outline"
            @click="open = false"
            :disabled="isSubmitting"
          />
          <UButton
            label="Save Changes"
            icon="i-lucide-save"
            :loading="isSubmitting"
            :disabled="!state.name || state.scopes.length === 0"
            @click="handleSubmit"
          />
        </div>
      </div>
    </template>
  </UModal>
</template>
