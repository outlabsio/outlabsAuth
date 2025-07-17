<template>
  <div class="w-full">
    <!-- Breadcrumb Navigation -->
    <div class="mb-6">
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
    <div v-else-if="entity" class="space-y-6">
      <!-- Header Section -->
      <div class="bg-default border rounded-lg p-6">
        <div class="flex items-start justify-between mb-4">
          <div class="flex items-center gap-4">
            <UIcon :name="entity.entity_class === 'STRUCTURAL' ? 'i-lucide-building' : 'i-lucide-users'" class="h-12 w-12 text-primary" />
            <div>
              <h1 class="text-3xl font-bold">{{ entity.display_name || entity.name }}</h1>
              <div class="flex items-center gap-2 mt-1">
                <UBadge :label="entity.entity_type" variant="subtle" />
                <UBadge :label="entity.entity_class" :color="entity.entity_class === 'STRUCTURAL' ? 'primary' : 'secondary'" variant="outline" size="sm" />
                <UBadge :label="entity.status" :color="entity.status === 'active' ? 'success' : 'neutral'" variant="subtle" size="sm" />
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-2">
            <UButton icon="i-lucide-edit" label="Edit" @click="openEditDrawer" variant="outline" />
            <UButton icon="i-lucide-plus" label="Add Child" @click="openCreateDrawer" v-if="entity.entity_class === 'STRUCTURAL'" />
          </div>
        </div>

        <!-- Description -->
        <p v-if="entity.description" class="text-muted-foreground">
          {{ entity.description }}
        </p>

        <!-- Entity Path -->
        <div v-if="entityPath.length > 1" class="mt-4 p-3 bg-elevated rounded-md">
          <p class="text-sm font-medium mb-2">Entity Path:</p>
          <UBreadcrumb :items="entityPath" />
        </div>
      </div>

      <!-- Tabs Section -->
      <UTabs v-model="activeTab" :items="tabItems" class="w-full">
        <!-- Overview Tab -->
        <template #overview>
          <div class="space-y-6">
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
          <div class="space-y-4">
            <div class="flex justify-between items-center">
              <h3 class="text-lg font-semibold">Child Entities</h3>
              <UButton icon="i-lucide-plus" label="Add Child Entity" @click="openCreateDrawer" v-if="entity.entity_class === 'STRUCTURAL'" />
            </div>

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
              <p class="text-muted-foreground mb-4">This entity doesn't have any child entities yet.</p>
              <UButton icon="i-lucide-plus" label="Add First Child" @click="openCreateDrawer" v-if="entity.entity_class === 'STRUCTURAL'" />
            </div>
          </div>
        </template>

        <!-- Members Tab -->
        <template #members>
          <div class="space-y-4">
            <div class="flex justify-between items-center">
              <h3 class="text-lg font-semibold">Members</h3>
              <UButton icon="i-lucide-user-plus" label="Add Member" @click="openMemberManagement" />
            </div>

            <!-- Member management would go here -->
            <div class="text-center py-12">
              <UIcon name="i-lucide-users" class="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <h3 class="font-medium mb-1">Member management</h3>
              <p class="text-muted-foreground">Member management functionality coming soon.</p>
            </div>
          </div>
        </template>

        <!-- Activity Tab -->
        <template #activity>
          <div class="space-y-4">
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
const entitiesStore = useEntitiesStore();

// State
const activeTab = ref(0); // Use index for tab selection
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

// Build entity path for breadcrumbs
const entityPath = computed(() => {
  if (!entity.value) return [];

  const path: { label: string; to: string }[] = [];

  // Add current entity
  path.push({
    label: entity.value.display_name || entity.value.name,
    to: `/entities/${entity.value.id}`,
  });

  // Note: For now, we only show the current entity in the path
  // A full parent chain would require recursive fetching or a different API endpoint
  
  return path;
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
  },
  {
    slot: "children",
    label: `Children (${childEntities.value.length})`,
    icon: "i-lucide-folder",
  },
  {
    slot: "members",
    label: "Members",
    icon: "i-lucide-users",
  },
  {
    slot: "activity",
    label: "Activity",
    icon: "i-lucide-activity",
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

function openMemberManagement() {
  // Placeholder for member management
  console.log("Member management coming soon");
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
