<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { permissionsQueries } from '~/queries/permissions'
import { useCreateApiKeyMutation } from '~/queries/api-keys'
import type { CreateApiKeyRequest, PrefixType, ApiKeyCreateResponse } from '~/types/api-key'

const open = defineModel<boolean>('open', { default: false })

// Fetch available permissions dynamically
const { data: permissions, isLoading: loadingPermissions } = useQuery(permissionsQueries.available())

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

// Prefix type options
const prefixTypes: { value: PrefixType; label: string; description: string }[] = [
  { value: 'sk_live', label: 'Live', description: 'Production environment' },
  { value: 'sk_test', label: 'Test', description: 'Testing environment' },
  { value: 'sk_prod', label: 'Prod', description: 'Production (alternative)' },
  { value: 'sk_dev', label: 'Dev', description: 'Development environment' }
]

// Form state
const state = reactive<CreateApiKeyRequest & { never_expires: boolean; ip_whitelist_raw: string; saved_confirmation: boolean }>({
  name: '',
  description: '',
  scopes: [],
  prefix_type: 'sk_live',
  ip_whitelist: [],
  ip_whitelist_raw: '',
  rate_limit_per_minute: 60,
  rate_limit_per_hour: undefined,
  rate_limit_per_day: undefined,
  expires_in_days: 90,
  never_expires: false,
  saved_confirmation: false
})

// Watch never_expires to clear expiration
watch(() => state.never_expires, (neverExpires) => {
  if (neverExpires) {
    state.expires_in_days = undefined
  } else if (!state.expires_in_days) {
    state.expires_in_days = 90
  }
})

// Watch IP whitelist raw input
watch(() => state.ip_whitelist_raw, (raw) => {
  if (raw.trim()) {
    // Split by newlines and comma, trim whitespace
    state.ip_whitelist = raw
      .split(/[\n,]+/)
      .map(ip => ip.trim())
      .filter(ip => ip.length > 0)
  } else {
    state.ip_whitelist = []
  }
})

// Generated API key response (shown after creation)
const generatedKeyResponse = ref<ApiKeyCreateResponse | null>(null)

// Create mutation
const createMutation = useCreateApiKeyMutation()

// Submit handler
async function handleSubmit() {
  // Build request payload
  const payload: CreateApiKeyRequest = {
    name: state.name,
    description: state.description || undefined,
    scopes: state.scopes.length > 0 ? state.scopes : undefined,
    prefix_type: state.prefix_type,
    ip_whitelist: state.ip_whitelist.length > 0 ? state.ip_whitelist : undefined,
    rate_limit_per_minute: state.rate_limit_per_minute,
    rate_limit_per_hour: state.rate_limit_per_hour,
    rate_limit_per_day: state.rate_limit_per_day,
    expires_in_days: state.never_expires ? undefined : state.expires_in_days,
  }

  try {
    const result = await createMutation.mutateAsync(payload)
    generatedKeyResponse.value = result
    state.saved_confirmation = false
  } catch (error) {
    // Error handling done by mutation
    console.error('Failed to create API key:', error)
  }
}

// Copy to clipboard
async function copyToClipboard() {
  if (generatedKeyResponse.value?.api_key) {
    await navigator.clipboard.writeText(generatedKeyResponse.value.api_key)
    const toast = useToast()
    toast.add({
      title: 'Copied!',
      description: 'API key copied to clipboard',
      color: 'success'
    })
  }
}

// Close and reset
function closeModal() {
  open.value = false
  setTimeout(() => {
    generatedKeyResponse.value = null
    Object.assign(state, {
      name: '',
      description: '',
      scopes: [],
      prefix_type: 'sk_live',
      ip_whitelist: [],
      ip_whitelist_raw: '',
      rate_limit_per_minute: 60,
      rate_limit_per_hour: undefined,
      rate_limit_per_day: undefined,
      expires_in_days: 90,
      never_expires: false,
      saved_confirmation: false
    })
  }, 300)
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="generatedKeyResponse ? 'API Key Created ✅' : 'Create API Key'"
    :description="generatedKeyResponse ? 'Save your API key - you won\'t be able to see it again!' : 'Generate a new API key for programmatic access'"
    size="xl"
    fullscreen
  >
    <template #body>
      <!-- Show generated key -->
      <div v-if="generatedKeyResponse" class="space-y-4">
        <UAlert
          icon="i-lucide-alert-triangle"
          color="error"
          variant="solid"
          title="⚠️ CRITICAL: Save this key immediately"
          description="This is the ONLY time you'll see the full API key. Once you close this dialog, it cannot be recovered. Copy and store it in a secure password manager or secrets vault."
        />

        <div class="space-y-2">
          <label class="text-sm font-medium">Your API Key</label>
          <div class="flex items-center gap-2">
            <UInput
              :model-value="generatedKeyResponse.api_key"
              readonly
              class="flex-1 font-mono text-sm"
            />
            <UButton
              icon="i-lucide-copy"
              color="primary"
              variant="solid"
              @click="copyToClipboard"
              label="Copy"
            />
          </div>
          <p class="text-xs text-muted">Prefix: {{ generatedKeyResponse.prefix }}</p>
        </div>

        <UAlert
          icon="i-lucide-shield-check"
          color="primary"
          variant="subtle"
          title="Security Best Practices"
          description="Store in a password manager or secrets vault. Never commit to version control. Rotate keys regularly. Use environment variables in production."
        />

        <!-- Confirmation checkbox -->
        <UCheckbox
          v-model="state.saved_confirmation"
          label="I have securely saved this API key"
          help="Required before closing this dialog"
        />
      </div>

      <!-- Creation form -->
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

        <USeparator label="Environment" />

        <!-- Prefix Type Selection -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Environment Type</label>
          <div class="grid grid-cols-2 gap-2">
            <div
              v-for="prefix in prefixTypes"
              :key="prefix.value"
              class="flex items-start gap-2 p-3 border rounded-lg cursor-pointer transition-colors"
              :class="state.prefix_type === prefix.value ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'"
              @click="state.prefix_type = prefix.value"
            >
              <div class="mt-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center" :class="state.prefix_type === prefix.value ? 'border-primary' : 'border-muted'">
                <div v-if="state.prefix_type === prefix.value" class="w-2 h-2 rounded-full bg-primary"></div>
              </div>
              <div class="flex-1">
                <p class="text-sm font-medium">{{ prefix.label }}</p>
                <p class="text-xs text-muted">{{ prefix.description }}</p>
              </div>
            </div>
          </div>
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
            <p class="text-xs text-muted">Default: 60 requests/minute</p>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-2">
              <label class="block text-sm font-medium">Per hour (optional)</label>
              <UInput
                v-model.number="state.rate_limit_per_hour"
                type="number"
                min="1"
                placeholder="3600"
              />
            </div>
            <div class="space-y-2">
              <label class="block text-sm font-medium">Per day (optional)</label>
              <UInput
                v-model.number="state.rate_limit_per_day"
                type="number"
                min="1"
                placeholder="86400"
              />
            </div>
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

        <!-- Expiration Settings -->
        <div class="space-y-3">
          <UCheckbox
            v-model="state.never_expires"
            label="Never expires"
            help="⚠️ Not recommended for production - keys should be rotated regularly"
          />

          <div v-if="!state.never_expires" class="space-y-2">
            <label class="block text-sm font-medium">Expires in (days)</label>
            <UInput
              v-model.number="state.expires_in_days"
              type="number"
              min="1"
              max="365"
              placeholder="90"
              icon="i-lucide-calendar"
            />
            <p class="text-xs text-muted">Recommended: 90 days for production keys</p>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div v-if="generatedKeyResponse" class="flex justify-end">
        <UButton
          label="Done"
          color="primary"
          @click="closeModal"
          :disabled="!state.saved_confirmation"
        />
      </div>
      <div v-else class="flex justify-end gap-2">
        <UButton
          label="Cancel"
          color="neutral"
          variant="outline"
          @click="open = false"
          :disabled="createMutation.isPending"
        />
        <UButton
          label="Generate API Key"
          icon="i-lucide-key"
          :loading="createMutation.isPending"
          :disabled="!state.name || state.scopes.length === 0"
          @click="handleSubmit"
        />
      </div>
    </template>
  </UModal>
</template>
