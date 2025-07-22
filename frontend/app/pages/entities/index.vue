<script setup lang="ts">
import type { Entity } from '~/types/auth.types';

// Store
const entitiesStore = useEntitiesStore();
const contextStore = useContextStore()

// State
const selectedEntity = ref<Entity | null>(null);
const drawerOpen = ref(false);
const drawerMode = ref<"view" | "create" | "edit">("view");

// Entity class options
const entityClassOptions = [
  { label: "All", value: "" },
  { label: "Structural", value: "STRUCTURAL" },
  { label: "Access Group", value: "ACCESS_GROUP" },
];

// Entity level options - dynamic based on context
const entityLevelOptions = computed(() => {
  if (contextStore.isSystemContext) {
    return [
      { label: "Top-level only", value: "top", icon: "i-lucide-home" },
      { label: "All entities", value: "all", icon: "i-lucide-layers" },
    ];
  } else if (contextStore.selectedOrganization) {
    return [
      { label: `Direct children of ${contextStore.selectedOrganization.name}`, value: "top", icon: "i-lucide-home" },
      { label: `All in ${contextStore.selectedOrganization.name}`, value: "all", icon: "i-lucide-layers" },
    ];
  }
  return [
    { label: "All entities", value: "all", icon: "i-lucide-layers" },
  ];
});

// Computed property for current hierarchy level
const hierarchyLevel = computed({
  get: () => {
    const includeChildren = entitiesStore.filters.include_children;
    // If include_children is true, we're showing "all"
    return includeChildren ? "all" : "top";
  },
  set: (value) => entitiesStore.setHierarchyLevel(value as "top" | "all")
});

// Fetch entities on mount with context-aware default
onMounted(() => {
  // Set initial hierarchy level based on context
  if (contextStore.isSystemContext) {
    entitiesStore.setHierarchyLevel("top"); // Show top-level entities
  } else if (contextStore.selectedOrganization) {
    entitiesStore.setHierarchyLevel("top"); // Show direct children of the org
  }
});

// Get entity types for filter
const { data: entityTypes } = await useAsyncData("entity-types", () => entitiesStore.fetchEntityTypes());

// Context-aware breadcrumb items
const breadcrumbItems = computed(() => {
  const items = [{ label: "Dashboard", to: "/dashboard" }];

  if (contextStore.isSystemContext) {
    items.push({ label: "All Entities", to: "/entities" });
  } else if (contextStore.selectedOrganization) {
    items.push({ label: "Entities", to: "/entities" }, { label: contextStore.selectedOrganization.name, to: "/entities" });
  } else {
    items.push({ label: "Entities", to: "/entities" });
  }

  return items;
});
const entityTypeOptions = computed(() => {
  const options = [{ label: "All Types", value: "" }];
  if (entityTypes.value && Array.isArray(entityTypes.value)) {
    entityTypes.value.forEach((type) => {
      options.push({
        label: type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, " "),
        value: type,
      });
    });
  }
  return options;
});

// Methods
function handleSearch(searchValue: string | number) {
  const search = String(searchValue);
  // When searching, automatically switch to "all entities" view
  if (search && hierarchyLevel.value === "top") {
    entitiesStore.setHierarchyLevel("all");
  }
  entitiesStore.setFilters({ search });
}

function openCreateDrawer() {
  selectedEntity.value = null;
  drawerMode.value = "create";
  drawerOpen.value = true;
}


function handleEntityCreated() {
  entitiesStore.fetchEntities();
}

function handleEntityUpdated() {
  entitiesStore.fetchEntities();
}

function handleEntityDeleted() {
  entitiesStore.fetchEntities();
}
</script>

<template>
  <UDashboardPanel>
    <UDashboardNavbar>
      <template #left>
        <div class="flex items-center gap-4">
          <UDashboardSidebarCollapse />
          <UBreadcrumb :items="breadcrumbItems" />
        </div>
      </template>
      <template #right>
        <UButton icon="i-lucide-plus" @click="openCreateDrawer"> Create Entity </UButton>
      </template>
    </UDashboardNavbar>

    <div class="px-4 py-6 lg:px-8">
      <!-- Filters -->
      <UCard class="mb-6">
        <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
          <!-- Hierarchy Level Filter -->
          <USelectMenu
            v-model="hierarchyLevel"
            :options="entityLevelOptions"
            placeholder="Hierarchy"
            value-attribute="value"
            option-attribute="label"
          >
            <template #leading>
              <UIcon :name="hierarchyLevel === 'top' ? 'i-lucide-home' : 'i-lucide-layers'" class="w-4 h-4" />
            </template>
          </USelectMenu>

          <!-- Search -->
          <UInput
            :model-value="entitiesStore.filters.search"
            @update:model-value="handleSearch"
            placeholder="Search entities..."
            icon="i-lucide-search"
            size="md"
          />

          <!-- Entity Class Filter -->
          <USelectMenu
            :model-value="entitiesStore.filters.entity_class"
            @update:model-value="entitiesStore.setFilters({ entity_class: String($event) })"
            :options="entityClassOptions"
            placeholder="All Classes"
            value-attribute="value"
            option-attribute="label"
          />

          <!-- Entity Type Filter -->
          <USelectMenu
            :model-value="entitiesStore.filters.entity_type"
            @update:model-value="entitiesStore.setFilters({ entity_type: String($event) })"
            :options="entityTypeOptions"
            placeholder="All Types"
            value-attribute="value"
            option-attribute="label"
          />

          <!-- Reset Button -->
          <UButton 
            @click="entitiesStore.resetFilters" 
            variant="outline" 
            icon="i-lucide-rotate-ccw"
          >
            Reset
          </UButton>
        </div>
      </UCard>

      <!-- Loading State -->
      <div v-if="entitiesStore.isLoading" class="text-center py-12">
        <UIcon name="i-lucide-loader-2" class="h-8 w-8 animate-spin text-primary" />
        <p class="mt-2 text-gray-600">Loading entities...</p>
      </div>

      <!-- Error State -->
      <UAlert v-else-if="entitiesStore.error" color="error" variant="subtle" icon="i-lucide-alert-circle" :title="entitiesStore.error" />

      <!-- Entities Grid -->
      <div v-else-if="entitiesStore.entities.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <NuxtLink v-for="entity in entitiesStore.entities" :key="entity.id" :to="`/entities/${entity.id}`" class="block">
          <UCard class="cursor-pointer hover:shadow-lg transition-shadow h-full">
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <UIcon :name="entity.entity_class === 'STRUCTURAL' ? 'i-lucide-building' : 'i-lucide-users'" class="h-4 w-4 text-primary" />
                  <h3 class="font-semibold">
                    {{ entity.display_name || entity.name }}
                  </h3>
                </div>
                <p class="text-sm text-gray-600 dark:text-gray-400">
                  {{ entity.entity_type.replace(/_/g, " ") }}
                </p>
                <p v-if="entity.description" class="text-sm text-gray-500 mt-1 line-clamp-2">
                  {{ entity.description }}
                </p>
              </div>
              <UBadge :color="entity.status === 'active' ? 'success' : 'neutral'" variant="subtle" size="xs">
                {{ entity.status }}
              </UBadge>
            </div>
          </UCard>
        </NuxtLink>
      </div>

      <!-- Empty State -->
      <UCard v-else class="text-center py-12">
        <UIcon name="i-lucide-building" class="h-12 w-12 text-gray-400 mb-4" />
        <h3 class="text-lg font-semibold mb-2">No entities found</h3>
        <p class="text-gray-600 dark:text-gray-400 mb-4">
          {{ entitiesStore.filters.search || entitiesStore.filters.entity_class || entitiesStore.filters.entity_type ? "Try adjusting your filters" : "Get started by creating your first entity" }}
        </p>
        <UButton v-if="!entitiesStore.filters.search && !entitiesStore.filters.entity_class && !entitiesStore.filters.entity_type" icon="i-lucide-plus" @click="openCreateDrawer">
          Create Entity
        </UButton>
      </UCard>

      <!-- Pagination -->
      <div v-if="entitiesStore.pagination.total > entitiesStore.pagination.pageSize" class="mt-6 flex justify-center">
        <UPagination 
          :page="entitiesStore.pagination.page" 
          :total="entitiesStore.pagination.total" 
          :items-per-page="entitiesStore.pagination.pageSize" 
          @update:page="entitiesStore.setPage" 
        />
      </div>
    </div>

    <!-- Entity Drawer -->
    <EntitiesDrawer v-model:open="drawerOpen" :entity="selectedEntity" :mode="drawerMode" @created="handleEntityCreated" @updated="handleEntityUpdated" @deleted="handleEntityDeleted" />
  </UDashboardPanel>
</template>
