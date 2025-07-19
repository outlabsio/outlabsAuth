<script setup lang="ts">
const debugStore = useDebugStore();
const contextStore = useContextStore();
const authStore = useAuthStore();
const permissionsStore = usePermissionsStore();
const rolesStore = useRolesStore();
const entitiesStore = useEntitiesStore();
const userStore = useUserStore();
const config = useRuntimeConfig();

// Panel position and size
const panelPosition = ref({ x: 20, y: 80 });
const isCollapsed = ref(false);
const isDragging = ref(false);
const dragOffset = ref({ x: 0, y: 0 });

// Selected tab state
const selectedTab = ref('context');

// Tabs configuration for Nuxt UI v3
const tabItems = computed(() => [
  { label: 'Context', value: 'context', slot: 'context', icon: 'i-lucide-globe' },
  { label: 'Stores', value: 'stores', slot: 'stores', icon: 'i-lucide-database' },
  { label: 'Permissions', value: 'permissions', slot: 'permissions', icon: 'i-lucide-key' },
  { label: 'API', value: 'api', slot: 'api', icon: 'i-lucide-activity' }
]);

// Context info
const contextInfo = computed(() => ({
  isSystemContext: contextStore.isSystemContext,
  selectedOrganization: contextStore.selectedOrganization,
  availableOrganizations: contextStore.availableOrganizations,
  contextHeaders: contextStore.getContextHeaders,
  currentUser: userStore.user
}));

// Store states for debugging
const authStoreState = computed(() => ({
  isAuthenticated: authStore.isAuthenticated,
  accessToken: authStore.accessToken ? 'Present' : 'None',
  refreshToken: authStore.refreshToken ? 'Present' : 'None'
}));

const userStoreState = computed(() => ({
  id: userStore.id,
  email: userStore.email,
  isAdmin: userStore.isAdmin,
  isPlatformAdmin: userStore.isPlatformAdmin,
  isSystemUser: userStore.isSystemUser
}));

// Store states
const storeStates = computed(() => ({
  auth: authStoreState.value,
  user: userStoreState.value,
  permissions: {
    total: permissionsStore.permissions.length,
    filtered: permissionsStore.filteredPermissions.length,
    displayCounts: permissionsStore.displayCounts,
    filters: permissionsStore.filters,
    currentContext: permissionsStore.currentContext
  },
  roles: {
    total: rolesStore.roles?.length || 0,
    filtered: rolesStore.filteredRoles?.length || 0
  },
  entities: {
    total: entitiesStore.entities?.length || 0,
    currentPath: entitiesStore.currentPath
  }
}));

// Permission details
const permissionDetails = computed(() => {
  const filtered = permissionsStore.contextFilteredPermissions;
  return {
    total: filtered.length,
    system: filtered.filter(p => p.is_system).length,
    custom: filtered.filter(p => !p.is_system).length,
    byEntity: filtered.reduce((acc, p) => {
      if (!p.is_system && p.entity_id) {
        acc[p.entity_id] = (acc[p.entity_id] || 0) + 1;
      }
      return acc;
    }, {} as Record<string, number>)
  };
});

// Handle dragging
const startDrag = (e: MouseEvent) => {
  isDragging.value = true;
  dragOffset.value = {
    x: e.clientX - panelPosition.value.x,
    y: e.clientY - panelPosition.value.y
  };
};

const onDrag = (e: MouseEvent) => {
  if (isDragging.value) {
    panelPosition.value = {
      x: e.clientX - dragOffset.value.x,
      y: e.clientY - dragOffset.value.y
    };
  }
};

const stopDrag = () => {
  isDragging.value = false;
};

// Add event listeners
onMounted(() => {
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag);
});

onUnmounted(() => {
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
});

// Copy to clipboard
const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text);
  const toast = useToast();
  toast.add({
    title: 'Copied to clipboard',
    color: 'success',
    icon: 'i-lucide-clipboard-check'
  });
};

// Format JSON
const formatJson = (obj: any) => JSON.stringify(obj, null, 2);
</script>

<template>
  <Teleport to="body">
    <div
      v-if="debugStore.enabled && debugStore.panelOpen"
      class="fixed z-50 bg-background/95 backdrop-blur-sm rounded-lg shadow-2xl"
      :style="{
        left: `${panelPosition.x}px`,
        top: `${panelPosition.y}px`,
        width: isCollapsed ? '48px' : '480px',
        maxHeight: '80vh'
      }"
    >
      <!-- Header -->
      <div 
        class="flex items-center justify-between p-3 cursor-move bg-muted/20 border-b border-muted/20"
        @mousedown="startDrag"
      >
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-bug" class="text-primary" />
          <span v-if="!isCollapsed" class="font-semibold">Debug Panel</span>
        </div>
        <div class="flex items-center gap-1">
          <UButton
            v-if="!isCollapsed"
            icon="i-lucide-minimize-2"
            variant="ghost"
            size="xs"
            @click.stop="isCollapsed = true"
          />
          <UButton
            v-else
            icon="i-lucide-maximize-2"
            variant="ghost"
            size="xs"
            @click.stop="isCollapsed = false"
          />
          <UButton
            icon="i-lucide-x"
            variant="ghost"
            size="xs"
            @click.stop="debugStore.togglePanel()"
          />
        </div>
      </div>

      <!-- Content -->
      <div v-if="!isCollapsed" class="overflow-hidden">
        <UTabs 
          v-model="selectedTab"
          :items="tabItems"
          class="w-full"
          :ui="{
            wrapper: 'flex flex-col',
            list: { 
              background: 'bg-transparent', 
              padding: 'px-4 pt-2',
              height: 'h-auto'
            },
            panel: {
              background: 'bg-transparent',
              padding: '',
              height: '',
              class: ''
            }
          }"
        >
          <!-- Context Tab -->
          <template #context>
            <div class="p-4 space-y-4 max-h-[50vh] overflow-y-auto">
              <div>
                <h3 class="text-sm font-semibold mb-2 flex items-center gap-2">
                  <UIcon name="i-lucide-layers" />
                  Current Context
                </h3>
                <UCard :ui="{ body: { padding: 'p-3' } }" class="text-sm space-y-2">
                  <div>
                    <span class="text-muted">Type:</span>
                    <UBadge :color="contextInfo.isSystemContext ? 'primary' : 'success'" variant="subtle" class="ml-2">
                      {{ contextInfo.isSystemContext ? 'System' : 'Organization' }}
                    </UBadge>
                  </div>
                  <div v-if="contextInfo.selectedOrganization">
                    <span class="text-muted">Organization:</span>
                    <span class="ml-2 font-mono">{{ contextInfo.selectedOrganization.name }}</span>
                  </div>
                  <div v-if="contextInfo.selectedOrganization?.id">
                    <span class="text-muted">ID:</span>
                    <code class="ml-2 text-xs bg-muted/30 px-1.5 py-0.5 rounded cursor-pointer" @click="copyToClipboard(contextInfo.selectedOrganization.id)">
                      {{ contextInfo.selectedOrganization.id }}
                    </code>
                  </div>
                  <div v-if="contextInfo.selectedOrganization?.entity_type">
                    <span class="text-muted">Entity Type:</span>
                    <span class="ml-2">{{ contextInfo.selectedOrganization.entity_type }}</span>
                  </div>
                </UCard>
              </div>

              <div>
                <h3 class="text-sm font-semibold mb-2 flex items-center gap-2">
                  <UIcon name="i-lucide-user" />
                  Current User
                </h3>
                <UCard :ui="{ body: { padding: 'p-3' } }" class="text-sm space-y-2">
                  <div>
                    <span class="text-muted">Email:</span>
                    <span class="ml-2">{{ contextInfo.currentUser?.email }}</span>
                  </div>
                  <div>
                    <span class="text-muted">ID:</span>
                    <code class="ml-2 text-xs bg-muted/30 px-1.5 py-0.5 rounded cursor-pointer" @click="copyToClipboard(contextInfo.currentUser?.id || '')">
                      {{ contextInfo.currentUser?.id }}
                    </code>
                  </div>
                  <div>
                    <span class="text-muted">Superuser:</span>
                    <UBadge :color="contextInfo.currentUser?.is_superuser ? 'success' : 'neutral'" variant="subtle" class="ml-2">
                      {{ contextInfo.currentUser?.is_superuser ? 'Yes' : 'No' }}
                    </UBadge>
                  </div>
                </UCard>
              </div>

              <div>
                <h3 class="text-sm font-semibold mb-2 flex items-center gap-2">
                  <UIcon name="i-lucide-send" />
                  API Headers
                </h3>
                <UCard :ui="{ body: { padding: 'p-3' } }" class="text-sm">
                  <pre class="text-xs overflow-x-auto">{{ formatJson(contextInfo.contextHeaders) }}</pre>
                </UCard>
              </div>
            </div>
          </template>

          <!-- Stores Tab -->
          <template #stores>
            <div class="p-4 space-y-4 max-h-[50vh] overflow-y-auto">
              <div v-for="(storeData, storeName) in storeStates" :key="storeName">
                <h3 class="text-sm font-semibold mb-2 capitalize">{{ storeName }} Store</h3>
                <UCard :ui="{ body: { padding: 'p-3' } }">
                  <pre class="text-xs overflow-x-auto">{{ formatJson(storeData) }}</pre>
                </UCard>
              </div>
            </div>
          </template>

          <!-- Permissions Tab -->
          <template #permissions>
            <div class="p-4 space-y-4 max-h-[50vh] overflow-y-auto">
              <div>
                <h3 class="text-sm font-semibold mb-2">Permission Summary</h3>
                <UCard :ui="{ body: { padding: 'p-3' } }" class="text-sm space-y-2">
                  <div>
                    <span class="text-muted">Total:</span>
                    <span class="ml-2 font-mono">{{ permissionDetails.total }}</span>
                  </div>
                  <div>
                    <span class="text-muted">System:</span>
                    <span class="ml-2 font-mono">{{ permissionDetails.system }}</span>
                  </div>
                  <div>
                    <span class="text-muted">Custom:</span>
                    <span class="ml-2 font-mono">{{ permissionDetails.custom }}</span>
                  </div>
                </UCard>
              </div>

              <div>
                <h3 class="text-sm font-semibold mb-2">Permissions by Entity</h3>
                <UCard :ui="{ body: { padding: 'p-3' } }">
                  <div v-for="(count, entityId) in permissionDetails.byEntity" :key="entityId" class="text-sm">
                    <code class="text-xs">{{ entityId }}</code>: {{ count }} permissions
                  </div>
                  <div v-if="Object.keys(permissionDetails.byEntity).length === 0" class="text-sm text-muted">
                    No custom permissions in current context
                  </div>
                </UCard>
              </div>

              <div>
                <h3 class="text-sm font-semibold mb-2">Current Filters</h3>
                <UCard :ui="{ body: { padding: 'p-3' } }">
                  <pre class="text-xs overflow-x-auto">{{ formatJson(permissionsStore.filters) }}</pre>
                </UCard>
              </div>
            </div>
          </template>

          <!-- API Tab -->
          <template #api>
            <div class="p-4 space-y-4 max-h-[50vh] overflow-y-auto">
              <div>
                <h3 class="text-sm font-semibold mb-2">API Configuration</h3>
                <UCard :ui="{ body: { padding: 'p-3' } }" class="text-sm space-y-2">
                  <div>
                    <span class="text-muted">Base URL:</span>
                    <span class="ml-2 font-mono">{{ config.public.apiBaseUrl || 'http://localhost:8030' }}</span>
                  </div>
                  <div>
                    <span class="text-muted">Auth Status:</span>
                    <UBadge :color="authStore.isAuthenticated ? 'success' : 'error'" variant="subtle" class="ml-2">
                      {{ authStore.isAuthenticated ? 'Authenticated' : 'Not Authenticated' }}
                    </UBadge>
                  </div>
                  <div v-if="authStore.accessToken">
                    <span class="text-muted">Has Access Token:</span>
                    <UBadge color="success" variant="subtle" class="ml-2">Yes</UBadge>
                  </div>
                </UCard>
              </div>

              <div>
                <h3 class="text-sm font-semibold mb-2">Recent API Calls</h3>
                <UCard :ui="{ body: { padding: 'p-3' } }" class="text-sm text-muted">
                  <p>API call logging coming soon...</p>
                </UCard>
              </div>
            </div>
          </template>
        </UTabs>
      </div>
    </div>
  </Teleport>

  <!-- Floating Debug Button -->
  <Teleport to="body">
    <UButton
      v-if="debugStore.enabled && !debugStore.panelOpen"
      icon="i-lucide-bug"
      color="primary"
      variant="solid"
      size="lg"
      class="fixed bottom-4 right-4 z-50 shadow-lg"
      @click="debugStore.togglePanel()"
    />
  </Teleport>
</template>

<style scoped>
/* Ensure smooth dragging */
.cursor-move {
  user-select: none;
  -webkit-user-select: none;
}
</style>