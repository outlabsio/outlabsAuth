<script setup lang="ts">
import { h, resolveComponent } from 'vue'
import type { User } from '~/types/auth.types'
import type { TableColumn, TableRow } from '@nuxt/ui'

// Resolve components for use in table
const UButton = resolveComponent('UButton')
const UCheckbox = resolveComponent('UCheckbox')
const UBadge = resolveComponent('UBadge')
const UAvatar = resolveComponent('UAvatar')
const UDropdownMenu = resolveComponent('UDropdownMenu')

// Store
const usersStore = useUsersStore()
const contextStore = useContextStore()
const entitiesStore = useEntitiesStore()
const toast = useToast()

// Filter options
const statusOptions = [
  { label: "All", value: "" },
  { label: "Active", value: "active" },
  { label: "Inactive", value: "inactive" },
  { label: "Locked", value: "locked" },
]

const columnOptions = computed(() => {
  return table.value?.tableApi?.getAllColumns()
    .filter(column => column.getCanHide())
    .map(column => ({
      label: column.id === 'profile' ? 'User' : column.id.charAt(0).toUpperCase() + column.id.slice(1),
      type: 'checkbox' as const,
      checked: column.getIsVisible(),
      onUpdateChecked(checked: boolean) {
        table.value?.tableApi?.getColumn(column.id)?.toggleVisibility(!!checked)
      },
      onSelect(e?: Event) {
        e?.preventDefault()
      }
    })) || []
})

// Fetch users and entities on mount
onMounted(async () => {
  console.log('[UsersPage] Mounted - current context:', contextStore.selectedOrganization?.name)
  await Promise.all([
    usersStore.fetchUsers(),
    entitiesStore.fetchEntities()
  ])
})

// Watch for context changes
watch(() => contextStore.selectedOrganization, (newOrg, oldOrg) => {
  console.log('[UsersPage] Context changed from', oldOrg?.name, 'to', newOrg?.name)
  if (newOrg?.id !== oldOrg?.id) {
    usersStore.fetchUsers()
  }
})

// Entity options for filter
const entityOptions = computed(() => {
  const options = [{ label: "All Entities", value: "" }]
  if (entitiesStore.entities && Array.isArray(entitiesStore.entities)) {
    entitiesStore.entities.forEach(entity => {
      options.push({
        label: `${entity.display_name} (${entity.entity_type})`,
        value: entity.id
      })
    })
  }
  return options
})

// Methods
function handleSearch(search: string) {
  usersStore.setFilters({ search })
}

function handleStatusFilter(value: string) {
  usersStore.setFilters({ status: value || null })
}

function handleEntityFilter(value: string) {
  usersStore.setFilters({ entity_id: value || null })
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

async function handleStatusChange(user: User, newStatus: "active" | "inactive" | "locked") {
  try {
    await usersStore.updateUserStatus(user.id, newStatus)
    toast.add({
      title: 'Success',
      description: `User status updated to ${newStatus}`,
      color: 'success'
    })
  } catch (error: any) {
    toast.add({
      title: 'Error',
      description: error.message || 'Failed to update user status',
      color: 'error'
    })
  }
}

async function handlePasswordReset(user: User) {
  if (confirm(`Reset password for ${usersStore.getUserDisplayName(user)}?`)) {
    try {
      await usersStore.resetUserPassword(user.id)
      toast.add({
        title: 'Success',
        description: 'Password reset email sent',
        color: 'success'
      })
    } catch (error: any) {
      toast.add({
        title: 'Error',
        description: error.message || 'Failed to reset password',
        color: 'error'
      })
    }
  }
}

// Bulk actions
async function handleBulkAction() {
  const selectedRows = table.value?.tableApi?.getFilteredSelectedRowModel().rows || []
  if (selectedRows.length === 0) return
  
  const items = [[
    {
      label: 'Activate Selected',
      icon: 'i-lucide-check-circle',
      onSelect: async () => {
        if (confirm(`Activate ${selectedRows.length} users?`)) {
          await usersStore.bulkAction({
            user_ids: selectedRows.map(r => r.original.id),
            action: 'activate'
          })
          table.value?.tableApi?.resetRowSelection()
        }
      }
    },
    {
      label: 'Deactivate Selected',
      icon: 'i-lucide-x-circle',
      onSelect: async () => {
        if (confirm(`Deactivate ${selectedRows.length} users?`)) {
          await usersStore.bulkAction({
            user_ids: selectedRows.map(r => r.original.id),
            action: 'deactivate'
          })
          table.value?.tableApi?.resetRowSelection()
        }
      }
    },
    {
      label: 'Lock Selected',
      icon: 'i-lucide-lock',
      onSelect: async () => {
        if (confirm(`Lock ${selectedRows.length} users?`)) {
          await usersStore.bulkAction({
            user_ids: selectedRows.map(r => r.original.id),
            action: 'lock'
          })
          table.value?.tableApi?.resetRowSelection()
        }
      }
    }
  ]]
  
  return items
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

// Table columns definition
const columns: TableColumn<User>[] = [{
  id: 'select',
  header: ({ table }) => h(UCheckbox, {
    'modelValue': table.getIsSomePageRowsSelected() ? 'indeterminate' : table.getIsAllPageRowsSelected(),
    'onUpdate:modelValue': (value: boolean | 'indeterminate') => table.toggleAllPageRowsSelected(!!value),
    'aria-label': 'Select all'
  }),
  cell: ({ row }) => h(UCheckbox, {
    'modelValue': row.getIsSelected(),
    'onUpdate:modelValue': (value: boolean | 'indeterminate') => row.toggleSelected(!!value),
    'aria-label': 'Select row'
  }),
  enableSorting: false,
  enableHiding: false
}, {
  accessorKey: 'profile',
  header: 'User',
  cell: ({ row }) => {
    const user = row.original
    return h('div', { class: 'flex items-center gap-3' }, [
      h(UAvatar, {
        src: user.profile?.avatar_url,
        alt: usersStore.getUserDisplayName(user),
        size: 'md'
      }),
      h('div', undefined, [
        h('p', { class: 'font-medium text-highlighted' }, usersStore.getUserDisplayName(user)),
        h('p', { class: 'text-sm text-muted' }, user.email)
      ])
    ])
  },
  enableSorting: false
}, {
  accessorKey: 'entities',
  header: 'Entities',
  cell: ({ row }) => {
    const entities = row.original.entities || []
    if (entities.length === 0) {
      return h('span', { class: 'text-sm text-muted' }, 'No entities')
    }
    
    return h('div', { class: 'flex flex-wrap gap-1.5' }, [
      ...entities.slice(0, 2).map(entity => 
        h(UBadge, { 
          variant: 'subtle', 
          size: 'xs',
          key: entity.id 
        }, () => [
          entity.display_name || entity.name,
          entity.roles && entity.roles.length > 0 && h('span', { class: 'ml-1 text-muted' }, 
            `(${entity.roles.map(r => r.display_name).join(', ')})`
          )
        ])
      ),
      entities.length > 2 && h('span', { class: 'text-xs text-muted' }, `+${entities.length - 2} more`)
    ])
  },
  enableSorting: false
}, {
  accessorKey: 'is_active',
  header: 'Status',
  cell: ({ row }) => {
    const user = row.original
    const color = usersStore.getUserStatusColor(user)
    const status = usersStore.getUserStatus(user)
    
    return h('div', { class: 'flex items-center gap-2' }, [
      h(UBadge, { color, variant: 'subtle' }, () => status),
      user.email_verified && h('div', { class: 'group relative inline-flex' }, [
        h('div', { class: 'w-1.5 h-1.5 bg-green-500 rounded-full' }),
        h('div', { class: 'absolute inset-0 bg-green-500 rounded-full animate-ping opacity-75' })
      ])
    ])
  }
}, {
  accessorKey: 'last_login',
  header: 'Last Login',
  cell: ({ row }) => h('span', { class: 'text-sm text-muted' }, usersStore.formatDate(row.original.last_login))
}, {
  id: 'actions',
  enableHiding: false,
  cell: ({ row }) => {
    const user = row.original
    const items = getRowActions(user)
    
    return h('div', { class: 'text-right' }, h(UDropdownMenu, {
      'content': {
        align: 'end'
      },
      items,
      'aria-label': 'Actions dropdown'
    }, () => h(UButton, {
      'icon': 'i-lucide-ellipsis-vertical',
      'color': 'neutral',
      'variant': 'ghost',
      'class': 'ml-auto',
      'aria-label': 'Actions dropdown'
    })))
  }
}]

// Get row actions for dropdown
function getRowActions(user: User) {
  const actions = []
  
  actions.push([{
    label: 'View Details',
    icon: 'i-lucide-eye',
    onSelect: () => viewUser(user)
  }, {
    label: 'Edit',
    icon: 'i-lucide-edit',
    onSelect: () => editUser(user)
  }])
  
  actions.push([{
    label: 'Change Status',
    icon: 'i-lucide-toggle-left',
    disabled: true
  }])
  
  if (user.is_active) {
    actions.push([{
      label: 'Deactivate',
      icon: 'i-lucide-x-circle',
      onSelect: () => handleStatusChange(user, 'inactive')
    }])
  } else {
    actions.push([{
      label: 'Activate',
      icon: 'i-lucide-check-circle',
      onSelect: () => handleStatusChange(user, 'active')
    }])
  }
  
  if (!user.locked_until || new Date(user.locked_until) < new Date()) {
    actions.push([{
      label: 'Lock Account',
      icon: 'i-lucide-lock',
      onSelect: () => handleStatusChange(user, 'locked')
    }])
  }
  
  actions.push([{
    label: 'Reset Password',
    icon: 'i-lucide-key',
    onSelect: () => handlePasswordReset(user)
  }])
  
  return actions
}

// Table ref
const table = useTemplateRef('table')

// Row selection state
const rowSelection = ref<Record<string, boolean>>({})

// Handle row click
function onSelect(row: TableRow<User>) {
  viewUser(row.original)
}

// Watch for filter changes
watch(() => usersStore.filters, () => {
  usersStore.fetchUsers()
}, { deep: true })
</script>

<template>
  <UDashboardPanel>
    <template #header>
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
    </template>

    <template #body>
      <div class="space-y-6">
        <!-- Stats Cards -->
        <div v-if="usersStore.stats" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <UCard>
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-muted">Total Users</p>
                <p class="text-2xl font-bold">{{ usersStore.stats.total_users }}</p>
              </div>
              <UIcon name="i-lucide-users" class="h-8 w-8 text-primary" />
            </div>
          </UCard>
          
          <UCard>
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-muted">Active Users</p>
                <p class="text-2xl font-bold">{{ usersStore.stats.active_users }}</p>
              </div>
              <UIcon name="i-lucide-user-check" class="h-8 w-8 text-green-500" />
            </div>
          </UCard>
          
          <UCard>
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-muted">Recent Logins</p>
                <p class="text-2xl font-bold">{{ usersStore.stats.recent_logins }}</p>
                <p class="text-xs text-muted">Last 30 days</p>
              </div>
              <UIcon name="i-lucide-activity" class="h-8 w-8 text-blue-500" />
            </div>
          </UCard>
          
          <UCard>
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm text-muted">Locked Users</p>
                <p class="text-2xl font-bold">{{ usersStore.stats.locked_users }}</p>
              </div>
              <UIcon name="i-lucide-lock" class="h-8 w-8 text-red-500" />
            </div>
          </UCard>
        </div>

        <!-- Filters -->
        <UCard class="mb-6">
          <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 flex-1">
              <!-- Search -->
              <UInput
                :model-value="usersStore.filters.search"
                @update:model-value="handleSearch"
                placeholder="Search users..."
                icon="i-lucide-search"
                size="md"
              />

              <!-- Entity Filter -->
              <USelectMenu
                :model-value="usersStore.filters.entity_id || ''"
                @update:model-value="handleEntityFilter"
                :options="entityOptions"
                placeholder="All Entities"
                value-attribute="value"
                option-attribute="label"
              />

              <!-- Status Filter -->
              <USelectMenu
                :model-value="usersStore.filters.status || ''"
                @update:model-value="handleStatusFilter"
                :options="statusOptions"
                placeholder="All Statuses"
                value-attribute="value"
                option-attribute="label"
              />

              <!-- Reset Button -->
              <UButton 
                @click="usersStore.resetFilters" 
                variant="outline" 
                icon="i-lucide-rotate-ccw"
                :disabled="!usersStore.hasActiveFilters"
              >
                Reset
              </UButton>
            </div>
            
            <!-- Column Visibility -->
            <UDropdownMenu
              :items="columnOptions"
              :content="{ align: 'end' }"
            >
              <UButton
                label="Columns"
                color="neutral"
                variant="outline"
                trailing-icon="i-lucide-chevron-down"
                aria-label="Columns select dropdown"
              />
            </UDropdownMenu>
          </div>
        </UCard>

        <!-- Bulk Actions Bar -->
        <div 
          v-if="table?.tableApi?.getFilteredSelectedRowModel().rows.length > 0" 
          class="mb-4 flex items-center justify-between"
        >
          <div class="flex items-center gap-4">
            <span class="text-sm text-muted">
              {{ table?.tableApi?.getFilteredSelectedRowModel().rows.length }} selected
            </span>
            <UDropdownMenu
              :items="handleBulkAction()"
            >
              <UButton variant="outline" icon="i-lucide-more-horizontal">
                Bulk Actions
              </UButton>
            </UDropdownMenu>
          </div>
          <UButton 
            variant="ghost" 
            size="sm" 
            @click="table?.tableApi?.resetRowSelection()"
          >
            Clear Selection
          </UButton>
        </div>

        <!-- Loading State -->
        <div v-if="usersStore.isLoading" class="text-center py-12">
          <UIcon name="i-lucide-loader-2" class="h-8 w-8 animate-spin text-primary" />
          <p class="mt-2 text-neutral-600">Loading users...</p>
        </div>

        <!-- Error State -->
        <UAlert 
          v-else-if="usersStore.error" 
          color="error" 
          variant="subtle" 
          icon="i-lucide-alert-circle" 
          :title="usersStore.error" 
        />

        <!-- Users Table -->
        <div v-else-if="usersStore.users.length > 0">
          <UTable
            ref="table"
            v-model:row-selection="rowSelection"
            :data="usersStore.users"
            :columns="columns"
            :loading="usersStore.isLoading"
            sticky
            @select="onSelect"

          />
          
          <!-- Table Footer -->
          <div>
            {{ table?.tableApi?.getFilteredSelectedRowModel().rows.length || 0 }} of
            {{ table?.tableApi?.getFilteredRowModel().rows.length || 0 }} row(s) selected.
          </div>
        </div>

        <!-- Empty State -->
        <UCard v-else class="text-center py-12">
          <UIcon name="i-lucide-users" class="h-12 w-12 mb-4" />
          <h3 class="text-lg font-semibold mb-2">No users found</h3>
          <p class="mb-4">
            {{ usersStore.hasActiveFilters ? "Try adjusting your filters" : "Get started by creating your first user" }}
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
    </template>
  </UDashboardPanel>

  <!-- User Drawer -->
  <UsersDrawer 
    v-model:open="usersStore.ui.drawerOpen" 
    :user="usersStore.selectedUser" 
    :mode="usersStore.ui.drawerMode" 
    @created="handleUserCreated" 
    @updated="handleUserUpdated" 
    @deleted="handleUserDeleted" 
  />
</template>