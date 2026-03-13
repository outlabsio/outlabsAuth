<script setup lang="ts">
import { useQuery } from '@pinia/colada'
import { permissionsQueries } from '~/queries/permissions'
import { useCreateApiKeyMutation } from '~/queries/api-keys'
import type { CreateApiKeyRequest, PrefixType, ApiKeyCreateResponse } from '~/types/api-key'

const open = defineModel<boolean>('open', { default: false })

// Fetch available permissions dynamically
const { data: permissions, isLoading: loadingPermissions } = useQuery(permissionsQueries.available())

// Prefix type options for UTabs
const prefixTypes: { value: PrefixType; label: string }[] = [
  { value: 'sk_live', label: 'Live' },
  { value: 'sk_test', label: 'Test' },
  { value: 'sk_prod', label: 'Prod' },
  { value: 'sk_dev', label: 'Dev' }
]

// Grouped scopes by category (resource prefix before the colon)
const scopesByCategory = computed(() => {
  if (!permissions.value) return {}

  const grouped: Record<string, { value: string; label: string; description: string }[]> = {}
  for (const p of permissions.value) {
    const category = p.name.includes(':') ? p.name.split(':')[0] : 'other'
    if (!grouped[category]) grouped[category] = []
    grouped[category].push({
      value: p.name,
      label: p.display_name || p.name,
      description: p.description || ''
    })
  }
  return grouped
})

function toggleScope(value: string) {
  const idx = state.scopes.indexOf(value)
  if (idx >= 0) {
    state.scopes.splice(idx, 1)
  } else {
    state.scopes.push(value)
  }
}

function toggleAllInCategory(category: string) {
  const items = scopesByCategory.value[category] || []
  const allSelected = items.every(i => state.scopes.includes(i.value))
  if (allSelected) {
    state.scopes = state.scopes.filter(s => !items.some(i => i.value === s))
  } else {
    for (const item of items) {
      if (!state.scopes.includes(item.value)) {
        state.scopes.push(item.value)
      }
    }
  }
}

function removeScope(value: string) {
  state.scopes = state.scopes.filter(s => s !== value)
}

// Permission search filter
const permissionSearch = ref('')

const filteredScopesByCategory = computed(() => {
  const query = permissionSearch.value.toLowerCase().trim()
  if (!query) return scopesByCategory.value

  const filtered: Record<string, { value: string; label: string; description: string }[]> = {}
  for (const [category, items] of Object.entries(scopesByCategory.value)) {
    const matched = items.filter(i =>
      i.label.toLowerCase().includes(query)
      || i.value.toLowerCase().includes(query)
      || i.description.toLowerCase().includes(query)
    )
    if (matched.length > 0) filtered[category] = matched
  }
  return filtered
})

interface ApiKeyCreateForm {
  name: string
  description: string
  scopes: string[]
  prefix_type: PrefixType
  ip_whitelist: string[]
  ip_whitelist_raw: string
  rate_limit_per_minute: number
  expires_in_days?: number
  never_expires: boolean
  saved_confirmation: boolean
}

function buildInitialState(): ApiKeyCreateForm {
  return {
    name: '',
    description: '',
    scopes: [],
    prefix_type: 'sk_live',
    ip_whitelist: [],
    ip_whitelist_raw: '',
    rate_limit_per_minute: 60,
    expires_in_days: 90,
    never_expires: false,
    saved_confirmation: false
  }
}

// Form state
const state = reactive<ApiKeyCreateForm>(buildInitialState())

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
const { isLoading: isCreatingKey } = createMutation

// Submit handler
async function handleSubmit() {
  const payload: CreateApiKeyRequest = {
    name: state.name,
    description: state.description || undefined,
    scopes: state.scopes.length > 0 ? [...state.scopes] : undefined,
    prefix_type: state.prefix_type,
    ip_whitelist: state.ip_whitelist.length > 0 ? [...state.ip_whitelist] : undefined,
    rate_limit_per_minute: state.rate_limit_per_minute,
    expires_in_days: state.never_expires ? undefined : state.expires_in_days,
  }

  try {
    const result = await createMutation.mutateAsync(payload)
    generatedKeyResponse.value = result
    state.saved_confirmation = false
  } catch (error) {
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
    Object.assign(state, buildInitialState())
  }, 300)
}

</script>

<template>
  <UModal
    v-model:open="open"
    :title="generatedKeyResponse ? 'API Key Created' : 'Create API Key'"
    :description="generatedKeyResponse ? 'Save your API key — you won\'t be able to see it again' : 'Generate a new API key for programmatic access'"
    fullscreen
  >
    <template #body>
      <!-- Show generated key -->
      <div v-if="generatedKeyResponse" class="max-w-xl mx-auto space-y-4">
        <UAlert
          icon="i-lucide-alert-triangle"
          color="error"
          variant="subtle"
          title="Save this key now"
          description="This is the only time you'll see the full API key. Copy and store it in a secure location."
        />

        <UFormField label="Your API Key">
          <div class="flex items-center gap-2">
            <UInput
              :model-value="generatedKeyResponse.api_key"
              readonly
              class="flex-1 font-mono"
            />
            <UButton
              icon="i-lucide-copy"
              label="Copy"
              @click="copyToClipboard"
            />
          </div>
          <template #description>
            Prefix: <code class="text-xs">{{ generatedKeyResponse.prefix }}</code>
          </template>
        </UFormField>

        <UAlert
          icon="i-lucide-shield-check"
          color="info"
          variant="subtle"
          title="Security tips"
          description="Store in a password manager or secrets vault. Never commit to version control. Use environment variables in production."
        />

        <UCheckbox
          v-model="state.saved_confirmation"
          label="I have securely saved this API key"
          description="Required before closing"
        />
      </div>

      <!-- Creation form -->
      <div v-else class="max-w-3xl mx-auto">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <!-- Left column: basics -->
          <div class="space-y-5">
            <UFormField label="Name" required>
              <UInput
                v-model="state.name"
                placeholder="e.g. Production API Key"
                icon="i-lucide-key"
                class="w-full"
              />
              <template #description>A memorable name for this API key</template>
            </UFormField>

            <UFormField label="Description" hint="Optional">
              <UTextarea
                v-model="state.description"
                placeholder="What is this key used for?"
                :rows="2"
                class="w-full"
              />
            </UFormField>

            <UFormField label="Environment">
              <UTabs
                :model-value="state.prefix_type"
                :items="prefixTypes"
                variant="pill"
                class="w-full"
                @update:model-value="state.prefix_type = $event as PrefixType"
              />
            </UFormField>

            <div class="grid grid-cols-2 gap-4">
              <UFormField label="Rate limit">
                <UInputNumber
                  v-model="state.rate_limit_per_minute"
                  :min="1"
                  :step="10"
                  class="w-full"
                />
                <template #description>Requests per minute</template>
              </UFormField>

              <UFormField label="Expires in (days)">
                <UInputNumber
                  v-model="state.expires_in_days"
                  :min="1"
                  :max="365"
                  :step="30"
                  :disabled="state.never_expires"
                  class="w-full"
                />
                <template #description>
                  <UCheckbox
                    v-model="state.never_expires"
                    label="Never expires"
                    class="mt-1"
                  />
                </template>
              </UFormField>
            </div>

            <UFormField label="IP Whitelist" hint="Optional">
              <UTextarea
                v-model="state.ip_whitelist_raw"
                placeholder="192.168.1.1&#10;10.0.0.0/24"
                :rows="2"
                class="w-full"
              />
              <template #description>
                One IP or CIDR per line. Leave empty to allow all.
                <span v-if="state.ip_whitelist.length > 0" class="text-highlighted">
                  ({{ state.ip_whitelist.length }} configured)
                </span>
              </template>
            </UFormField>
          </div>

          <!-- Right column: permissions -->
          <div class="space-y-3">
            <UFormField label="Permissions" required>
              <template #description>
                {{ state.scopes.length > 0
                  ? `${state.scopes.includes('*:*') ? 'All permissions' : state.scopes.length + ' selected'}`
                  : 'Select at least one permission'
                }}
              </template>
            </UFormField>

            <!-- All Permissions toggle -->
            <button
              type="button"
              class="w-full flex items-center gap-3 p-3 rounded-lg ring ring-inset transition-colors text-left"
              :class="state.scopes.includes('*:*')
                ? 'ring-warning bg-warning/5'
                : 'ring-accented hover:bg-elevated/50'"
              @click="toggleScope('*:*')"
            >
              <UCheckbox :model-value="state.scopes.includes('*:*')" />
              <div class="flex-1">
                <p class="text-sm font-medium">All Permissions</p>
                <p class="text-xs text-warning">Full access — use with caution</p>
              </div>
            </button>

            <!-- Selected scopes chips -->
            <div
              v-if="state.scopes.length > 0 && !state.scopes.includes('*:*')"
              class="flex flex-wrap gap-1.5"
            >
              <UBadge
                v-for="scope in state.scopes"
                :key="scope"
                :label="scope"
                color="primary"
                variant="subtle"
                size="sm"
                class="cursor-pointer"
                @click="removeScope(scope)"
              >
                <template #trailing>
                  <UIcon name="i-lucide-x" class="size-3" />
                </template>
              </UBadge>
            </div>

            <!-- Permission search -->
            <UInput
              v-if="!state.scopes.includes('*:*')"
              v-model="permissionSearch"
              placeholder="Filter permissions..."
              icon="i-lucide-search"
              class="w-full"
              :ui="{ trailing: permissionSearch ? '' : 'hidden' }"
            >
              <template v-if="permissionSearch" #trailing>
                <UButton
                  icon="i-lucide-x"
                  size="xs"
                  color="neutral"
                  variant="ghost"
                  @click="permissionSearch = ''"
                />
              </template>
            </UInput>

            <!-- Permissions by category -->
            <div
              v-if="!state.scopes.includes('*:*')"
              class="max-h-[50vh] overflow-y-auto rounded-lg ring ring-inset ring-accented"
            >
              <template v-if="Object.keys(filteredScopesByCategory).length > 0">
                <div
                  v-for="(items, category) in filteredScopesByCategory"
                  :key="category"
                >
                  <button
                    type="button"
                    class="w-full flex items-center gap-2 px-3 py-2 bg-elevated text-xs font-semibold uppercase tracking-wide text-muted sticky top-0 z-10 hover:text-default transition-colors shadow-[0_1px_0_0_var(--ui-border)]"
                    @click="toggleAllInCategory(category as string)"
                  >
                    <UCheckbox
                      :model-value="items.every(i => state.scopes.includes(i.value))"
                      :indeterminate="items.some(i => state.scopes.includes(i.value)) && !items.every(i => state.scopes.includes(i.value))"
                      size="xs"
                    />
                    <span>{{ category }}</span>
                    <span class="ml-auto text-dimmed font-normal normal-case">
                      {{ items.filter(i => state.scopes.includes(i.value)).length }}/{{ items.length }}
                    </span>
                  </button>
                  <div>
                    <button
                      v-for="item in items"
                      :key="item.value"
                      type="button"
                      class="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-elevated/50 transition-colors text-left"
                      @click="toggleScope(item.value)"
                    >
                      <UCheckbox :model-value="state.scopes.includes(item.value)" size="xs" />
                      <div class="flex-1 min-w-0">
                        <p class="text-sm truncate">{{ item.label }}</p>
                        <p v-if="item.description" class="text-xs text-muted truncate">{{ item.description }}</p>
                      </div>
                    </button>
                  </div>
                </div>
              </template>
              <div v-else class="flex flex-col items-center gap-1 py-6 text-muted">
                <UIcon name="i-lucide-search-x" class="size-5" />
                <span class="text-sm">No permissions match "{{ permissionSearch }}"</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div v-if="generatedKeyResponse" class="flex justify-end">
        <UButton
          label="Done"
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
          :disabled="isCreatingKey"
        />
        <UButton
          label="Generate API Key"
          icon="i-lucide-key"
          :loading="isCreatingKey"
          :disabled="!state.name || state.scopes.length === 0"
          @click="handleSubmit"
        />
      </div>
    </template>
  </UModal>
</template>
