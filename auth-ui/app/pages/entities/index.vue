<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Entity } from '~/types/entity'

const entitiesStore = useEntitiesStore()
const search = ref('')
const showCreateModal = ref(false)

// Fetch entities on mount
onMounted(async () => {
  await entitiesStore.fetchEntities()
})

// Table columns
const columns: TableColumn<Entity>[] = [
  {
    accessorKey: 'name',
    header: 'Entity',
    cell: ({ row }) => h('div', { class: 'flex flex-col gap-1' }, [
      h('p', { class: 'font-medium' }, row.original.name),
      h('p', { class: 'text-sm text-muted' }, row.original.entity_type)
    ])
  },
  {
    accessorKey: 'entity_class',
    header: 'Class',
    cell: ({ row }) => h('span', { class: 'text-sm' }, row.original.entity_class)
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

// Filtered entities based on search
const filteredEntities = computed(() => {
  if (!search.value) return entitiesStore.entities

  const searchLower = search.value.toLowerCase()
  return entitiesStore.entities.filter(entity =>
    entity.name.toLowerCase().includes(searchLower) ||
    entity.entity_type.toLowerCase().includes(searchLower) ||
    entity.description?.toLowerCase().includes(searchLower)
  )
})
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
            @click="showCreateModal = true"
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
              @click="showCreateModal = true"
            />
          </div>
        </template>
      </UTable>

      <UPagination
        v-if="entitiesStore.pagination.pages > 1"
        v-model:page="entitiesStore.pagination.page"
        :total="entitiesStore.pagination.total"
        :page-size="entitiesStore.pagination.limit"
      />
    </template>
  </UDashboardPanel>

  <!-- Create Entity Modal -->
  <EntityCreateModal v-model:open="showCreateModal" />
</template>
