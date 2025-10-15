<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Role } from '~/types/role'

const rolesStore = useRolesStore()
const search = ref('')

// Fetch roles on mount
onMounted(async () => {
  await rolesStore.fetchRoles()
})

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
        onClick: () => console.log('Edit role:', row.original.id)
      }),
      h(UButton, {
        icon: 'i-lucide-trash-2',
        color: 'error',
        variant: 'ghost',
        size: 'xs',
        onClick: () => console.log('Delete role:', row.original.id)
      })
    ])
  }
]

// Filtered roles based on search
const filteredRoles = computed(() => {
  if (!search.value) return rolesStore.roles

  const searchLower = search.value.toLowerCase()
  return rolesStore.roles.filter(role =>
    role.name.toLowerCase().includes(searchLower) ||
    role.display_name?.toLowerCase().includes(searchLower) ||
    role.description?.toLowerCase().includes(searchLower)
  )
})
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
      <UCard v-if="rolesStore.isLoading">
        <div class="flex items-center justify-center py-12">
          <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
        </div>
      </UCard>

      <UCard v-else-if="rolesStore.error">
        <div class="flex flex-col items-center justify-center py-12 gap-4">
          <UIcon name="i-lucide-alert-circle" class="w-12 h-12 text-error" />
          <p class="text-error">{{ rolesStore.error }}</p>
          <UButton
            icon="i-lucide-refresh-cw"
            label="Retry"
            @click="rolesStore.fetchRoles()"
          />
        </div>
      </UCard>

      <UTable
        v-else
        :columns="columns"
        :rows="filteredRoles"
      >
        <template #empty>
          <div class="flex flex-col items-center justify-center py-12 gap-4">
            <UIcon name="i-lucide-shield" class="w-12 h-12 text-muted" />
            <p class="text-muted">No roles found</p>
            <UButton
              icon="i-lucide-plus"
              label="Create your first role"
              variant="outline"
            />
          </div>
        </template>
      </UTable>

      <UDashboardPagination
        v-if="rolesStore.pagination.pages > 1"
        v-model="rolesStore.pagination.page"
        :total="rolesStore.pagination.total"
        :page-size="rolesStore.pagination.limit"
      />
    </template>
  </UDashboardPanel>
</template>
