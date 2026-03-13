<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Permission } from '~/types/role'
import { useQuery } from '@pinia/colada'
import { permissionsQueries, useDeletePermissionMutation } from '~/queries/permissions'

// Resolve components for use in cell renderers
const UButton = resolveComponent('UButton')
const UBadge = resolveComponent('UBadge')

const authStore = useAuthStore()
const permissionsStore = usePermissionsStore()
const search = ref('')
const showCreateModal = ref(false)
const showUpdateModal = ref(false)
const permissionToEdit = ref<Permission | null>(null)
const permissionForAbac = ref<Permission | null>(null)
const showAbacModal = ref(false)
const toast = useToast()
const canReadPermissions = computed(
  () => authStore.currentUser?.is_superuser || permissionsStore.hasPermission('permission:read')
)
const canCreatePermission = computed(
  () => authStore.currentUser?.is_superuser || permissionsStore.hasPermission('permission:create')
)
const canUpdatePermission = computed(
  () => authStore.currentUser?.is_superuser || permissionsStore.hasPermission('permission:update')
)
const canDeletePermission = computed(
  () => authStore.currentUser?.is_superuser || permissionsStore.hasPermission('permission:delete')
)
const canManagePermissionAbac = computed(
  () => authStore.features.abac && canReadPermissions.value && canUpdatePermission.value
)

// Query permissions with Pinia Colada (60s staleTime since permissions change rarely)
const { data: permissions, isLoading, error } = useQuery(
  () => permissionsQueries.available()
)

// Delete mutation
const { mutate: deletePermission, isLoading: isDeleting } = useDeletePermissionMutation()

// Handle delete permission
function handleDelete(permission: Permission) {
  if (!canDeletePermission.value) {
    toast.add({
      title: 'Not authorized',
      description: 'You do not have permission to delete permissions.',
      color: 'warning'
    })
    return
  }

  if (permission.is_system) {
    toast.add({
      title: 'Cannot delete',
      description: 'System permissions cannot be deleted',
      color: 'error'
    })
    return
  }

  deletePermission(permission.id)
}

// Handle edit permission
function handleEdit(permission: Permission) {
  if (!canUpdatePermission.value) {
    toast.add({
      title: 'Not authorized',
      description: 'You do not have permission to update permissions.',
      color: 'warning'
    })
    return
  }
  // Open edit modal with selected permission
  permissionToEdit.value = permission
  showUpdateModal.value = true
}

function handleAbac(permission: Permission) {
  permissionForAbac.value = permission
  showAbacModal.value = true
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
            color: 'info',
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
      canManagePermissionAbac.value && h(UButton, {
        icon: 'i-lucide-sliders-horizontal',
        color: 'secondary',
        variant: 'ghost',
        size: 'xs',
        disabled: !canUpdatePermission.value,
        onClick: () => handleAbac(row.original)
      }),
      h(UButton, {
        icon: 'i-lucide-pencil',
        color: 'neutral',
        variant: 'ghost',
        size: 'xs',
        disabled: !canUpdatePermission.value,
        onClick: () => handleEdit(row.original)
      }),
      h(UButton, {
        icon: 'i-lucide-trash-2',
        color: 'error',
        variant: 'ghost',
        size: 'xs',
        disabled: row.original.is_system || isDeleting || !canDeletePermission.value,
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
    <!-- Default slot for edge-to-edge table -->
    <div class="flex flex-col flex-1 min-h-0">
      <!-- Header -->
      <UDashboardNavbar title="Permissions">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            icon="i-lucide-plus"
            label="Create Permission"
            color="primary"
            :disabled="!canCreatePermission"
            @click="showCreateModal = true"
          />
        </template>
      </UDashboardNavbar>

      <!-- Toolbar -->
      <div class="flex items-center justify-between gap-2 px-4 py-3 border-b border-default">
        <UInput
          v-model="search"
          icon="i-lucide-search"
          placeholder="Search permissions..."
          class="w-64"
        />

      </div>

      <div v-if="!canReadPermissions" class="flex-1 flex flex-col items-center justify-center gap-4">
        <UIcon name="i-lucide-lock" class="w-12 h-12 text-warning" />
        <p class="text-muted">You do not have permission to view permissions.</p>
      </div>

      <!-- Loading State -->
      <div v-else-if="isLoading" class="flex-1 flex items-center justify-center">
        <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="flex-1 flex flex-col items-center justify-center gap-4">
        <UIcon name="i-lucide-alert-circle" class="w-12 h-12 text-error" />
        <p class="text-error">{{ error }}</p>
      </div>

      <!-- Table -->
      <UTable
        v-else
        sticky
        class="flex-1"
        :columns="columns"
        :data="filteredPermissions"
      >
        <template #empty>
          <div class="flex flex-col items-center justify-center py-12 gap-4">
            <UIcon name="i-lucide-shield-off" class="w-12 h-12 text-muted" />
            <p class="text-muted">No permissions found</p>
            <UButton
              v-if="canCreatePermission"
              icon="i-lucide-plus"
              label="Create your first permission"
              variant="outline"
              @click="showCreateModal = true"
            />
          </div>
        </template>
      </UTable>
    </div>
  </UDashboardPanel>

  <!-- Create Permission Modal -->
  <PermissionCreateModal v-if="canCreatePermission" v-model:open="showCreateModal" />

  <!-- Update Permission Modal -->
  <PermissionUpdateModal
    v-if="canUpdatePermission"
    v-model:open="showUpdateModal"
    :permission="permissionToEdit"
  />

  <AbacManagerModal
    v-if="permissionForAbac && canManagePermissionAbac"
    v-model:open="showAbacModal"
    subject-type="permission"
    :subject-id="permissionForAbac.id"
    :subject-name="permissionForAbac.display_name || permissionForAbac.name"
    :can-read="canManagePermissionAbac"
    :can-update="canUpdatePermission"
  />
</template>
