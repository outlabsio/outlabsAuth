<script setup lang="ts">
import type { User } from '~/types/auth.types'

const props = defineProps<{
  user: User
}>()

const emit = defineEmits<{
  edit: []
}>()

// Stores
const usersStore = useUsersStore()

// Format date helper
const formatDate = (date: string | null | undefined) => {
  if (!date) return 'Never'
  return new Date(date).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<template>
  <div class="space-y-6">
    <!-- Basic Information -->
    <div>
      <h3 class="text-lg font-semibold mb-4">Basic Information</h3>
      <div class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-muted-foreground">Email</label>
            <p class="mt-1 font-medium">{{ user.email }}</p>
          </div>
          <div>
            <label class="text-sm font-medium text-muted-foreground">Status</label>
            <div class="mt-1">
              <UBadge 
                :color="usersStore.getUserStatusColor(user)" 
                variant="subtle"
              >
                {{ usersStore.getUserStatus(user) }}
              </UBadge>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-muted-foreground">First Name</label>
            <p class="mt-1">{{ user.profile.first_name || '-' }}</p>
          </div>
          <div>
            <label class="text-sm font-medium text-muted-foreground">Last Name</label>
            <p class="mt-1">{{ user.profile.last_name || '-' }}</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-muted-foreground">Phone</label>
            <p class="mt-1">{{ user.profile.phone || '-' }}</p>
          </div>
          <div>
            <label class="text-sm font-medium text-muted-foreground">Email Verified</label>
            <div class="mt-1">
              <UIcon 
                v-if="user.email_verified"
                name="i-lucide-check-circle" 
                class="h-5 w-5 text-green-500"
              />
              <UIcon 
                v-else
                name="i-lucide-x-circle" 
                class="h-5 w-5 text-gray-400"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Account Information -->
    <div>
      <h3 class="text-lg font-semibold mb-4">Account Information</h3>
      <div class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-muted-foreground">Created</label>
            <p class="mt-1 text-sm">{{ formatDate(user.created_at) }}</p>
          </div>
          <div>
            <label class="text-sm font-medium text-muted-foreground">Last Login</label>
            <p class="mt-1 text-sm">{{ formatDate(user.last_login) }}</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-muted-foreground">Last Password Change</label>
            <p class="mt-1 text-sm">{{ formatDate(user.last_password_change) }}</p>
          </div>
          <div>
            <label class="text-sm font-medium text-muted-foreground">System User</label>
            <div class="mt-1">
              <UBadge 
                v-if="user.is_system_user"
                color="neutral" 
                variant="subtle"
                size="xs"
              >
                System
              </UBadge>
              <span v-else class="text-sm text-gray-500">No</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Entity Memberships -->
    <div v-if="user.entities && user.entities.length > 0">
      <h3 class="text-lg font-semibold mb-4">Entity Memberships</h3>
      <div class="space-y-3">
        <UCard v-for="entity in user.entities" :key="entity.id">
          <div class="flex items-center justify-between">
            <div>
              <h4 class="font-medium">{{ entity.display_name }}</h4>
              <p class="text-sm text-gray-500">{{ entity.entity_type }}</p>
              <div v-if="entity.roles && entity.roles.length > 0" class="mt-2 flex flex-wrap gap-2">
                <UBadge 
                  v-for="role in entity.roles" 
                  :key="role.id"
                  variant="subtle"
                  size="xs"
                >
                  {{ role.display_name }}
                </UBadge>
              </div>
            </div>
            <div class="text-right">
              <UBadge 
                :color="entity.status === 'active' ? 'success' : 'neutral'" 
                variant="subtle"
                size="xs"
              >
                {{ entity.status }}
              </UBadge>
            </div>
          </div>
        </UCard>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-2 pt-4">
      <UButton
        icon="i-lucide-pencil"
        @click="emit('edit')"
      >
        Edit User
      </UButton>
    </div>
  </div>
</template>