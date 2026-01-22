<script setup lang="ts">
import type { DefaultChildTypes } from '~/api/config'

const authStore = useAuthStore()
const configStore = useConfigStore()
const toast = useToast()

// Access control - only superusers
const isSuperuser = computed(() => authStore.currentUser?.is_superuser ?? false)

// Redirect if not superuser
onMounted(() => {
  if (!isSuperuser.value) {
    navigateTo('/settings')
  }
})

// Local state for editing
const rootTypes = ref<string[]>([])
const structuralChildTypes = ref<string[]>([])
const accessGroupChildTypes = ref<string[]>([])
const newRootType = ref('')
const newStructuralType = ref('')
const newAccessGroupType = ref('')

const isSaving = ref(false)
const hasChanges = ref(false)

// Initialize from store
onMounted(async () => {
  await configStore.fetchEntityTypeConfig()
  resetForm()
})

const resetForm = () => {
  rootTypes.value = [...configStore.allowedRootTypes]
  structuralChildTypes.value = [...configStore.defaultStructuralChildTypes]
  accessGroupChildTypes.value = [...configStore.defaultAccessGroupChildTypes]
  hasChanges.value = false
}

// Watch for changes
watch([rootTypes, structuralChildTypes, accessGroupChildTypes], () => {
  hasChanges.value = true
}, { deep: true })

// Add type handlers
const addRootType = () => {
  const type = newRootType.value.trim().toLowerCase().replace(/\s+/g, '_')
  if (type && !rootTypes.value.includes(type)) {
    rootTypes.value.push(type)
    newRootType.value = ''
  }
}

const removeRootType = (type: string) => {
  if (rootTypes.value.length > 1) {
    rootTypes.value = rootTypes.value.filter(t => t !== type)
  } else {
    toast.add({
      title: 'Cannot remove',
      description: 'At least one root entity type is required',
      color: 'error'
    })
  }
}

const addStructuralType = () => {
  const type = newStructuralType.value.trim().toLowerCase().replace(/\s+/g, '_')
  if (type && !structuralChildTypes.value.includes(type)) {
    structuralChildTypes.value.push(type)
    newStructuralType.value = ''
  }
}

const removeStructuralType = (type: string) => {
  structuralChildTypes.value = structuralChildTypes.value.filter(t => t !== type)
}

const addAccessGroupType = () => {
  const type = newAccessGroupType.value.trim().toLowerCase().replace(/\s+/g, '_')
  if (type && !accessGroupChildTypes.value.includes(type)) {
    accessGroupChildTypes.value.push(type)
    newAccessGroupType.value = ''
  }
}

const removeAccessGroupType = (type: string) => {
  accessGroupChildTypes.value = accessGroupChildTypes.value.filter(t => t !== type)
}

// Save changes
const saveChanges = async () => {
  if (rootTypes.value.length === 0) {
    toast.add({
      title: 'Validation Error',
      description: 'At least one root entity type is required',
      color: 'error'
    })
    return
  }

  isSaving.value = true
  try {
    const defaultChildTypes: DefaultChildTypes = {
      structural: structuralChildTypes.value,
      access_group: accessGroupChildTypes.value
    }

    const success = await configStore.updateEntityTypeConfig({
      allowed_root_types: rootTypes.value,
      default_child_types: defaultChildTypes
    })

    if (success) {
      toast.add({
        title: 'Settings saved',
        description: 'Entity type configuration has been updated',
        color: 'success'
      })
      hasChanges.value = false
    } else {
      toast.add({
        title: 'Save failed',
        description: configStore.error || 'Failed to save settings',
        color: 'error'
      })
    }
  } finally {
    isSaving.value = false
  }
}

// Format type for display
const formatTypeName = (type: string): string => {
  return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}
</script>

<template>
  <UDashboardPanel id="settings-entity-types">
    <template #header>
      <UDashboardNavbar title="Entity Type Configuration">
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
      <div v-if="!isSuperuser" class="flex items-center justify-center h-64">
        <UCard class="max-w-md">
          <div class="text-center space-y-4">
            <UIcon name="i-lucide-shield-x" class="w-12 h-12 text-error mx-auto" />
            <h3 class="text-lg font-semibold">Access Denied</h3>
            <p class="text-muted">
              Only superusers can access entity type configuration.
            </p>
            <UButton to="/settings" label="Back to Settings" />
          </div>
        </UCard>
      </div>

      <div v-else class="max-w-3xl space-y-6">
        <!-- Introduction -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-info" class="w-5 h-5 text-info" />
              <h3 class="text-lg font-semibold">About Entity Types</h3>
            </div>
          </template>

          <div class="space-y-3 text-sm text-muted">
            <p>
              Entity types define the vocabulary used when creating organizational structures.
              Different deployments may use different terminology.
            </p>
            <p>
              <strong>Root Entity Types:</strong> Types available when creating top-level entities
              (e.g., "organization", "brokerage", "franchise").
            </p>
            <p>
              <strong>Default Child Types:</strong> Suggested types when creating child entities.
              Root entities can customize their own allowed child types.
            </p>
          </div>
        </UCard>

        <!-- Allowed Root Entity Types -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-building-2" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Allowed Root Entity Types</h3>
            </div>
          </template>

          <div class="space-y-4">
            <p class="text-sm text-muted">
              These types are available when creating top-level entities (organizations).
            </p>

            <div class="flex flex-wrap gap-2">
              <UBadge
                v-for="type in rootTypes"
                :key="type"
                color="primary"
                variant="subtle"
                size="lg"
                class="pr-1"
              >
                {{ formatTypeName(type) }}
                <UButton
                  icon="i-lucide-x"
                  color="primary"
                  variant="ghost"
                  size="xs"
                  class="ml-1 -mr-1"
                  @click="removeRootType(type)"
                />
              </UBadge>
            </div>

            <div class="flex gap-2">
              <UInput
                v-model="newRootType"
                placeholder="Add new type (e.g., brokerage)"
                class="flex-1"
                @keyup.enter="addRootType"
              />
              <UButton
                icon="i-lucide-plus"
                label="Add"
                @click="addRootType"
              />
            </div>
          </div>
        </UCard>

        <!-- Default Child Types - Structural -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-git-branch" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Default Structural Child Types</h3>
            </div>
          </template>

          <div class="space-y-4">
            <p class="text-sm text-muted">
              Default types for structural entities (departments, teams, branches, etc.).
            </p>

            <div class="flex flex-wrap gap-2">
              <UBadge
                v-for="type in structuralChildTypes"
                :key="type"
                color="neutral"
                variant="subtle"
                size="lg"
                class="pr-1"
              >
                {{ formatTypeName(type) }}
                <UButton
                  icon="i-lucide-x"
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  class="ml-1 -mr-1"
                  @click="removeStructuralType(type)"
                />
              </UBadge>
              <UBadge
                v-if="structuralChildTypes.length === 0"
                color="warning"
                variant="subtle"
              >
                No default types configured
              </UBadge>
            </div>

            <div class="flex gap-2">
              <UInput
                v-model="newStructuralType"
                placeholder="Add new type (e.g., region)"
                class="flex-1"
                @keyup.enter="addStructuralType"
              />
              <UButton
                icon="i-lucide-plus"
                label="Add"
                @click="addStructuralType"
              />
            </div>
          </div>
        </UCard>

        <!-- Default Child Types - Access Groups -->
        <UCard>
          <template #header>
            <div class="flex items-center gap-3">
              <UIcon name="i-lucide-users" class="w-5 h-5" />
              <h3 class="text-lg font-semibold">Default Access Group Types</h3>
            </div>
          </template>

          <div class="space-y-4">
            <p class="text-sm text-muted">
              Default types for access group entities (permission groups, admin groups, etc.).
            </p>

            <div class="flex flex-wrap gap-2">
              <UBadge
                v-for="type in accessGroupChildTypes"
                :key="type"
                color="secondary"
                variant="subtle"
                size="lg"
                class="pr-1"
              >
                {{ formatTypeName(type) }}
                <UButton
                  icon="i-lucide-x"
                  color="secondary"
                  variant="ghost"
                  size="xs"
                  class="ml-1 -mr-1"
                  @click="removeAccessGroupType(type)"
                />
              </UBadge>
              <UBadge
                v-if="accessGroupChildTypes.length === 0"
                color="warning"
                variant="subtle"
              >
                No default types configured
              </UBadge>
            </div>

            <div class="flex gap-2">
              <UInput
                v-model="newAccessGroupType"
                placeholder="Add new type (e.g., admin_team)"
                class="flex-1"
                @keyup.enter="addAccessGroupType"
              />
              <UButton
                icon="i-lucide-plus"
                label="Add"
                @click="addAccessGroupType"
              />
            </div>
          </div>
        </UCard>

        <!-- Save Actions -->
        <div class="flex items-center justify-between py-4">
          <div class="flex items-center gap-2">
            <UBadge v-if="hasChanges" color="warning" variant="subtle">
              Unsaved changes
            </UBadge>
          </div>
          <div class="flex gap-2">
            <UButton
              label="Reset"
              color="neutral"
              variant="outline"
              :disabled="!hasChanges || isSaving"
              @click="resetForm"
            />
            <UButton
              icon="i-lucide-save"
              label="Save Changes"
              :loading="isSaving"
              :disabled="!hasChanges"
              @click="saveChanges"
            />
          </div>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
