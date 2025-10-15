<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Row } from '@tanstack/table-core'
import { getPaginationRowModel } from '@tanstack/table-core'
import type { User } from '~/types/auth'

definePageMeta({
  layout: 'default'
})

const UAvatar = resolveComponent('UAvatar')
const UButton = resolveComponent('UButton')
const UBadge = resolveComponent('UBadge')
const UDropdownMenu = resolveComponent('UDropdownMenu')
const UCheckbox = resolveComponent('UCheckbox')

const usersStore = useUsersStore()
const toast = useToast()
const table = useTemplateRef('table')

// State
const search = ref('')
const statusFilter = ref<'all' | 'active' | 'inactive'>('all')
const columnFilters = ref([{ id: 'email', value: '' }])
const columnVisibility = ref()
const rowSelection = ref({})
const pagination = ref({
  pageIndex: 0,
  pageSize: 20
})

// Fetch users on mount
onMounted(async () => {
  await fetchUsers()
})

// Fetch users with current filters
const fetchUsers = async () => {
  const filters: any = {}

  if (search.value) {
    filters.search = search.value
  }

  if (statusFilter.value !== 'all') {
    filters.is_active = statusFilter.value === 'active'
  }

  await usersStore.fetchUsers(filters, {
    page: pagination.value.pageIndex + 1,
    limit: pagination.value.pageSize
  })
}

// Watch filters with debounce
watchDebounced([search, statusFilter], () => {
  pagination.value.pageIndex = 0
  fetchUsers()
}, { debounce: 300 })

watch(() => pagination.value.pageIndex, () => {
  fetchUsers()
})

// Get row action items
function getRowItems(row: Row<User>) {
  return [
    {
      type: 'label',
      label: 'Actions'
    },
    {
      label: 'View details',
      icon: 'i-lucide-eye',
      onSelect() {
        navigateTo(`/users/${row.original.id}`)
      }
    },
    {
      label: 'Edit user',
      icon: 'i-lucide-pencil',
      onSelect() {
        navigateTo(`/users/${row.original.id}/edit`)
      }
    },
    {
      type: 'separator'
    },
    {
      label: row.original.is_active ? 'Deactivate' : 'Activate',
      icon: row.original.is_active ? 'i-lucide-user-x' : 'i-lucide-user-check',
      onSelect: async () => {
        const action = row.original.is_active ? 'deactivate' : 'activate'
        const success = row.original.is_active
          ? await usersStore.deactivateUser(row.original.id)
          : await usersStore.activateUser(row.original.id)

        if (success) {
          toast.add({
            title: `User ${action}d`,
            description: `${row.original.full_name || row.original.username} has been ${action}d.`
          })
          await fetchUsers()
        } else {
          toast.add({
            title: 'Error',
            description: `Failed to ${action} user.`,
            color: 'error'
          })
        }
      }
    },
    {
      type: 'separator'
    },
    {
      label: 'Delete user',
      icon: 'i-lucide-trash',
      color: 'error',
      onSelect: async () => {
        if (confirm(`Are you sure you want to delete ${row.original.full_name || row.original.username}?`)) {
          const success = await usersStore.deleteUser(row.original.id)
          if (success) {
            toast.add({
              title: 'User deleted',
              description: `${row.original.full_name || row.original.username} has been deleted.`
            })
            await fetchUsers()
          } else {
            toast.add({
              title: 'Error',
              description: 'Failed to delete user.',
              color: 'error'
            })
          }
        }
      }
    }
  ]
}

// Table columns
const columns: TableColumn<User>[] = [
  {
    id: 'select',
    header: ({ table }) =>
      h(UCheckbox, {
        'modelValue': table.getIsSomePageRowsSelected()
          ? 'indeterminate'
          : table.getIsAllPageRowsSelected(),
        'onUpdate:modelValue': (value: boolean | 'indeterminate') =>
          table.toggleAllPageRowsSelected(!!value),
        'ariaLabel': 'Select all'
      }),
    cell: ({ row }) =>
      h(UCheckbox, {
        'modelValue': row.getIsSelected(),
        'onUpdate:modelValue': (value: boolean | 'indeterminate') => row.toggleSelected(!!value),
        'ariaLabel': 'Select row'
      })
  },
  {
    accessorKey: 'username',
    header: 'User',
    cell: ({ row }) => {
      const avatarUrl = row.original.metadata?.avatar || `https://api.dicebear.com/7.x/avataaars/svg?seed=${row.original.username}`

      return h('div', { class: 'flex items-center gap-3' }, [
        h(UAvatar, {
          src: avatarUrl,
          alt: row.original.full_name || row.original.username,
          size: 'lg'
        }),
        h('div', undefined, [
          h('p', { class: 'font-medium text-highlighted' }, row.original.full_name || row.original.username),
          h('p', { class: 'text-sm text-muted' }, `@${row.original.username}`)
        ])
      ])
    }
  },
  {
    accessorKey: 'email',
    header: 'Email',
    cell: ({ row }) => h('span', { class: 'text-sm' }, row.original.email)
  },
  {
    accessorKey: 'is_active',
    header: 'Status',
    cell: ({ row }) => {
      const color = row.original.is_active ? 'success' : 'error'
      const label = row.original.is_active ? 'Active' : 'Inactive'

      return h(UBadge, { variant: 'subtle', color }, () => label)
    }
  },
  {
    accessorKey: 'is_superuser',
    header: 'Role',
    cell: ({ row }) => {
      if (row.original.is_superuser) {
        return h(UBadge, { variant: 'subtle', color: 'primary' }, () => 'Superuser')
      }
      return h('span', { class: 'text-sm text-muted' }, row.original.metadata?.title || 'User')
    }
  },
  {
    id: 'actions',
    cell: ({ row }) => {
      return h(
        'div',
        { class: 'text-right' },
        h(
          UDropdownMenu,
          {
            content: { align: 'end' },
            items: getRowItems(row)
          },
          () =>
            h(UButton, {
              icon: 'i-lucide-ellipsis-vertical',
              color: 'neutral',
              variant: 'ghost',
              class: 'ml-auto'
            })
        )
      )
    }
  }
]
</script>

<template>
  <UDashboardPanel id="users">
    <template #header>
      <UDashboardNavbar title="Users">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            label="Create User"
            icon="i-lucide-user-plus"
            color="primary"
            @click="navigateTo('/users/create')"
          />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <!-- Filters -->
      <div class="flex flex-wrap items-center justify-between gap-1.5 mb-4">
        <UInput
          v-model="search"
          class="max-w-sm"
          icon="i-lucide-search"
          placeholder="Search users..."
        />

        <div class="flex flex-wrap items-center gap-1.5">
          <USelect
            v-model="statusFilter"
            :items="[
              { label: 'All', value: 'all' },
              { label: 'Active', value: 'active' },
              { label: 'Inactive', value: 'inactive' }
            ]"
            :ui="{ trailingIcon: 'group-data-[state=open]:rotate-180 transition-transform duration-200' }"
            placeholder="Filter status"
            class="min-w-28"
          />
        </div>
      </div>

      <!-- Table -->
      <UTable
        ref="table"
        v-model:column-filters="columnFilters"
        v-model:column-visibility="columnVisibility"
        v-model:row-selection="rowSelection"
        v-model:pagination="pagination"
        :pagination-options="{
          getPaginationRowModel: getPaginationRowModel()
        }"
        class="shrink-0"
        :data="usersStore.users"
        :columns="columns"
        :loading="usersStore.isLoading"
        :ui="{
          base: 'table-fixed border-separate border-spacing-0',
          thead: '[&>tr]:bg-elevated/50 [&>tr]:after:content-none',
          tbody: '[&>tr]:last:[&>td]:border-b-0',
          th: 'py-2 first:rounded-l-lg last:rounded-r-lg border-y border-default first:border-l last:border-r',
          td: 'border-b border-default'
        }"
      />

      <!-- Pagination -->
      <div class="flex items-center justify-between gap-3 border-t border-default pt-4 mt-auto">
        <div class="text-sm text-muted">
          Showing {{ usersStore.users.length }} of {{ usersStore.pagination.total }} users
        </div>

        <div class="flex items-center gap-1.5">
          <UPagination
            v-if="usersStore.pagination.pages > 1"
            :model-value="usersStore.pagination.page"
            :items-per-page="usersStore.pagination.limit"
            :total="usersStore.pagination.total"
            @update:model-value="(p: number) => { pagination.pageIndex = p - 1 }"
          />
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
