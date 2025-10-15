<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'

const permissionsStore = usePermissionsStore()
const search = ref('')
const scopeFilter = ref<'all' | 'global' | 'tree'>('all')

// Mock permissions data for display
const permissions = ref([
  { resource: 'user', action: 'create', scope: 'global', description: 'Create new users' },
  { resource: 'user', action: 'read', scope: 'tree', description: 'View users in entity tree' },
  { resource: 'user', action: 'update', scope: 'global', description: 'Update user details' },
  { resource: 'user', action: 'delete', scope: 'global', description: 'Delete users' },
  { resource: 'role', action: 'create', scope: 'global', description: 'Create new roles' },
  { resource: 'role', action: 'read', scope: 'tree', description: 'View roles in entity tree' },
  { resource: 'role', action: 'update', scope: 'global', description: 'Update role details' },
  { resource: 'role', action: 'delete', scope: 'global', description: 'Delete roles' },
  { resource: 'entity', action: 'create', scope: 'tree', description: 'Create entities' },
  { resource: 'entity', action: 'read', scope: 'tree', description: 'View entities in tree' },
  { resource: 'entity', action: 'update', scope: 'tree', description: 'Update entity details' },
  { resource: 'entity', action: 'delete', scope: 'tree', description: 'Delete entities' },
  { resource: 'permission', action: 'read', scope: 'global', description: 'View permissions' },
  { resource: 'permission', action: 'grant', scope: 'global', description: 'Grant permissions to roles' },
  { resource: 'api_key', action: 'create', scope: 'global', description: 'Create API keys' },
  { resource: 'api_key', action: 'read', scope: 'global', description: 'View API keys' },
  { resource: 'api_key', action: 'revoke', scope: 'global', description: 'Revoke API keys' }
])

// Table columns
const columns: TableColumn<typeof permissions.value[0]>[] = [
  {
    accessorKey: 'resource',
    header: 'Resource',
    cell: ({ row }) => h('div', { class: 'flex items-center gap-2' }, [
      h('UIcon', { name: 'i-lucide-database', class: 'w-4 h-4 text-primary' }),
      h('span', { class: 'font-medium' }, row.original.resource)
    ])
  },
  {
    accessorKey: 'action',
    header: 'Action',
    cell: ({ row }) => {
      const actionColors: Record<string, string> = {
        create: 'green',
        read: 'blue',
        update: 'yellow',
        delete: 'red',
        grant: 'purple',
        revoke: 'orange'
      }
      return h('UBadge', {
        color: actionColors[row.original.action] || 'neutral',
        variant: 'subtle'
      }, () => row.original.action)
    }
  },
  {
    accessorKey: 'scope',
    header: 'Scope',
    cell: ({ row }) => {
      const icon = row.original.scope === 'tree' ? 'i-lucide-git-branch' : 'i-lucide-globe'
      return h('div', { class: 'flex items-center gap-2' }, [
        h('UIcon', { name: icon, class: 'w-4 h-4' }),
        h('span', { class: 'text-sm' }, row.original.scope === 'tree' ? 'Tree' : 'Global')
      ])
    }
  },
  {
    accessorKey: 'description',
    header: 'Description',
    cell: ({ row }) => h('span', { class: 'text-sm text-muted' },
      row.original.description
    )
  },
  {
    id: 'permission_string',
    header: 'Permission String',
    cell: ({ row }) => {
      const suffix = row.original.scope === 'tree' ? '_tree' : ''
      const permString = `${row.original.resource}:${row.original.action}${suffix}`
      return h('code', { class: 'text-xs bg-neutral-100 dark:bg-neutral-800 px-2 py-1 rounded' },
        permString
      )
    }
  }
]

// Filtered permissions
const filteredPermissions = computed(() => {
  let result = permissions.value

  // Apply scope filter
  if (scopeFilter.value !== 'all') {
    result = result.filter(perm => perm.scope === scopeFilter.value)
  }

  // Apply search filter
  if (search.value) {
    const searchLower = search.value.toLowerCase()
    result = result.filter(perm =>
      perm.resource.toLowerCase().includes(searchLower) ||
      perm.action.toLowerCase().includes(searchLower) ||
      perm.description.toLowerCase().includes(searchLower)
    )
  }

  return result
})

// Stats
const stats = computed(() => ({
  total: permissions.value.length,
  global: permissions.value.filter(p => p.scope === 'global').length,
  tree: permissions.value.filter(p => p.scope === 'tree').length,
  resources: new Set(permissions.value.map(p => p.resource)).size
}))
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
            icon="i-lucide-info"
            label="Permission Guide"
            color="neutral"
            variant="outline"
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

          <UButtonGroup>
            <UButton
              :color="scopeFilter === 'all' ? 'primary' : 'neutral'"
              :variant="scopeFilter === 'all' ? 'solid' : 'ghost'"
              label="All"
              @click="scopeFilter = 'all'"
            />
            <UButton
              :color="scopeFilter === 'global' ? 'primary' : 'neutral'"
              :variant="scopeFilter === 'global' ? 'solid' : 'ghost'"
              label="Global"
              @click="scopeFilter = 'global'"
            />
            <UButton
              :color="scopeFilter === 'tree' ? 'primary' : 'neutral'"
              :variant="scopeFilter === 'tree' ? 'solid' : 'ghost'"
              label="Tree"
              @click="scopeFilter = 'tree'"
            />
          </UButtonGroup>
        </template>

        <template #right>
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
      <!-- Stats Cards -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Total Permissions</p>
              <p class="text-2xl font-bold mt-1">{{ stats.total }}</p>
            </div>
            <UIcon name="i-lucide-lock" class="w-8 h-8 text-primary" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Global Scope</p>
              <p class="text-2xl font-bold mt-1">{{ stats.global }}</p>
            </div>
            <UIcon name="i-lucide-globe" class="w-8 h-8 text-blue-500" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Tree Scope</p>
              <p class="text-2xl font-bold mt-1">{{ stats.tree }}</p>
            </div>
            <UIcon name="i-lucide-git-branch" class="w-8 h-8 text-green-500" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Resources</p>
              <p class="text-2xl font-bold mt-1">{{ stats.resources }}</p>
            </div>
            <UIcon name="i-lucide-database" class="w-8 h-8 text-purple-500" />
          </div>
        </UCard>
      </div>

      <UTable
        :columns="columns"
        :rows="filteredPermissions"
      >
        <template #empty>
          <div class="flex flex-col items-center justify-center py-12 gap-4">
            <UIcon name="i-lucide-lock" class="w-12 h-12 text-muted" />
            <p class="text-muted">No permissions found</p>
          </div>
        </template>
      </UTable>
    </template>
  </UDashboardPanel>
</template>
