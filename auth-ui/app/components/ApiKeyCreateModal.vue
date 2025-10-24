<script setup lang="ts">
const open = defineModel<boolean>('open', { default: false })

const toast = useToast()

// Available scopes
const availableScopes = [
  { value: '*:*', label: 'All Permissions', description: 'Full access to all resources' },
  { value: 'user:read', label: 'User Read', description: 'Read user information' },
  { value: 'user:create', label: 'User Create', description: 'Create new users' },
  { value: 'user:update', label: 'User Update', description: 'Update user information' },
  { value: 'user:delete', label: 'User Delete', description: 'Delete users' },
  { value: 'role:read', label: 'Role Read', description: 'Read role information' },
  { value: 'role:create', label: 'Role Create', description: 'Create new roles' },
  { value: 'role:update', label: 'Role Update', description: 'Update roles' },
  { value: 'role:delete', label: 'Role Delete', description: 'Delete roles' },
  { value: 'entity:read', label: 'Entity Read', description: 'Read entity information' },
  { value: 'entity:create', label: 'Entity Create', description: 'Create new entities' },
  { value: 'entity:update', label: 'Entity Update', description: 'Update entities' },
  { value: 'entity:delete', label: 'Entity Delete', description: 'Delete entities' },
  { value: 'permission:read', label: 'Permission Read', description: 'Read permissions' }
]

// Form state
const state = reactive({
  name: '',
  description: '',
  scopes: [] as string[],
  expires_in_days: 90,
  never_expires: false
})

// Watch never_expires to clear expiration
watch(() => state.never_expires, (neverExpires) => {
  if (neverExpires) {
    state.expires_in_days = 0
  } else if (state.expires_in_days === 0) {
    state.expires_in_days = 90
  }
})

// Generated API key (shown after creation)
const generatedKey = ref<string | null>(null)

// Submit handler
const isSubmitting = ref(false)

async function handleSubmit() {
  isSubmitting.value = true
  try {
    // In mock mode, generate a fake API key
    const prefix = 'olauth_' + state.name.toLowerCase().replace(/\s+/g, '_').substring(0, 10)
    const mockKey = `${prefix}_${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500))

    // Show generated key
    generatedKey.value = mockKey

    toast.add({
      title: 'API Key created',
      description: 'Your API key has been created. Make sure to copy it now!',
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.message || 'Failed to create API key',
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

// Copy to clipboard
async function copyToClipboard() {
  if (generatedKey.value) {
    await navigator.clipboard.writeText(generatedKey.value)
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
    generatedKey.value = null
    Object.assign(state, {
      name: '',
      description: '',
      scopes: [],
      expires_in_days: 90,
      never_expires: false
    })
  }, 300)
}
</script>

<template>
  <UModal
    v-model:open="open"
    :title="generatedKey ? 'API Key Created' : 'Create API Key'"
    :description="generatedKey ? 'Save your API key - you won\'t be able to see it again!' : 'Generate a new API key for programmatic access'"
  >
    <template #body>
      <!-- Show generated key -->
      <div v-if="generatedKey" class="space-y-4">
        <UAlert
          icon="i-lucide-alert-triangle"
          color="warning"
          variant="subtle"
          title="Save this key now"
          description="This is the only time you'll see this key. Store it securely."
        />

        <div class="space-y-2">
          <label class="text-sm font-medium">Your API Key</label>
          <div class="flex items-center gap-2">
            <UInput
              :model-value="generatedKey"
              readonly
              class="flex-1 font-mono text-sm"
            />
            <UButton
              icon="i-lucide-copy"
              color="neutral"
              variant="outline"
              @click="copyToClipboard"
            />
          </div>
        </div>
      </div>

      <!-- Creation form -->
      <div v-else class="space-y-4">
        <!-- Name & Description -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Name</label>
          <UInput
            v-model="state.name"
            placeholder="Production API Key"
            icon="i-lucide-key"
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

        <UDivider label="Permissions" />

        <!-- Scopes Selection -->
        <div class="space-y-2">
          <label class="block text-sm font-medium">Scopes</label>
          <div class="space-y-2">
            <div v-for="scope in availableScopes" :key="scope.value" class="flex items-start gap-2">
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

        <UDivider label="Expiration" />

        <!-- Expiration Settings -->
        <div class="space-y-3">
          <UCheckbox
            v-model="state.never_expires"
            label="Never expires"
            help="Key will remain valid indefinitely (not recommended for production)"
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
            <p class="text-xs text-muted">Recommended: 90 days</p>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div v-if="generatedKey" class="flex justify-end">
        <UButton
          label="Done"
          color="primary"
          @click="closeModal"
        />
      </div>
      <div v-else class="flex justify-end gap-2">
        <UButton
          label="Cancel"
          color="neutral"
          variant="outline"
          @click="open = false"
          :disabled="isSubmitting"
        />
        <UButton
          label="Generate API Key"
          icon="i-lucide-key"
          :loading="isSubmitting"
          @click="handleSubmit"
        />
      </div>
    </template>
  </UModal>
</template>
