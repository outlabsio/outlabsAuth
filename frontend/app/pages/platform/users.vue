<template>
  <div class="space-y-6">
    <!-- Header -->
    <div>
      <UBreadcrumb :items="breadcrumbItems" class="mb-4" />
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold">Platform Users</h1>
          <p class="text-muted-foreground mt-1">
            Manage all users across the platform
          </p>
        </div>
        <UButton icon="i-lucide-user-plus" @click="showCreateModal = true">
          Create User
        </UButton>
      </div>
    </div>

    <!-- Filters -->
    <UCard>
      <div class="flex gap-4 items-end">
        <div class="flex-1">
          <UInput
            v-model="filters.search"
            placeholder="Search by name or email..."
            icon="i-lucide-search"
            size="lg"
            @input="debouncedFetch"
          />
        </div>
        <USelect
          v-model="filters.status"
          :items="statusOptions"
          placeholder="All statuses"
          class="w-48"
          @change="fetchUsers"
        />
        <UButton variant="outline" icon="i-lucide-refresh-cw" @click="resetFilters">
          Reset
        </UButton>
      </div>
    </UCard>

    <!-- Users Table -->
    <UCard>
      <UTable
        :columns="columns"
        :rows="users"
        :loading="isLoading"
        :ui="{ td: { padding: 'py-3' } }"
      >
        <!-- User Cell -->
        <template #user-data="{ row }">
          <div class="flex items-center gap-3">
            <UAvatar 
              :label="getInitials(row.profile?.first_name, row.profile?.last_name, row.email)" 
              size="sm"
            />
            <div>
              <p class="font-medium">
                {{ row.profile?.first_name && row.profile?.last_name 
                  ? `${row.profile.first_name} ${row.profile.last_name}` 
                  : row.email }}
              </p>
              <p class="text-sm text-muted-foreground">{{ row.email }}</p>
            </div>
          </div>
        </template>

        <!-- Status Cell -->
        <template #status-data="{ row }">
          <UBadge 
            :color="row.is_active ? 'success' : 'error'" 
            variant="subtle"
          >
            {{ row.is_active ? 'Active' : 'Inactive' }}
          </UBadge>
        </template>

        <!-- Entities Cell -->
        <template #entities-data="{ row }">
          <div class="flex items-center gap-2">
            <span class="text-sm">{{ row.entities?.length || 0 }} entities</span>
            <UTooltip v-if="row.entities?.length > 0">
              <UButton variant="ghost" size="xs" icon="i-lucide-info" />
              <template #content>
                <div class="space-y-1">
                  <p v-for="entity in row.entities" :key="entity.id" class="text-xs">
                    {{ entity.display_name || entity.name }}
                  </p>
                </div>
              </template>
            </UTooltip>
          </div>
        </template>

        <!-- Roles Cell -->
        <template #roles-data="{ row }">
          <div class="text-sm">
            {{ getTotalRoleCount(row) }} roles
          </div>
        </template>

        <!-- Type Cell -->
        <template #type-data="{ row }">
          <UBadge 
            :color="row.is_system_user ? 'primary' : 'neutral'" 
            variant="subtle"
          >
            {{ row.is_system_user ? 'System' : 'Regular' }}
          </UBadge>
        </template>

        <!-- Created Cell -->
        <template #created-data="{ row }">
          <span class="text-sm text-muted-foreground">
            {{ formatDate(row.created_at) }}
          </span>
        </template>

        <!-- Actions Cell -->
        <template #actions-data="{ row }">
          <UDropdown :items="getActions(row)">
            <UButton variant="ghost" icon="i-lucide-more-vertical" size="sm" />
          </UDropdown>
        </template>
      </UTable>

      <!-- Pagination -->
      <template v-if="totalPages > 1" #footer>
        <div class="flex items-center justify-between py-3">
          <p class="text-sm text-muted-foreground">
            Showing {{ startItem }}-{{ endItem }} of {{ totalUsers }} users
          </p>
          <UPagination
            :page="currentPage"
            :total="totalUsers"
            :items-per-page="pageSize"
            @update:page="(page) => { currentPage = page; fetchUsers() }"
          />
        </div>
      </template>
    </UCard>

    <!-- User Details Slideover -->
    <USlideover v-model="showUserDetails">
      <UCard v-if="selectedUser">
        <template #header>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold">User Details</h3>
            <UButton 
              icon="i-lucide-x" 
              variant="ghost" 
              square
              size="sm"
              @click="showUserDetails = false"
            />
          </div>
        </template>

        <div class="space-y-6">
          <!-- User Info -->
          <div class="flex items-center gap-4">
            <UAvatar 
              :label="getInitials(selectedUser.profile?.first_name, selectedUser.profile?.last_name, selectedUser.email)" 
              size="lg"
            />
            <div>
              <h4 class="text-lg font-medium">
                {{ selectedUser.profile?.first_name && selectedUser.profile?.last_name 
                  ? `${selectedUser.profile.first_name} ${selectedUser.profile.last_name}` 
                  : selectedUser.email }}
              </h4>
              <p class="text-sm text-muted-foreground">{{ selectedUser.email }}</p>
              <div class="flex gap-2 mt-2">
                <UBadge 
                  :color="selectedUser.is_active ? 'success' : 'error'" 
                  variant="subtle"
                >
                  {{ selectedUser.is_active ? 'Active' : 'Inactive' }}
                </UBadge>
                <UBadge 
                  v-if="selectedUser.is_system_user"
                  color="primary" 
                  variant="subtle"
                >
                  System User
                </UBadge>
              </div>
            </div>
          </div>

          <UDivider />

          <!-- Contact Info -->
          <div class="space-y-3">
            <h5 class="text-sm font-medium">Contact Information</h5>
            <div class="space-y-2 text-sm">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-mail" class="text-muted-foreground" />
                <span>{{ selectedUser.email }}</span>
              </div>
              <div v-if="selectedUser.profile?.phone" class="flex items-center gap-2">
                <UIcon name="i-lucide-phone" class="text-muted-foreground" />
                <span>{{ selectedUser.profile.phone }}</span>
              </div>
            </div>
          </div>

          <UDivider />

          <!-- Entity Memberships -->
          <div class="space-y-3">
            <h5 class="text-sm font-medium">Entity Memberships</h5>
            <div v-if="selectedUser.entities?.length > 0" class="space-y-2">
              <UCard v-for="entity in selectedUser.entities" :key="entity.id" class="p-3">
                <div class="space-y-1">
                  <p class="font-medium text-sm">{{ entity.display_name || entity.name }}</p>
                  <p class="text-xs text-muted-foreground">{{ entity.entity_type }}</p>
                  <div class="flex flex-wrap gap-1 mt-2">
                    <UBadge 
                      v-for="role in entity.roles" 
                      :key="role.id"
                      size="xs"
                      variant="subtle"
                    >
                      {{ role.display_name || role.name }}
                    </UBadge>
                  </div>
                </div>
              </UCard>
            </div>
            <p v-else class="text-sm text-muted-foreground">No entity memberships</p>
          </div>

          <UDivider />

          <!-- Account Info -->
          <div class="space-y-3">
            <h5 class="text-sm font-medium">Account Information</h5>
            <div class="space-y-2 text-sm">
              <div>
                <span class="text-muted-foreground">Created:</span>
                <span class="ml-2">{{ formatDate(selectedUser.created_at) }}</span>
              </div>
              <div v-if="selectedUser.last_login">
                <span class="text-muted-foreground">Last Login:</span>
                <span class="ml-2">{{ formatDate(selectedUser.last_login) }}</span>
              </div>
              <div v-if="selectedUser.email_verified">
                <span class="text-muted-foreground">Email Verified:</span>
                <span class="ml-2">{{ formatDate(selectedUser.email_verified) }}</span>
              </div>
            </div>
          </div>
        </div>

        <template #footer>
          <div class="flex gap-3">
            <UButton variant="outline" block @click="editUser(selectedUser)">
              <UIcon name="i-lucide-edit" class="mr-2" />
              Edit User
            </UButton>
            <UButton 
              variant="outline" 
              color="error" 
              @click="confirmDeleteUser(selectedUser)"
            >
              <UIcon name="i-lucide-trash" />
            </UButton>
          </div>
        </template>
      </UCard>
    </USlideover>

    <!-- Create/Edit Modal -->
    <UserFormModal
      v-model="showFormModal"
      :mode="formMode"
      :user="formUser"
      @saved="onUserSaved"
    />

    <!-- Delete Confirmation -->
    <ConfirmationModal
      v-model="showDeleteConfirm"
      title="Delete User"
      :description="`Are you sure you want to delete ${userToDelete?.email}? This action cannot be undone.`"
      confirm-text="Delete"
      confirm-color="error"
      @confirm="deleteUser"
    />
  </div>
</template>

<script setup lang="ts">
import type { User } from '~/types/auth.types'

// Stores
const authStore = useAuthStore()
const contextStore = useContextStore()
const router = useRouter()
const toast = useToast()

// State
const users = ref<User[]>([])
const isLoading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalUsers = ref(0)
const showUserDetails = ref(false)
const selectedUser = ref<User | null>(null)
const showFormModal = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const formUser = ref<User | null>(null)
const showDeleteConfirm = ref(false)
const userToDelete = ref<User | null>(null)

// Filters
const filters = reactive({
  search: '',
  status: 'all'
})

// Breadcrumb
const breadcrumbItems = [
  { label: 'Platform', to: '/platform' },
  { label: 'Users' }
]

// Table columns
const columns = [
  { key: 'user', label: 'User' },
  { key: 'status', label: 'Status' },
  { key: 'entities', label: 'Entities' },
  { key: 'roles', label: 'Roles' },
  { key: 'type', label: 'Type' },
  { key: 'created', label: 'Created' },
  { key: 'actions', label: '' }
]

// Status options
const statusOptions = [
  { value: 'all', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' }
]

// Computed
const totalPages = computed(() => Math.ceil(totalUsers.value / pageSize.value))
const startItem = computed(() => (currentPage.value - 1) * pageSize.value + 1)
const endItem = computed(() => Math.min(currentPage.value * pageSize.value, totalUsers.value))

// Methods
const fetchUsers = async () => {
  isLoading.value = true
  try {
    const params = new URLSearchParams({
      page: currentPage.value.toString(),
      page_size: pageSize.value.toString()
    })

    if (filters.search) {
      params.append('search', filters.search)
    }

    if (filters.status !== 'all') {
      params.append('is_active', filters.status === 'active' ? 'true' : 'false')
    }

    const response = await authStore.apiCall<{ items: User[], total: number }>(
      `/v1/users?${params}`,
      { headers: contextStore.getContextHeaders }
    )

    users.value = response.items
    totalUsers.value = response.total
  } catch (error: any) {
    toast.add({
      title: 'Failed to fetch users',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    isLoading.value = false
  }
}

// Debounced search
let searchTimeout: NodeJS.Timeout | null = null
const debouncedFetch = () => {
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  searchTimeout = setTimeout(() => {
    currentPage.value = 1
    fetchUsers()
  }, 300)
}

const resetFilters = () => {
  filters.search = ''
  filters.status = 'all'
  currentPage.value = 1
  fetchUsers()
}

const getInitials = (firstName?: string, lastName?: string, email?: string) => {
  if (firstName && lastName) {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase()
  }
  return email?.substring(0, 2).toUpperCase() || 'U'
}

const getTotalRoleCount = (user: User) => {
  if (!user.entities) return 0
  return user.entities.reduce((count, entity) => count + (entity.roles?.length || 0), 0)
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}

const viewUserDetails = (user: User) => {
  selectedUser.value = user
  showUserDetails.value = true
}

const editUser = (user: User) => {
  formUser.value = user
  formMode.value = 'edit'
  showFormModal.value = true
  showUserDetails.value = false
}

const confirmDeleteUser = (user: User) => {
  userToDelete.value = user
  showDeleteConfirm.value = true
}

const deleteUser = async () => {
  if (!userToDelete.value) return

  try {
    await authStore.apiCall(`/v1/users/${userToDelete.value.id}`, {
      method: 'DELETE',
      headers: contextStore.getContextHeaders
    })

    toast.add({
      title: 'User deleted',
      description: 'User has been successfully deleted',
      color: 'success'
    })

    fetchUsers()
  } catch (error: any) {
    toast.add({
      title: 'Failed to delete user',
      description: error.message || 'An error occurred',
      color: 'error'
    })
  } finally {
    showDeleteConfirm.value = false
    userToDelete.value = null
  }
}

const onUserSaved = () => {
  fetchUsers()
  showFormModal.value = false
}

const getActions = (user: User) => [
  [{
    label: 'View Details',
    icon: 'i-lucide-eye',
    click: () => viewUserDetails(user)
  }],
  [{
    label: 'Edit',
    icon: 'i-lucide-edit',
    click: () => editUser(user)
  }],
  [{
    label: 'Delete',
    icon: 'i-lucide-trash',
    color: 'error' as const,
    click: () => confirmDeleteUser(user)
  }]
]

// Check permissions
const canAccessPlatformUsers = computed(() => {
  return authStore.currentUser?.is_system_user || false
})

// Redirect if not authorized
onMounted(() => {
  if (!canAccessPlatformUsers.value) {
    router.push('/')
  } else {
    fetchUsers()
  }
})

// SEO
useHead({
  title: 'Platform Users',
  meta: [
    {
      name: 'description',
      content: 'Manage all users across the platform'
    }
  ]
})
</script>