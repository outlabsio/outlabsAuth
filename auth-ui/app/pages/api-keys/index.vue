<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'

const search = ref('')
const statusFilter = ref<'all' | 'active' | 'revoked' | 'expired'>('all')
const showCreateModal = ref(false)

// Mock API keys data
const apiKeys = ref([
  {
    id: '1',
    name: 'Production API',
    prefix: 'olauth_prod',
    key_hash: '***************************abc123',
    scopes: ['user:read', 'user:create', 'role:read'],
    status: 'active',
    created_at: '2025-01-10T10:00:00Z',
    expires_at: '2026-01-10T10:00:00Z',
    last_used_at: '2025-01-15T14:30:00Z',
    created_by: 'admin@outlabs.com'
  },
  {
    id: '2',
    name: 'Development API',
    prefix: 'olauth_dev',
    key_hash: '***************************xyz789',
    scopes: ['*:*'],
    status: 'active',
    created_at: '2025-01-05T09:00:00Z',
    expires_at: null,
    last_used_at: '2025-01-15T16:45:00Z',
    created_by: 'developer@outlabs.com'
  },
  {
    id: '3',
    name: 'Testing API',
    prefix: 'olauth_test',
    key_hash: '***************************def456',
    scopes: ['user:read', 'entity:read'],
    status: 'revoked',
    created_at: '2024-12-01T08:00:00Z',
    expires_at: '2025-12-01T08:00:00Z',
    last_used_at: '2024-12-15T11:20:00Z',
    created_by: 'admin@outlabs.com'
  },
  {
    id: '4',
    name: 'Legacy Integration',
    prefix: 'olauth_legacy',
    key_hash: '***************************ghi789',
    scopes: ['user:read'],
    status: 'expired',
    created_at: '2024-06-01T10:00:00Z',
    expires_at: '2024-12-31T23:59:59Z',
    last_used_at: '2024-12-20T09:15:00Z',
    created_by: 'admin@outlabs.com'
  }
])

// Table columns
const columns: TableColumn<typeof apiKeys.value[0]>[] = [
  {
    accessorKey: 'name',
    header: 'Name',
    cell: ({ row }) => h('div', { class: 'flex flex-col gap-1' }, [
      h('p', { class: 'font-medium' }, row.original.name),
      h('code', { class: 'text-xs text-muted' }, row.original.prefix)
    ])
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => {
      const colors: Record<string, string> = {
        active: 'green',
        revoked: 'red',
        expired: 'neutral'
      }
      return h('UBadge', {
        color: colors[row.original.status] || 'neutral',
        variant: 'subtle'
      }, () => row.original.status.toUpperCase())
    }
  },
  {
    accessorKey: 'scopes',
    header: 'Scopes',
    cell: ({ row }) => {
      const scopes = row.original.scopes
      if (scopes.includes('*:*')) {
        return h('UBadge', { color: 'warning', variant: 'subtle' }, () => 'All Permissions')
      }
      return h('div', { class: 'flex flex-wrap gap-1' },
        scopes.slice(0, 2).map(scope =>
          h('UBadge', { color: 'neutral', variant: 'subtle', size: 'xs' }, () => scope)
        ).concat(
          scopes.length > 2 ? [h('UBadge', { color: 'neutral', variant: 'subtle', size: 'xs' }, () => `+${scopes.length - 2}`)] : []
        )
      )
    }
  },
  {
    accessorKey: 'last_used_at',
    header: 'Last Used',
    cell: ({ row }) => {
      if (!row.original.last_used_at) return h('span', { class: 'text-sm text-muted' }, 'Never')
      const date = new Date(row.original.last_used_at)
      const now = new Date()
      const diffHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60))

      if (diffHours < 1) return h('span', { class: 'text-sm text-green-600' }, 'Just now')
      if (diffHours < 24) return h('span', { class: 'text-sm' }, `${diffHours}h ago`)
      return h('span', { class: 'text-sm text-muted' }, date.toLocaleDateString())
    }
  },
  {
    accessorKey: 'expires_at',
    header: 'Expires',
    cell: ({ row }) => {
      if (!row.original.expires_at) {
        return h('UBadge', { color: 'blue', variant: 'subtle' }, () => 'Never')
      }
      const date = new Date(row.original.expires_at)
      const now = new Date()
      const isExpired = date < now

      if (isExpired) {
        return h('span', { class: 'text-sm text-error' }, 'Expired')
      }
      return h('span', { class: 'text-sm text-muted' }, date.toLocaleDateString())
    }
  },
  {
    id: 'actions',
    header: 'Actions',
    cell: ({ row }) => {
      const isActive = row.original.status === 'active'
      return h('div', { class: 'flex items-center gap-2' }, [
        h(UButton, {
          icon: 'i-lucide-eye',
          color: 'neutral',
          variant: 'ghost',
          size: 'xs',
          onClick: () => console.log('View details:', row.original.id)
        }),
        isActive && h(UButton, {
          icon: 'i-lucide-ban',
          color: 'error',
          variant: 'ghost',
          size: 'xs',
          onClick: () => console.log('Revoke key:', row.original.id)
        })
      ].filter(Boolean))
    }
  }
]

// Filtered API keys
const filteredKeys = computed(() => {
  let result = apiKeys.value

  // Apply status filter
  if (statusFilter.value !== 'all') {
    result = result.filter(key => key.status === statusFilter.value)
  }

  // Apply search filter
  if (search.value) {
    const searchLower = search.value.toLowerCase()
    result = result.filter(key =>
      key.name.toLowerCase().includes(searchLower) ||
      key.prefix.toLowerCase().includes(searchLower) ||
      key.created_by.toLowerCase().includes(searchLower)
    )
  }

  return result
})

// Stats
const stats = computed(() => ({
  total: apiKeys.value.length,
  active: apiKeys.value.filter(k => k.status === 'active').length,
  revoked: apiKeys.value.filter(k => k.status === 'revoked').length,
  expired: apiKeys.value.filter(k => k.status === 'expired').length
}))
</script>

<template>
  <UDashboardPanel id="api-keys">
    <template #header>
      <UDashboardNavbar title="API Keys">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            icon="i-lucide-plus"
            label="Create API Key"
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
            placeholder="Search API keys..."
            class="w-64"
          />

          <UButtonGroup>
            <UButton
              :color="statusFilter === 'all' ? 'primary' : 'neutral'"
              :variant="statusFilter === 'all' ? 'solid' : 'ghost'"
              label="All"
              @click="statusFilter = 'all'"
            />
            <UButton
              :color="statusFilter === 'active' ? 'primary' : 'neutral'"
              :variant="statusFilter === 'active' ? 'solid' : 'ghost'"
              label="Active"
              @click="statusFilter = 'active'"
            />
            <UButton
              :color="statusFilter === 'revoked' ? 'primary' : 'neutral'"
              :variant="statusFilter === 'revoked' ? 'solid' : 'ghost'"
              label="Revoked"
              @click="statusFilter = 'revoked'"
            />
            <UButton
              :color="statusFilter === 'expired' ? 'primary' : 'neutral'"
              :variant="statusFilter === 'expired' ? 'solid' : 'ghost'"
              label="Expired"
              @click="statusFilter = 'expired'"
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
              <p class="text-sm text-muted">Total Keys</p>
              <p class="text-2xl font-bold mt-1">{{ stats.total }}</p>
            </div>
            <UIcon name="i-lucide-key" class="w-8 h-8 text-primary" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Active</p>
              <p class="text-2xl font-bold mt-1 text-green-600">{{ stats.active }}</p>
            </div>
            <UIcon name="i-lucide-check-circle" class="w-8 h-8 text-green-500" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Revoked</p>
              <p class="text-2xl font-bold mt-1 text-red-600">{{ stats.revoked }}</p>
            </div>
            <UIcon name="i-lucide-ban" class="w-8 h-8 text-red-500" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Expired</p>
              <p class="text-2xl font-bold mt-1 text-neutral-600">{{ stats.expired }}</p>
            </div>
            <UIcon name="i-lucide-clock" class="w-8 h-8 text-neutral-500" />
          </div>
        </UCard>
      </div>

      <UTable
        :columns="columns"
        :rows="filteredKeys"
      >
        <template #empty>
          <div class="flex flex-col items-center justify-center py-12 gap-4">
            <UIcon name="i-lucide-key" class="w-12 h-12 text-muted" />
            <p class="text-muted">No API keys found</p>
            <UButton
              icon="i-lucide-plus"
              label="Create your first API key"
              variant="outline"
            />
          </div>
        </template>
      </UTable>
    </template>
  </UDashboardPanel>

  <!-- Create API Key Modal -->
  <ApiKeyCreateModal v-model:open="showCreateModal" />
</template>
