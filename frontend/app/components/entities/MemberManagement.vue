<template>
  <div class="space-y-4">
    <!-- Header with Add Member button -->
    <div class="flex justify-between items-center">
      <div>
        <h3 class="text-lg font-semibold">Members</h3>
        <p class="text-sm text-muted-foreground mt-1">
          Manage users who have access to this entity
        </p>
      </div>
      <UButton 
        icon="i-lucide-user-plus" 
        label="Add Member" 
        @click="openAddMemberModal"
        :disabled="!canAddMembers"
      />
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex justify-center py-8">
      <UIcon name="i-lucide-loader" class="h-6 w-6 animate-spin text-primary" />
    </div>

    <!-- Error State -->
    <UAlert 
      v-else-if="error" 
      color="error" 
      variant="subtle" 
      icon="i-lucide-alert-circle"
      :title="error"
      class="mb-4"
    />

    <!-- Members List -->
    <div v-else-if="members.length > 0" class="space-y-3">
      <UCard v-for="member in members" :key="member.id" class="p-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <UAvatar 
              :alt="member.user_name" 
              :label="getInitials(member.user_name)"
              size="md"
            />
            <div>
              <h4 class="font-medium">{{ member.user_name }}</h4>
              <p class="text-sm text-muted-foreground">{{ member.user_email }}</p>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <!-- Role Badge -->
            <UBadge 
              :label="member.role_name" 
              variant="subtle"
              color="primary"
            />

            <!-- Status Badge -->
            <UBadge 
              :label="member.status" 
              :color="member.status === 'active' ? 'success' : 'neutral'"
              variant="subtle"
              size="sm"
            />

            <!-- Actions Dropdown -->
            <UDropdownMenu :items="getMemberActions(member)" v-if="canManageMembers">
              <UButton 
                icon="i-lucide-more-vertical" 
                variant="ghost" 
                square
                size="sm"
              />
            </UDropdownMenu>
          </div>
        </div>

        <!-- Additional member info -->
        <div v-if="member.valid_from || member.valid_until" class="mt-3 pt-3 border-t text-sm text-muted-foreground">
          <div class="flex gap-4">
            <span v-if="member.valid_from">
              <strong>Valid from:</strong> {{ formatDate(member.valid_from) }}
            </span>
            <span v-if="member.valid_until">
              <strong>Valid until:</strong> {{ formatDate(member.valid_until) }}
            </span>
          </div>
        </div>
      </UCard>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-12">
      <UIcon name="i-lucide-users" class="h-12 w-12 mx-auto text-muted-foreground mb-3" />
      <h3 class="font-medium mb-1">No members yet</h3>
      <p class="text-muted-foreground">Add users to this entity to get started.</p>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex justify-center mt-6">
      <UPagination 
        :page="currentPage" 
        :total="total"
        :items-per-page="pageSize"
        @update:page="(page) => { currentPage = page; fetchMembers() }"
      />
    </div>

    <!-- Add Member Modal -->
    <AddMemberModal
      v-model:open="addMemberModalOpen"
      :entity-id="entityId"
      :entity-name="entityName"
      @member-added="handleMemberAdded"
    />

    <!-- Update Member Modal -->
    <UpdateMemberModal
      v-model:open="updateMemberModalOpen"
      :member="selectedMember"
      :entity-id="entityId"
      @member-updated="handleMemberUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import type { EntityMember } from '~/types/auth.types'

const props = defineProps<{
  entityId: string
  entityName: string
}>()

// Stores
const authStore = useAuthStore()
const userStore = useUserStore()
const contextStore = useContextStore()
const toast = useToast()

// State
const members = ref<EntityMember[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalPages = ref(1)
const total = ref(0)

// Modal state
const addMemberModalOpen = ref(false)
const updateMemberModalOpen = ref(false)
const selectedMember = ref<EntityMember | null>(null)

// Permission checks
const canAddMembers = computed(() => {
  // Check if user has member:create permission in this entity
  const hasPerm = userStore.hasPermission('member:create') || userStore.hasPermission('member:create_tree') || userStore.hasPermission('member:create_all')
  console.log('MemberManagement - canAddMembers:', hasPerm)
  console.log('User permissions:', userStore.permissions)
  console.log('User entities:', userStore.entities)
  return hasPerm
})

const canManageMembers = computed(() => {
  // Check if user has member:update or member:delete permissions
  return userStore.hasPermission('member:update') || userStore.hasPermission('member:delete') || 
         userStore.hasPermission('member:update_tree') || userStore.hasPermission('member:delete_tree') ||
         userStore.hasPermission('member:update_all') || userStore.hasPermission('member:delete_all')
})

// Fetch members
const fetchMembers = async () => {
  isLoading.value = true
  error.value = null

  try {
    const params = new URLSearchParams({
      page: currentPage.value.toString(),
      page_size: pageSize.value.toString()
    })

    const response = await authStore.apiCall<{
      items: EntityMember[]
      total: number
      page: number
      page_size: number
      total_pages: number
    }>(`/v1/entities/${props.entityId}/members?${params}`, {
      headers: contextStore.getContextHeaders
    })

    members.value = response.items
    total.value = response.total
    totalPages.value = response.total_pages
  } catch (err: any) {
    error.value = err.message || 'Failed to fetch members'
    console.error('Failed to fetch members:', err)
  } finally {
    isLoading.value = false
  }
}

// Get member actions
const getMemberActions = (member: EntityMember) => {
  const actions = []

  if (userStore.hasPermission('member:update') || userStore.hasPermission('member:update_tree') || userStore.hasPermission('member:update_all')) {
    actions.push([
      {
        label: 'Change Role',
        icon: 'i-lucide-shield',
        click: () => openUpdateMemberModal(member)
      },
      {
        label: 'Update Validity',
        icon: 'i-lucide-calendar',
        click: () => openUpdateMemberModal(member)
      }
    ])
  }

  if (userStore.hasPermission('member:delete') || userStore.hasPermission('member:delete_tree') || userStore.hasPermission('member:delete_all')) {
    actions.push([
      {
        label: 'Remove Member',
        icon: 'i-lucide-user-minus',
        color: 'error' as const,
        click: () => removeMember(member)
      }
    ])
  }

  return actions
}

// Open modals
const openAddMemberModal = () => {
  addMemberModalOpen.value = true
}

const openUpdateMemberModal = (member: EntityMember) => {
  selectedMember.value = member
  updateMemberModalOpen.value = true
}

// Remove member
const removeMember = async (member: EntityMember) => {
  const confirmed = confirm(`Remove ${member.user_name} from this entity?`)
  if (!confirmed) return

  try {
    await authStore.apiCall(`/v1/entities/${props.entityId}/members/${member.user_id}`, {
      method: 'DELETE',
      headers: contextStore.getContextHeaders
    })

    toast.add({
      title: 'Member removed',
      description: `${member.user_name} has been removed from this entity`,
      color: 'success'
    })

    // Refresh the list
    await fetchMembers()
  } catch (err: any) {
    toast.add({
      title: 'Failed to remove member',
      description: err.message || 'An error occurred',
      color: 'error'
    })
  }
}

// Handle events
const handleMemberAdded = () => {
  fetchMembers()
}

const handleMemberUpdated = () => {
  fetchMembers()
}

// Utilities
const getInitials = (name: string) => {
  return name
    .split(' ')
    .map(part => part.charAt(0))
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

// Fetch members on mount
onMounted(() => {
  console.log('[MemberManagement] Component mounted')
  console.log('[MemberManagement] User from store:', userStore.user)
  console.log('[MemberManagement] User permissions:', userStore.permissions)
  console.log('[MemberManagement] canAddMembers:', canAddMembers.value)
  fetchMembers()
})
</script>