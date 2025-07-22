<script setup lang="ts">
import type { User } from '~/types/auth.types'

// Store
const usersStore = useUsersStore()
const contextStore = useContextStore()
const entitiesStore = useEntitiesStore()

// Fetch users on mount
onMounted(async () => {
  await usersStore.fetchUsers()
})

// Methods
function handleSearch(search: string) {
  usersStore.setFilters({ search })
}

function openCreateDrawer() {
  usersStore.openDrawer('create')
}

function viewUser(user: User) {
  usersStore.openDrawer('view', user)
}

function editUser(user: User) {
  usersStore.openDrawer('edit', user)
}

function handleUserCreated() {
  usersStore.fetchUsers()
}

function handleUserUpdated() {
  usersStore.fetchUsers()
}

function handleUserDeleted() {
  usersStore.fetchUsers()
}

// Watch for filter changes
watch(() => usersStore.filters, () => {
  usersStore.fetchUsers()
}, { deep: true })
</script>

<template>
  <UDashboardPanel>
    <UDashboardNavbar title="Users">
      <template #left>
        <UDashboardSidebarCollapse />
      </template>
      <template #right>
        <UButton 
          icon="i-lucide-plus" 
          @click="openCreateDrawer"
        >
          Create User
        </UButton>
      </template>
    </UDashboardNavbar>

    <div class="px-4 py-6 lg:px-8">
        <!-- Search -->
        <div class="mb-6">
          <UInput
            :model-value="usersStore.filters.search"
            @update:model-value="handleSearch"
            placeholder="Search users..."
            icon="i-lucide-search"
            size="lg"
          />
        </div>

        <!-- Loading State -->
        <div v-if="usersStore.isLoading" class="text-center py-12">
          <UIcon name="i-lucide-loader-2" class="h-8 w-8 animate-spin text-primary" />
          <p class="mt-2 text-gray-600">Loading users...</p>
        </div>

        <!-- Error State -->
        <UAlert 
          v-else-if="usersStore.error" 
          color="error" 
          variant="subtle" 
          icon="i-lucide-alert-circle" 
          :title="usersStore.error" 
        />

        <!-- Users List -->
        <div v-else-if="usersStore.users.length > 0" class="space-y-4">
          <UCard 
            v-for="user in usersStore.users" 
            :key="user.id"
            @click="viewUser(user)"
            class="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <UAvatar 
                  :src="user.profile?.avatar_url" 
                  :alt="usersStore.getUserDisplayName(user)"
                  size="lg"
                />
                <div>
                  <h3 class="font-semibold">{{ usersStore.getUserDisplayName(user) }}</h3>
                  <p class="text-sm text-gray-500">{{ user.email }}</p>
                  <div v-if="user.entities && user.entities.length > 0" class="mt-1">
                    <UBadge 
                      v-for="entity in user.entities.slice(0, 2)" 
                      :key="entity.id"
                      variant="subtle"
                      size="xs"
                      class="mr-2"
                    >
                      {{ entity.name }}
                    </UBadge>
                    <span v-if="user.entities.length > 2" class="text-xs text-gray-500">
                      +{{ user.entities.length - 2 }} more
                    </span>
                  </div>
                </div>
              </div>
              
              <div class="flex items-center gap-4">
                <div class="text-right">
                  <UBadge 
                    :color="usersStore.getUserStatusColor(user)" 
                    variant="subtle"
                  >
                    {{ usersStore.getUserStatus(user) }}
                  </UBadge>
                  <p class="text-xs text-gray-500 mt-1">
                    Last login: {{ usersStore.formatDate(user.last_login) }}
                  </p>
                </div>
                
                <div class="flex gap-2">
                  <UButton 
                    variant="ghost" 
                    size="sm" 
                    icon="i-lucide-edit"
                    @click.stop="editUser(user)"
                  />
                </div>
              </div>
            </div>
          </UCard>
        </div>

        <!-- Empty State -->
        <UCard v-else class="text-center py-12">
          <UIcon name="i-lucide-users" class="h-12 w-12 text-gray-400 mb-4" />
          <h3 class="text-lg font-semibold mb-2">No users found</h3>
          <p class="text-gray-600 dark:text-gray-400 mb-4">
            {{ usersStore.hasActiveFilters ? "Try adjusting your search" : "Get started by creating your first user" }}
          </p>
          <UButton 
            v-if="!usersStore.hasActiveFilters" 
            icon="i-lucide-plus" 
            @click="openCreateDrawer"
          >
            Create User
          </UButton>
        </UCard>

        <!-- Pagination -->
        <div v-if="usersStore.totalPages > 1" class="mt-6 flex justify-center">
          <UPagination 
            :page="usersStore.currentPage" 
            :total="usersStore.totalUsers" 
            :items-per-page="usersStore.pageSize"
            @update:page="usersStore.setPage" 
          />
        </div>
    </div>

    <!-- User Drawer -->
    <UsersDrawer 
      v-model:open="usersStore.ui.drawerOpen" 
      :user="usersStore.selectedUser" 
      :mode="usersStore.ui.drawerMode" 
      @created="handleUserCreated" 
      @updated="handleUserUpdated" 
      @deleted="handleUserDeleted" 
    />
  </UDashboardPanel>
</template>