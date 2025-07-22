<template>
  <div class="w-full">
    <!-- Breadcrumb Navigation -->
    <div class="m-4">
      <UBreadcrumb :items="breadcrumbItems" />
    </div>

    <!-- Loading State -->
    <div v-if="pending" class="flex justify-center py-12">
      <div class="text-center space-y-3">
        <UIcon name="i-lucide-loader" class="h-8 w-8 animate-spin mx-auto text-primary" />
        <p class="text-muted-foreground">Loading entity details...</p>
      </div>
    </div>

    <!-- Error State -->
    <UAlert v-else-if="error" color="error" variant="subtle" icon="i-lucide-alert-circle" :title="error.statusMessage || 'Failed to load entity'" class="mb-6" />

    <!-- Entity Details -->
    <div v-else-if="entity" class="space-y-0">
      <!-- Compact Header Section -->
      <div class="bg-primary-100 dark:bg-primary-500/10 p-4">
        <div class="flex items-center justify-between gap-4">
          <!-- Left side - Entity info -->
          <div class="flex items-center gap-3 min-w-0">
            <div class="flex-shrink-0">
              <div class="p-2 bg-primary/10 rounded-md">
                <UIcon
                  :name="entity.entity_class === 'STRUCTURAL' ? 'i-lucide-building' : 'i-lucide-users'"
                  class="h-5 w-5 text-primary"
                />
              </div>
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <h1 class="text-lg font-semibold truncate">
                  {{ entity.display_name || entity.name }}
                </h1>
                <UBadge
                  :label="entity.status"
                  :color="entity.status === 'active' ? 'success' : 'neutral'"
                  variant="subtle"
                  size="xs"
                />
              </div>

              <div class="flex items-center gap-2 mt-0.5 text-sm text-muted">
                <span>
                  {{ entity.entity_type.charAt(0).toUpperCase() + entity.entity_type.slice(1).replace(/_/g, " ") }}
                </span>
                <span>•</span>
                <span>
                  {{ entity.entity_class === 'STRUCTURAL' ? 'Structural' : 'Access Group' }}
                </span>
                <span v-if="entity.description" class="hidden sm:inline">•</span>
                <span v-if="entity.description" class="hidden sm:inline truncate max-w-xs">
                  {{ entity.description }}
                </span>
              </div>
            </div>
          </div>

          <!-- Right side - Actions -->
          <div class="flex items-center gap-2 flex-shrink-0">
            <UButton
              icon="i-lucide-pencil"
              variant="subtle"
              size="sm"
              class="hidden sm:flex"
              @click="openEditDrawer"
            >
              Modify
            </UButton>
            <UButton
              icon="i-lucide-pencil"
              variant="subtle"
              size="sm"
              class="sm:hidden"
              square
              @click="openEditDrawer"
            />
            <UButton
              v-if="entity.entity_class === 'STRUCTURAL'"
              icon="i-lucide-plus"
              size="sm"
              @click="openCreateDrawer"
            >
              <span class="hidden sm:inline">Add Child</span>
            </UButton>
          </div>
        </div>
      </div>

      <!-- Tabs Section -->
      <UTabs 
        v-model="activeTab" 
        :items="tabItems" 
        class="w-full"
        :ui="{
          list: 'rounded-none bg-neutral-500/10'
        }"
      >
        <!-- Overview Tab -->
        <template #overview>
          <div class="space-y-4 p-4">
            <!-- Entity Information -->
            <UCard>
              <template #header>
                <h3 class="text-lg font-semibold">Entity Information</h3>
              </template>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">System Name</h4>
                  <p class="mt-1 font-mono text-sm bg-elevated px-2 py-1 rounded">{{ entity.name }}</p>
                </div>

                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">Entity Type</h4>
                  <p class="mt-1">{{ entity.entity_type }}</p>
                </div>

                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">Entity Class</h4>
                  <p class="mt-1">{{ entity.entity_class }}</p>
                </div>

                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">Status</h4>
                  <UBadge :label="entity.status" :color="entity.status === 'active' ? 'success' : 'neutral'" variant="subtle" />
                </div>

                <div v-if="entity.max_members">
                  <h4 class="text-sm font-medium text-muted-foreground">Maximum Members</h4>
                  <p class="mt-1">{{ entity.max_members }}</p>
                </div>

                <div>
                  <h4 class="text-sm font-medium text-muted-foreground">Created</h4>
                  <p class="mt-1">{{ formatDate(entity.created_at) }}</p>
                </div>

                <div v-if="entity.updated_at">
                  <h4 class="text-sm font-medium text-muted-foreground">Last Updated</h4>
                  <p class="mt-1">{{ formatDate(entity.updated_at) }}</p>
                </div>

                <div v-if="parentEntity">
                  <h4 class="text-sm font-medium text-muted-foreground">Parent Entity</h4>
                  <NuxtLink :to="`/entities/${parentEntity.id}`" class="mt-1 flex items-center gap-2 text-primary hover:underline">
                    <UIcon name="i-lucide-building" class="h-4 w-4" />
                    {{ parentEntity.display_name || parentEntity.name }}
                  </NuxtLink>
                </div>
              </div>
            </UCard>

            <!-- Statistics -->
            <UCard v-if="entityStats">
              <template #header>
                <h3 class="text-lg font-semibold">Statistics</h3>
              </template>

              <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="text-center">
                  <div class="text-2xl font-bold text-primary">{{ entityStats.child_count || 0 }}</div>
                  <div class="text-sm text-muted-foreground">Child Entities</div>
                </div>

                <div class="text-center">
                  <div class="text-2xl font-bold text-success">{{ entityStats.member_count || 0 }}</div>
                  <div class="text-sm text-muted-foreground">Direct Members</div>
                </div>

                <div class="text-center">
                  <div class="text-2xl font-bold text-info">{{ entityStats.permission_count || 0 }}</div>
                  <div class="text-sm text-muted-foreground">Permissions</div>
                </div>
              </div>
            </UCard>
          </div>
        </template>

        <!-- Children Tab -->
        <template #children>
          <div class="space-y-4 p-4">
            <!-- Children List -->
            <div v-if="childEntities && childEntities.length > 0" class="space-y-3">
              <UCard v-for="child in childEntities" :key="child.id" class="hover:shadow-md transition-shadow cursor-pointer" @click="navigateToEntity(child.id)">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-3">
                    <UIcon :name="child.entity_class === 'STRUCTURAL' ? 'i-lucide-building' : 'i-lucide-users'" class="h-5 w-5" />
                    <div>
                      <h4 class="font-medium">{{ child.display_name || child.name }}</h4>
                      <p class="text-sm text-muted-foreground">{{ child.entity_type }}</p>
                    </div>
                  </div>
                  <div class="flex items-center gap-2">
                    <UBadge :label="child.status" :color="child.status === 'active' ? 'success' : 'neutral'" variant="subtle" size="sm" />
                    <UIcon name="i-lucide-chevron-right" class="h-4 w-4 text-muted-foreground" />
                  </div>
                </div>
              </UCard>
            </div>

            <!-- Empty State -->
            <div v-else class="text-center py-12">
              <UIcon name="i-lucide-folder-open" class="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <h3 class="font-medium mb-1">No child entities</h3>
              <p class="text-muted-foreground">This entity doesn't have any child entities yet.</p>
            </div>
          </div>
        </template>

        <!-- Members Tab -->
        <template #members>
          <div class="p-4">
            <MemberManagement 
              v-if="entity"
              :entity-id="entity.id" 
              :entity-name="entity.display_name || entity.name"
            />
          </div>
        </template>

        <!-- Activity Tab -->
        <template #activity>
          <div class="space-y-4 p-4">
            <h3 class="text-lg font-semibold">Activity Log</h3>

            <div class="text-center py-12">
              <UIcon name="i-lucide-activity" class="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <h3 class="font-medium mb-1">Activity tracking</h3>
              <p class="text-muted-foreground">Activity log functionality coming soon.</p>
            </div>
          </div>
        </template>
      </UTabs>
    </div>

    <!-- Drawers -->
    <EntitiesDrawer
      v-model:open="drawerOpen"
      :entity="drawerEntity"
      :mode="drawerMode"
      :default-parent-id="drawerMode === 'create' ? entity?.id : null"
      @created="handleEntityCreated"
      @updated="handleEntityUpdated"
      @deleted="handleEntityDeleted"
    />
  </div>
</template>

<script setup lang="ts">
import type { Entity } from "~/types/auth.types";

// Route params
const route = useRoute();
const router = useRouter();
const entityId = computed(() => route.params.entityId as string);

// Store
const authStore = useAuthStore();

// State
const activeTab = ref('overview'); // Use slot name for tab selection
const drawerOpen = ref(false);
const drawerMode = ref<"view" | "create" | "edit">("view");
const drawerEntity = ref<Entity | null>(null);

// Fetch entity data
const {
  data: entity,
  pending,
  error,
  refresh,
} = await useAsyncData(
  `entity-${entityId.value}`,
  async () => {
    const contextStore = useContextStore();
    const headers = contextStore.getContextHeaders;
    const response = await authStore.apiCall<Entity>(`/v1/entities/${entityId.value}`, { headers });
    return response;
  },
  {
    key: `entity-${entityId.value}`,
    lazy: false,
  }
);

// State for child entities
const childEntities = ref<Entity[]>([]);

// Fetch child entities
const fetchChildEntities = async () => {
  try {
    const contextStore = useContextStore();
    const headers = contextStore.getContextHeaders;
    const response = await authStore.apiCall<{ items: Entity[] }>(`/v1/entities?parent_entity_id=${entityId.value}&page_size=50`, { headers });
    childEntities.value = response.items || [];
  } catch (error) {
    console.error('Failed to fetch child entities:', error);
    childEntities.value = [];
  }
};

// Fetch children when entity is loaded
watchEffect(() => {
  if (entity.value) {
    fetchChildEntities();
  }
});

// Watch for route changes and refresh data
watch(entityId, async (newId, oldId) => {
  if (newId !== oldId) {
    await refresh();
    await fetchChildEntities();
    await fetchEntityPath();
  }
});

// State for parent entity
const parentEntity = ref<Entity | null>(null);

// Fetch parent entity when entity changes
watchEffect(async () => {
  if (entity.value && entity.value.parent_entity_id) {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      const response = await authStore.apiCall<Entity>(`/v1/entities/${entity.value.parent_entity_id}`, { headers });
      parentEntity.value = response;
    } catch (error) {
      console.error('Failed to fetch parent entity:', error);
      parentEntity.value = null;
    }
  } else {
    parentEntity.value = null;
  }
});

// Fetch entity statistics
const { data: entityStats } = await useAsyncData(
  `entity-stats-${entityId.value}`,
  async () => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      const response = await authStore.apiCall<any>(`/v1/entities/${entityId.value}/stats`, { headers });
      return response;
    } catch (error) {
      return null;
    }
  },
  {
    lazy: true,
    default: () => null,
  }
);

// State for entity path
const entityPath = ref<{ label: string; to: string }[]>([]);

// Fetch full entity path using the dedicated API endpoint
const fetchEntityPath = async () => {
  if (!entity.value) {
    entityPath.value = [];
    return;
  }

  try {
    const contextStore = useContextStore();
    const headers = contextStore.getContextHeaders;
    const pathResponse = await authStore.apiCall<Entity[]>(
      `/v1/entities/${entityId.value}/path`, 
      { headers }
    );
    
    // Convert the response to breadcrumb format
    entityPath.value = pathResponse.map(entity => ({
      label: entity.display_name || entity.name,
      to: `/entities/${entity.id}`,
    }));
  } catch (error) {
    console.error('Failed to fetch entity path:', error);
    // Fallback to just the current entity
    entityPath.value = [{
      label: entity.value.display_name || entity.value.name,
      to: `/entities/${entity.value.id}`,
    }];
  }
};

// Watch for entity changes and fetch path
watchEffect(() => {
  if (entity.value) {
    fetchEntityPath();
  }
});

// Build breadcrumb items
const breadcrumbItems = computed(() => {
  const items = [{ label: "Entities", to: "/entities" }];

  if (entityPath.value.length > 0) {
    items.push(...entityPath.value);
  }

  return items;
});

// Tab configuration
const tabItems = computed(() => [
  {
    slot: "overview",
    label: "Overview",
    icon: "i-lucide-info",
    value: "overview",
  },
  {
    slot: "children",
    label: `Children (${childEntities.value.length})`,
    icon: "i-lucide-folder",
    value: "children",
  },
  {
    slot: "members",
    label: "Members",
    icon: "i-lucide-users",
    value: "members",
  },
  {
    slot: "activity",
    label: "Activity",
    icon: "i-lucide-activity",
    value: "activity",
  },
]);

// Methods
function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function openEditDrawer() {
  drawerEntity.value = entity.value;
  drawerMode.value = "edit";
  drawerOpen.value = true;
}

function openCreateDrawer() {
  drawerEntity.value = null;
  drawerMode.value = "create";
  drawerOpen.value = true;
}


function navigateToEntity(entityId: string) {
  router.push(`/entities/${entityId}`);
}

async function handleEntityCreated(newEntity: Entity) {
  // Refresh child entities
  await fetchChildEntities();
}

function handleEntityUpdated(updatedEntity: Entity) {
  // Refresh current entity
  refresh();
}

function handleEntityDeleted() {
  // Navigate back to entities list or parent
  if (entity.value?.parent_entity_id) {
    router.push(`/entities/${entity.value.parent_entity_id}`);
  } else {
    router.push("/entities");
  }
}

// SEO
useHead({
  title: computed(() => (entity.value ? `${entity.value.display_name || entity.value.name} - Entities` : "Entity Details")),
  meta: [
    {
      name: "description",
      content: computed(() => entity.value?.description || `Details for ${entity.value?.display_name || entity.value?.name}`),
    },
  ],
});
</script>
