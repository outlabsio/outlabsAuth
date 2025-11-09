<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Permission } from '~/types/role'
import { useQuery } from '@pinia/colada'
import { permissionsQueries, useDeletePermissionMutation } from '~/queries/permissions'

// Resolve components for use in cell renderers
const UButton = resolveComponent('UButton')
const UBadge = resolveComponent('UBadge')

const search = ref('')
const showCreateModal = ref(false)
const toast = useToast()

// Query permissions with Pinia Colada (60s staleTime since permissions change rarely)
const { data: permissions, isLoading, error } = useQuery(
  () => permissionsQueries.available()
)

// Delete mutation
const { mutate: deletePermission, isPending: isDeleting } = useDeletePermissionMutation()

// Handle delete permission
function handleDelete(permission: Permission) {
  if (permission.is_system) {
    toast.add({
      title: 'Cannot delete',
      description: 'System permissions cannot be deleted',
      color: 'error'
    })
    return
  }

  // TODO: Add confirmation dialog
  deletePermission(permission.id)
}

// Handle edit permission (placeholder)
function handleEdit(permission: Permission) {
  if (permission.is_system) {
    toast.add({
      title: 'Cannot edit',
      description: 'System permissions cannot be edited',
      color: 'warning'
    })
    return
  }

  // TODO: Open edit modal
  toast.add({
    title: 'Edit coming soon',
    description: `Edit functionality for "${permission.name}" will be available soon`,
    color: 'info'
  })
}

// Table columns
const columns: TableColumn<Permission>[] = [
  {
    accessorKey: 'name',
    header: 'Permission',
    cell: ({ row }) => {
      const isDeprecated = row.original.metadata?.deprecated
      return h('div', { class: 'flex flex-col gap-1' }, [
        h('div', { class: 'flex items-center gap-2' }, [
          h('p', {
            class: `font-mono text-sm font-medium ${isDeprecated ? 'line-through text-muted' : ''}`
          }, row.original.name),
          row.original.is_system && h(UBadge, {
            color: 'blue',
            variant: 'subtle',
            size: 'xs'
          }, () => 'System'),
          !row.original.is_active && h(UBadge, {
            color: 'neutral',
            variant: 'subtle',
            size: 'xs'
          }, () => 'Inactive')
        ]),
        h('p', { class: 'text-sm text-muted' }, row.original.display_name)
      ])
    }
  },
  {
    accessorKey: 'resource',
    header: 'Resource',
    cell: ({ row }) => h(UBadge, {
      color: row.original.resource === '*' ? 'error' : 'primary',
      variant: 'subtle'
    }, () => row.original.resource)
  },
  {
    accessorKey: 'action',
    header: 'Action',
    cell: ({ row }) => h(UBadge, {
      color: row.original.action === '*' ? 'error' : 'neutral',
      variant: 'outline'
    }, () => row.original.action)
  },
  {
    accessorKey: 'scope',
    header: 'Scope',
    cell: ({ row }) => {
      if (!row.original.scope) {
        return h('span', { class: 'text-sm text-muted' }, '-')
      }
      return h(UBadge, {
        color: 'purple',
        variant: 'subtle',
        size: 'xs'
      }, () => row.original.scope)
    }
  },
  {
    accessorKey: 'description',
    header: 'Description',
    cell: ({ row }) => h('span', { class: 'text-sm text-muted truncate max-w-md' },
      row.original.description || '-'
    )
  },
  {
    id: 'actions',
    header: 'Actions',
    cell: ({ row }) => h('div', { class: 'flex items-center gap-2' }, [
      h(UButton, {
        icon: 'i-lucide-pencil',
        color: 'neutral',
        variant: 'ghost',
        size: 'xs',
        disabled: row.original.is_system,
        onClick: () => handleEdit(row.original)
      }),
      h(UButton, {
        icon: 'i-lucide-trash-2',
        color: 'error',
        variant: 'ghost',
        size: 'xs',
        disabled: row.original.is_system || isDeleting,
        onClick: () => handleDelete(row.original)
      })
    ])
  }
]

// Filtered permissions based on search (client-side filtering)
const filteredPermissions = computed(() => {
  if (!permissions.value) return []
  if (!search.value) return permissions.value

  const searchLower = search.value.toLowerCase()
  return permissions.value.filter(permission =>
    permission.name.toLowerCase().includes(searchLower) ||
    permission.display_name.toLowerCase().includes(searchLower) ||
    permission.description?.toLowerCase().includes(searchLower) ||
    permission.resource.toLowerCase().includes(searchLower) ||
    permission.action.toLowerCase().includes(searchLower) ||
    permission.tags?.some(tag => tag.toLowerCase().includes(searchLower))
  )
})
</script>

<template>
  <UDashboardPanel id="permissions">
    <template #header>
      <UDashboardNavbar title="Permissions">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            icon="i-lucide-plus"
            label="Create Permission"
            color="primary"
            @click="showCreateModal = true"
          />
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <template #left>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            placeholder="Search permissions..."
            class="w-64"
          />
        </template>

        <template #right>
          <UButton
            icon="i-lucide-filter"
            color="neutral"
            variant="ghost"
            label="Filter"
          />
          <UButton
            icon="i-lucide-download"
            color="neutral"
            variant="ghost"
            label="Export"
          />
        </template>
      </UDashboardToolbar>
    </template>

    <template #body>
      <UCard v-if="isLoading">
        <div class="flex items-center justify-center py-12">
          <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
        </div>
      </UCard>

      <UCard v-else-if="error">
        <div class="flex flex-col items-center justify-center py-12 gap-4">
          <UIcon name="i-lucide-alert-circle" class="w-12 h-12 text-error" />
          <p class="text-error">{{ error }}</p>
        </div>
      </UCard>

      <UTable
        v-else
        :columns="columns"
        :data="filteredPermissions"
      >
        <template #empty>
          <div class="flex flex-col items-center justify-center py-12 gap-4">
            <UIcon name="i-lucide-shield-off" class="w-12 h-12 text-muted" />
            <p class="text-muted">No permissions found</p>
            <UButton
              icon="i-lucide-plus"
              label="Create your first permission"
              variant="outline"
              @click="showCreateModal = true"
            />
          </div>
        </template>
      </UTable>
    </template>
  </UDashboardPanel>

  <!-- Create Permission Modal -->
  <PermissionCreateModal v-model:open="showCreateModal" />
</template>
