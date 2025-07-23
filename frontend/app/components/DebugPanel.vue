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
const isFullscreen = ref(false);
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

// Dynamic store state extraction
const getStoreState = (store: any) => {
  const state: any = {};
  
  // Get the actual state object
  const storeState = store.$state;
  
  // Also include computed getters
  const descriptors = Object.getOwnPropertyDescriptors(store);
  
  // Add state properties
  for (const [key, value] of Object.entries(storeState)) {
    // Handle sensitive data
    if (key === 'accessToken' || key === 'refreshToken') {
      state[key] = value ? '***PRESENT***' : null;
    } else if (key === 'password' || key === 'secret') {
      state[key] = '***HIDDEN***';
    } else {
      state[key] = value;
    }
  }
  
  // Add getters (computed properties)
  for (const [key, descriptor] of Object.entries(descriptors)) {
    if (descriptor.get && !key.startsWith('$') && !key.startsWith('_')) {
      try {
        const value = store[key];
        // Only add if it's not already in state and is a simple value
        if (!(key in state) && 
            (typeof value === 'string' || 
             typeof value === 'number' || 
             typeof value === 'boolean' || 
             value === null || 
             value === undefined ||
             Array.isArray(value))) {
          state[`[getter] ${key}`] = value;
        }
      } catch (e) {
        // Ignore errors from getters
      }
    }
  }
  
  return state;
};

// Store states - dynamically get all Pinia stores
const storeStates = computed(() => {
  const stores: Record<string, any> = {};
  
  // Get all active Pinia stores
  const pinia = useNuxtApp().$pinia;
  
  // Map of store IDs to friendly names
  const storeNames: Record<string, string> = {
    auth: 'auth',
    user: 'user',
    permissions: 'permissions',
    roles: 'roles',
    entities: 'entities',
    context: 'context',
    ui: 'ui',
    debug: 'debug'
  };
  
  // Get each store's state
  for (const [storeId, storeName] of Object.entries(storeNames)) {
    try {
      const store = pinia._s.get(storeId);
      if (store) {
        stores[storeName] = getStoreState(store);
      }
    } catch (e) {
      console.error(`Failed to get store ${storeId}:`, e);
    }
  }
  
  return stores;
});

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
  if (isFullscreen.value) return; // Prevent dragging in fullscreen
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

// Format JSON with better handling of complex objects
const formatJson = (obj: any) => {
  // Custom replacer to handle special cases
  const replacer = (key: string, value: any) => {
    // Handle functions
    if (typeof value === 'function') {
      return '[Function]';
    }
    // Handle undefined
    if (value === undefined) {
      return '[undefined]';
    }
    // Handle circular references
    if (value instanceof Error) {
      return {
        name: value.name,
        message: value.message,
        stack: value.stack
      };
    }
    return value;
  };
  
  try {
    return JSON.stringify(obj, replacer, 2);
  } catch (error) {
    return `Error formatting: ${error.message}`;
  }
};
</script>

<template>
  <Teleport to="body">
    <div
      v-if="debugStore.enabled && debugStore.panelOpen"
      :class="[
        'fixed z-50 bg-background/95 backdrop-blur-sm shadow-2xl',
        isFullscreen ? 'inset-0' : 'rounded-lg'
      ]"
      :style="isFullscreen ? {} : {
        left: `${panelPosition.x}px`,
        top: `${panelPosition.y}px`,
        width: '480px',
        maxHeight: '80vh'
      }"
    >
      <!-- Header -->
      <div 
        class="flex items-center justify-between p-3 bg-muted/20 border-b border-muted/20"
        :class="{ 'cursor-move': !isFullscreen }"
        @mousedown="!isFullscreen && startDrag($event)"
      >
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-bug" class="text-primary" />
          <span class="font-semibold">Debug Panel</span>
        </div>
        <div class="flex items-center gap-1">
          <UButton
            v-if="!isFullscreen"
            icon="i-lucide-maximize"
            variant="ghost"
            size="xs"
            title="Fullscreen"
            @click.stop="isFullscreen = true"
          />
          <UButton
            v-else
            icon="i-lucide-minimize"
            variant="ghost"
            size="xs"
            title="Exit fullscreen"
            @click.stop="isFullscreen = false"
          />
          <UButton
            icon="i-lucide-x"
            variant="ghost"
            size="xs"
            title="Close"
            @click.stop="debugStore.togglePanel()"
          />
        </div>
      </div>

      <!-- Content -->
      <div class="overflow-hidden" :class="{ 'h-[calc(100vh-60px)]': isFullscreen }">
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
            <div class="p-4 space-y-4 overflow-y-auto" :class="isFullscreen ? 'max-h-[calc(100vh-140px)]' : 'max-h-[50vh]'">
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
            <div class="p-4 space-y-4 overflow-y-auto" :class="isFullscreen ? 'max-h-[calc(100vh-140px)]' : 'max-h-[50vh]'">
              <div class="mb-2 text-xs text-muted">
                <UIcon name="i-lucide-info" class="inline mr-1" />
                Showing actual Pinia store state. Properties marked with [getter] are computed values.
              </div>
              <div v-for="(storeData, storeName) in storeStates" :key="storeName">
                <h3 class="text-sm font-semibold mb-2 capitalize flex items-center gap-2">
                  <UIcon name="i-lucide-database" class="h-4 w-4" />
                  {{ storeName }} Store
                </h3>
                <UCard :ui="{ body: { padding: 'p-3' } }">
                  <div class="relative">
                    <pre class="text-xs overflow-x-auto whitespace-pre-wrap">{{ formatJson(storeData) }}</pre>
                    <UButton
                      icon="i-lucide-copy"
                      variant="ghost"
                      size="xs"
                      class="absolute top-0 right-0"
                      @click="copyToClipboard(JSON.stringify(storeData, null, 2))"
                    />
                  </div>
                </UCard>
              </div>
            </div>
          </template>

          <!-- Permissions Tab -->
          <template #permissions>
            <div class="p-4 space-y-4 overflow-y-auto" :class="isFullscreen ? 'max-h-[calc(100vh-140px)]' : 'max-h-[50vh]'">
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
            <div class="p-4 space-y-4 overflow-y-auto" :class="isFullscreen ? 'max-h-[calc(100vh-140px)]' : 'max-h-[50vh]'">
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