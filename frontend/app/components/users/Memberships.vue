<script setup lang="ts">
import type { User } from '~/types/auth.types'

const props = defineProps<{
  user: User
}>()

// Stores
const usersStore = useUsersStore()

// State
const memberships = ref<any[]>([])
const isLoading = ref(false)
const includeInactive = ref(false)

// Fetch memberships
const fetchMemberships = async () => {
  isLoading.value = true
  try {
    const response = await usersStore.fetchUserMemberships(props.user.id, includeInactive.value)
    memberships.value = response.memberships
  } finally {
    isLoading.value = false
  }
}

// Initial fetch
onMounted(() => {
  fetchMemberships()
})

// Watch for include inactive changes
watch(includeInactive, () => {
  fetchMemberships()
})

// Methods
const getMembershipStatus = (membership: any) => {
  if (membership.status !== 'active') return 'inactive'
  
  const now = new Date()
  if (membership.valid_from && new Date(membership.valid_from) > now) {
    return 'pending'
  }
  if (membership.valid_until && new Date(membership.valid_until) < now) {
    return 'expired'
  }
  
  return 'active'
}

const getMembershipStatusColor = (status: string) => {
  switch (status) {
    case 'active':
      return 'success'
    case 'pending':
      return 'warning'
    case 'expired':
    case 'inactive':
      return 'neutral'
    default:
      return 'neutral'
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Options -->
    <div class="flex items-center justify-between">
      <UCheckbox v-model="includeInactive">
        Show inactive memberships
      </UCheckbox>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="text-center py-8">
      <UIcon name="i-lucide-loader-2" class="h-6 w-6 animate-spin text-primary" />
    </div>

    <!-- Memberships List -->
    <div v-else-if="memberships.length > 0" class="space-y-3">
      <UCard v-for="membership in memberships" :key="`${membership.entity.id}-${membership.joined_at}`">
        <div class="space-y-3">
          <!-- Entity Info -->
          <div class="flex items-start justify-between">
            <div>
              <div class="flex items-center gap-2">
                <UIcon 
                  :name="membership.entity.entity_class === 'STRUCTURAL' ? 'i-lucide-building' : 'i-lucide-users'" 
                  class="h-4 w-4 text-gray-500"
                />
                <h5 class="font-medium">{{ membership.entity.display_name || membership.entity.name }}</h5>
                <UBadge size="xs" variant="subtle">
                  {{ membership.entity.entity_type }}
                </UBadge>
              </div>
              <p class="text-sm text-gray-500 mt-1">{{ membership.entity.slug }}</p>
            </div>
            
            <UBadge 
              :color="getMembershipStatusColor(getMembershipStatus(membership))" 
              variant="subtle"
            >
              {{ getMembershipStatus(membership) }}
            </UBadge>
          </div>

          <!-- Roles -->
          <div v-if="membership.roles.length > 0">
            <p class="text-sm font-medium mb-2">Roles:</p>
            <div class="flex flex-wrap gap-2">
              <UBadge 
                v-for="role in membership.roles" 
                :key="role.id"
                color="primary"
                variant="subtle"
                size="sm"
              >
                {{ role.display_name }}
              </UBadge>
            </div>
          </div>

          <!-- Metadata -->
          <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span class="text-gray-500">Joined:</span>
              <span class="ml-2">{{ usersStore.formatDate(membership.joined_at) }}</span>
            </div>
            <div v-if="membership.joined_by">
              <span class="text-gray-500">Added by:</span>
              <span class="ml-2">{{ membership.joined_by.full_name || membership.joined_by.email }}</span>
            </div>
          </div>

          <!-- Validity Period -->
          <div v-if="membership.valid_from || membership.valid_until" class="text-sm">
            <span class="text-gray-500">Valid:</span>
            <span class="ml-2">
              {{ membership.valid_from ? usersStore.formatDate(membership.valid_from) : 'Always' }}
              →
              {{ membership.valid_until ? usersStore.formatDate(membership.valid_until) : 'Forever' }}
            </span>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-8">
      <UIcon name="i-lucide-building" class="h-8 w-8 text-gray-400 mb-2" />
      <p class="text-sm text-gray-500">No memberships found</p>
    </div>
  </div>
</template>