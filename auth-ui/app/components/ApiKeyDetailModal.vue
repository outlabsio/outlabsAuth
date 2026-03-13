<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { apiKeysQueries } from '~/queries/api-keys'
import { ApiKeyStatus } from '~/types/api-key'
import type { UiColor } from '~/types/ui'

const props = defineProps<{
  keyId: string
}>()

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{
  edit: []
}>()

// Fetch API key details
const { data: apiKey, isLoading } = useQuery(() => ({
  ...apiKeysQueries.detail(props.keyId),
  enabled: open.value && !!props.keyId
}))

// Status color mapping
const statusColors: Record<ApiKeyStatus, UiColor> = {
  [ApiKeyStatus.ACTIVE]: 'success',
  [ApiKeyStatus.SUSPENDED]: 'warning',
  [ApiKeyStatus.REVOKED]: 'error',
  [ApiKeyStatus.EXPIRED]: 'neutral'
}

// Helper to format dates
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return 'Never'
  return new Date(dateString).toLocaleString()
}

// Helper to format relative time
function formatRelativeTime(dateString: string | null | undefined): string {
  if (!dateString) return 'Never'

  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffHours / 24)

  if (diffHours < 1) return 'Just now'
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`
  return formatDate(dateString)
}

// Check if key is expired
const isExpired = computed(() => {
  if (!apiKey.value?.expires_at) return false
  return new Date(apiKey.value.expires_at) < new Date()
})

// Days until expiry
const daysUntilExpiry = computed(() => {
  if (!apiKey.value?.expires_at) return null
  const date = new Date(apiKey.value.expires_at)
  const now = new Date()
  return Math.ceil((date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
})

// Copy to clipboard
async function copyPrefix() {
  if (apiKey.value?.prefix) {
    await navigator.clipboard.writeText(apiKey.value.prefix)
    const toast = useToast()
    toast.add({
      title: 'Copied!',
      description: 'Prefix copied to clipboard',
      color: 'success'
    })
  }
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="`API Key Details`"
    :description="apiKey ? `${apiKey.name} (${apiKey.prefix})` : 'Loading...'"
    size="xl"
  >
    <template #body>
      <div v-if="isLoading" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
      </div>

      <div v-else-if="apiKey" class="space-y-6">
        <!-- Status Alert -->
        <UAlert
          v-if="isExpired"
          icon="i-lucide-alert-triangle"
          color="error"
          variant="solid"
          title="This API key has expired"
          description="This key can no longer be used for authentication. Create a new key or extend the expiration date."
        />
        <UAlert
          v-else-if="apiKey.status === 'revoked'"
          icon="i-lucide-ban"
          color="error"
          variant="solid"
          title="This API key has been revoked"
          description="Revoked keys cannot be re-activated. You must create a new key."
        />
        <UAlert
          v-else-if="apiKey.status === 'suspended'"
          icon="i-lucide-pause-circle"
          color="warning"
          variant="solid"
          title="This API key is suspended"
          description="Suspended keys are temporarily disabled. Re-activate to resume usage."
        />
        <UAlert
          v-else-if="daysUntilExpiry && daysUntilExpiry <= 7"
          icon="i-lucide-clock"
          color="warning"
          variant="subtle"
          title="Expiring soon"
          :description="`This key will expire in ${daysUntilExpiry} days`"
        />

        <!-- Basic Information -->
        <div>
          <h3 class="text-sm font-semibold mb-3 flex items-center gap-2">
            <UIcon name="i-lucide-info" class="w-4 h-4" />
            Basic Information
          </h3>
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1">
              <p class="text-xs text-muted">Name</p>
              <p class="text-sm font-medium">{{ apiKey.name }}</p>
            </div>
            <div class="space-y-1">
              <p class="text-xs text-muted">Prefix</p>
              <div class="flex items-center gap-2">
                <code class="text-sm font-mono bg-elevated px-2 py-1 rounded">{{ apiKey.prefix }}</code>
                <UButton
                  icon="i-lucide-copy"
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  @click="copyPrefix"
                />
              </div>
            </div>
            <div class="space-y-1">
              <p class="text-xs text-muted">Status</p>
              <UBadge :color="statusColors[apiKey.status]" variant="subtle">
                {{ apiKey.status.toUpperCase() }}
              </UBadge>
            </div>
            <div class="space-y-1">
              <p class="text-xs text-muted">Created</p>
              <p class="text-sm">{{ formatDate(apiKey.created_at) }}</p>
            </div>
          </div>

          <div v-if="apiKey.description" class="mt-4 space-y-1">
            <p class="text-xs text-muted">Description</p>
            <p class="text-sm">{{ apiKey.description }}</p>
          </div>
        </div>

        <USeparator />

        <!-- Usage Statistics -->
        <div>
          <h3 class="text-sm font-semibold mb-3 flex items-center gap-2">
            <UIcon name="i-lucide-activity" class="w-4 h-4" />
            Usage Statistics
          </h3>
          <div class="grid grid-cols-3 gap-4">
            <UCard>
              <div class="text-center">
                <p class="text-2xl font-bold">{{ apiKey.usage_count }}</p>
                <p class="text-xs text-muted mt-1">Total Requests</p>
              </div>
            </UCard>
            <UCard>
              <div class="text-center">
                <p class="text-sm font-medium">{{ formatRelativeTime(apiKey.last_used_at) }}</p>
                <p class="text-xs text-muted mt-1">Last Used</p>
              </div>
            </UCard>
            <UCard>
              <div class="text-center">
                <p class="text-sm font-medium">
                  {{ apiKey.expires_at ? (isExpired ? 'Expired' : formatDate(apiKey.expires_at).split(',')[0]) : 'Never' }}
                </p>
                <p class="text-xs text-muted mt-1">Expires</p>
              </div>
            </UCard>
          </div>
        </div>

        <USeparator />

        <!-- Permissions / Scopes -->
        <div>
          <h3 class="text-sm font-semibold mb-3 flex items-center gap-2">
            <UIcon name="i-lucide-shield-check" class="w-4 h-4" />
            Permissions ({{ apiKey.scopes.length }})
          </h3>

          <div v-if="apiKey.scopes.includes('*:*')" class="space-y-2">
            <UAlert
              icon="i-lucide-alert-triangle"
              color="warning"
              variant="subtle"
              title="Full Access"
              description="This API key has unrestricted access to all resources and actions."
            />
          </div>

          <div v-else-if="apiKey.scopes.length === 0" class="text-sm text-muted">
            No permissions assigned
          </div>

          <div v-else class="flex flex-wrap gap-2">
            <UBadge
              v-for="scope in apiKey.scopes"
              :key="scope"
              color="neutral"
              variant="subtle"
            >
              {{ scope }}
            </UBadge>
          </div>
        </div>

        <USeparator />

        <!-- Rate Limits -->
        <div>
          <h3 class="text-sm font-semibold mb-3 flex items-center gap-2">
            <UIcon name="i-lucide-gauge" class="w-4 h-4" />
            Rate Limits
          </h3>
          <div class="grid grid-cols-1 gap-4">
            <div class="space-y-1">
              <p class="text-xs text-muted">Per Minute</p>
              <p class="text-lg font-bold">{{ apiKey.rate_limit_per_minute }}</p>
            </div>
          </div>
        </div>

        <!-- IP Whitelist -->
        <div v-if="apiKey.ip_whitelist && apiKey.ip_whitelist.length > 0">
          <USeparator />
          <div>
            <h3 class="text-sm font-semibold mb-3 flex items-center gap-2">
              <UIcon name="i-lucide-shield" class="w-4 h-4" />
              IP Whitelist ({{ apiKey.ip_whitelist.length }})
            </h3>
            <div class="space-y-1">
              <code
                v-for="ip in apiKey.ip_whitelist"
                :key="ip"
                class="block text-xs font-mono bg-elevated px-2 py-1 rounded"
              >
                {{ ip }}
              </code>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="text-center py-12 text-muted">
        <UIcon name="i-lucide-key-off" class="w-12 h-12 mx-auto mb-2 opacity-50" />
        <p>API key not found</p>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-between w-full">
        <UButton
          label="Edit Key"
          icon="i-lucide-pencil"
          color="primary"
          variant="outline"
          :disabled="apiKey?.status === 'revoked'"
          @click="emit('edit')"
        />
        <UButton
          label="Close"
          color="neutral"
          variant="outline"
          @click="open = false"
        />
      </div>
    </template>
  </UModal>
</template>
