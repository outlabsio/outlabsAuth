<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Entity } from '~/types/entity'

const entitiesStore = useEntitiesStore()
const search = ref('')
const classFilter = ref<'all' | 'STRUCTURAL' | 'ACCESS_GROUP'>('all')

// Fetch entities on mount
onMounted(async () => {
  await entitiesStore.fetchEntities()
})

// Table columns
const columns: TableColumn<Entity>[] = [
  {
    accessorKey: 'name',
    header: 'Entity',
    cell: ({ row }) => {
      const hasParent = !!row.original.parent_id
      return h('div', { class: 'flex items-center gap-2' }, [
        hasParent && h('UIcon', { name: 'i-lucide-corner-down-right', class: 'w-4 h-4 text-muted ml-4' }),
        h('div', { class: 'flex flex-col gap-1' }, [
          h('p', { class: 'font-medium' }, row.original.name),
          h('p', { class: 'text-sm text-muted' }, row.original.entity_type)
        ])
      ])
    }
  },
  {
    accessorKey: 'entity_class',
    header: 'Class',
    cell: ({ row }) => h('UBadge', {
      color: row.original.entity_class === 'STRUCTURAL' ? 'blue' : 'green',
      variant: 'subtle'
    }, () => row.original.entity_class)
  },
  {
    accessorKey: 'parent_id',
    header: 'Parent',
    cell: ({ row }) => {
      if (!row.original.parent_id) {
        return h('UBadge', { color: 'neutral', variant: 'subtle' }, () => 'Root')
      }
      // Find parent entity
      const parent = entitiesStore.entities.find(e => e.id === row.original.parent_id)
      return h('span', { class: 'text-sm' }, parent?.name || row.original.parent_id)
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
    accessorKey: 'created_at',
    header: 'Created',
    cell: ({ row }) => h('span', { class: 'text-sm text-muted' },
      new Date(row.original.created_at).toLocaleDateString()
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
        onClick: () => console.log('Edit entity:', row.original.id)
      }),
      h(UButton, {
        icon: 'i-lucide-trash-2',
        color: 'error',
        variant: 'ghost',
        size: 'xs',
        onClick: () => console.log('Delete entity:', row.original.id)
      })
    ])
  }
]

// Filtered entities based on search and class filter
const filteredEntities = computed(() => {
  let result = entitiesStore.entities

  // Apply class filter
  if (classFilter.value !== 'all') {
    result = result.filter(entity => entity.entity_class === classFilter.value)
  }

  // Apply search filter
  if (search.value) {
    const searchLower = search.value.toLowerCase()
    result = result.filter(entity =>
      entity.name.toLowerCase().includes(searchLower) ||
      entity.entity_type.toLowerCase().includes(searchLower) ||
      entity.description?.toLowerCase().includes(searchLower)
    )
  }

  return result
})

// Stats
const stats = computed(() => ({
  total: entitiesStore.entities.length,
  structural: entitiesStore.structuralEntities.length,
  accessGroup: entitiesStore.accessGroupEntities.length,
  root: entitiesStore.rootEntities.length
}))
</script>

<template>
  <UDashboardPanel id="entities">
    <template #header>
      <UDashboardNavbar title="Entities">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>

        <template #right>
          <UButton
            icon="i-lucide-plus"
            label="Create Entity"
            color="primary"
          />
        </template>
      </UDashboardNavbar>

      <UDashboardToolbar>
        <template #left>
          <UInput
            v-model="search"
            icon="i-lucide-search"
            placeholder="Search entities..."
            class="w-64"
          />

          <UButtonGroup>
            <UButton
              :color="classFilter === 'all' ? 'primary' : 'neutral'"
              :variant="classFilter === 'all' ? 'solid' : 'ghost'"
              label="All"
              @click="classFilter = 'all'"
            />
            <UButton
              :color="classFilter === 'STRUCTURAL' ? 'primary' : 'neutral'"
              :variant="classFilter === 'STRUCTURAL' ? 'solid' : 'ghost'"
              label="Structural"
              @click="classFilter = 'STRUCTURAL'"
            />
            <UButton
              :color="classFilter === 'ACCESS_GROUP' ? 'primary' : 'neutral'"
              :variant="classFilter === 'ACCESS_GROUP' ? 'solid' : 'ghost'"
              label="Access Groups"
              @click="classFilter = 'ACCESS_GROUP'"
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
              <p class="text-sm text-muted">Total Entities</p>
              <p class="text-2xl font-bold mt-1">{{ stats.total }}</p>
            </div>
            <UIcon name="i-lucide-building" class="w-8 h-8 text-primary" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Structural</p>
              <p class="text-2xl font-bold mt-1">{{ stats.structural }}</p>
            </div>
            <UIcon name="i-lucide-sitemap" class="w-8 h-8 text-blue-500" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Access Groups</p>
              <p class="text-2xl font-bold mt-1">{{ stats.accessGroup }}</p>
            </div>
            <UIcon name="i-lucide-users" class="w-8 h-8 text-green-500" />
          </div>
        </UCard>

        <UCard>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm text-muted">Root Entities</p>
              <p class="text-2xl font-bold mt-1">{{ stats.root }}</p>
            </div>
            <UIcon name="i-lucide-git-branch" class="w-8 h-8 text-purple-500" />
          </div>
        </UCard>
      </div>

      <UCard v-if="entitiesStore.isLoading">
        <div class="flex items-center justify-center py-12">
          <UIcon name="i-lucide-loader-2" class="w-8 h-8 animate-spin text-primary" />
        </div>
      </UCard>

      <UCard v-else-if="entitiesStore.error">
        <div class="flex flex-col items-center justify-center py-12 gap-4">
          <UIcon name="i-lucide-alert-circle" class="w-12 h-12 text-error" />
          <p class="text-error">{{ entitiesStore.error }}</p>
          <UButton
            icon="i-lucide-refresh-cw"
            label="Retry"
            @click="entitiesStore.fetchEntities()"
          />
        </div>
      </UCard>

      <UTable
        v-else
        :columns="columns"
        :rows="filteredEntities"
      >
        <template #empty>
          <div class="flex flex-col items-center justify-center py-12 gap-4">
            <UIcon name="i-lucide-building" class="w-12 h-12 text-muted" />
            <p class="text-muted">No entities found</p>
            <UButton
              icon="i-lucide-plus"
              label="Create your first entity"
              variant="outline"
            />
          </div>
        </template>
      </UTable>

      <UDashboardPagination
        v-if="entitiesStore.pagination.pages > 1"
        v-model="entitiesStore.pagination.page"
        :total="entitiesStore.pagination.total"
        :page-size="entitiesStore.pagination.limit"
      />
    </template>
  </UDashboardPanel>
</template>
