<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Role } from '~/types/role'
import { useQuery } from '@pinia/colada'
import { rolesQueries, useDeleteRoleMutation } from '~/queries/roles'

// Resolve components for use in cell renderers
const UButton = resolveComponent('UButton')
const UBadge = resolveComponent('UBadge')

const search = ref('')
const showCreateModal = ref(false)
const showEditModal = ref(false)
const selectedRoleId = ref('')

function openEditModal(roleId: string) {
    selectedRoleId.value = roleId
    showEditModal.value = true
}

// Reactive filters for query
const filters = computed(() => {
  const f: any = {}
  if (search.value) {
    f.search = search.value
  }
  return f
})

// Query roles with Pinia Colada (auto-fetches and auto-refetches when search changes)
const { data: rolesData, isLoading, error } = useQuery(
  () => rolesQueries.list(filters.value, { page: 1, limit: 100 })
)

// Mutations
const { mutate: deleteRole } = useDeleteRoleMutation()

// Table columns
const columns: TableColumn<Role>[] = [
  {
    accessorKey: 'name',
    header: 'Role',
    cell: ({ row }) => h('div', { class: 'flex flex-col gap-1' }, [
      h('p', { class: 'font-medium' }, row.original.display_name || row.original.name),
      h('p', { class: 'text-sm text-muted' }, row.original.name)
    ])
  },
  {
    accessorKey: 'permissions',
    header: 'Permissions',
    cell: ({ row }) => {
      const count = row.original.permissions?.length || 0
      return h('div', { class: 'flex items-center gap-2' }, [
        h('span', { class: 'text-sm' }, `${count} permission${count !== 1 ? 's' : ''}`),
        h('UBadge', {
          color: count > 0 ? 'primary' : 'neutral',
          variant: 'subtle',
          size: 'xs'
        }, () => count)
      ])
    }
  },
  {
    accessorKey: 'entity_type',
    header: 'Context',
    cell: ({ row }) => {
      if (row.original.entity_type) {
        return h('UBadge', {
          color: 'blue',
          variant: 'subtle'
        }, () => row.original.entity_type)
      }
      return h('span', { class: 'text-muted text-sm' }, 'Global')
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
        onClick: () => openEditModal(row.original.id)
      }),
      h(UButton, {
        icon: 'i-lucide-trash-2',
        color: 'error',
        variant: 'ghost',
        size: 'xs',
        onClick: async () => {
          if (confirm(`Are you sure you want to delete role "${row.original.display_name || row.original.name}"?`)) {
            await deleteRole(row.original.id)
          }
        }
      })
    ])
  }
]
</script>

<template>
  <UDashboardPanel id="roles">
    <template #header>
      <UDashboardNavbar title="Roles">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            icon="i-lucide-plus"
            label="Create Role"
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
            placeholder="Search roles..."
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
        :data="rolesData?.items || []"
      >
        <template #empty>
          <div class="flex flex-col items-center justify-center py-12 gap-4">
            <UIcon name="i-lucide-shield" class="w-12 h-12 text-muted" />
            <p class="text-muted">No roles found</p>
            <UButton
              icon="i-lucide-plus"
              label="Create your first role"
              variant="outline"
              @click="showCreateModal = true"
            />
          </div>
        </template>
      </UTable>

      <UPagination
        v-if="rolesData && rolesData.pages > 1"
        :model-value="rolesData.page"
        :total="rolesData.total"
        :page-size="rolesData.limit"
      />
    </template>
  </UDashboardPanel>

  <!-- Create Role Modal -->
  <RoleCreateModal v-model:open="showCreateModal" />

  <!-- Edit Role Modal -->
  <RoleUpdateModal
    v-if="selectedRoleId"
    v-model:open="showEditModal"
    :role-id="selectedRoleId"
  />
</template>
