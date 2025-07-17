import type { Permission, Condition } from "~/types/auth.types";

interface PermissionListResponse {
  permissions: Permission[];
  total: number;
  system_count: number;
  custom_count: number;
}

interface PermissionsState {
  permissions: Permission[];
  selectedPermission: Permission | null;
  isLoading: boolean;
  error: string | null;
  // Counters
  totalPermissions: number;
  systemCount: number;
  customCount: number;
  // Filters
  filters: {
    search: string;
    resource: string | null;
    is_system: boolean | null;
    is_active: boolean | null;
    has_conditions: boolean | null;
    tags: string[];
  };
  // UI State
  ui: {
    drawerOpen: boolean;
    drawerMode: "view" | "create" | "edit";
  };
}

export const usePermissionsStore = defineStore("permissions", () => {
  // State
  const state = reactive<PermissionsState>({
    permissions: [],
    selectedPermission: null,
    isLoading: false,
    error: null,
    totalPermissions: 0,
    systemCount: 0,
    customCount: 0,
    filters: {
      search: "",
      resource: null,
      is_system: null,
      is_active: null,
      has_conditions: null,
      tags: [],
    },
    ui: {
      drawerOpen: false,
      drawerMode: "view",
    },
  });

  // Use auth and context stores
  const authStore = useAuthStore();
  const contextStore = useContextStore();

  // Actions
  const fetchPermissions = async () => {
    state.isLoading = true;
    state.error = null;

    try {
      // Get context headers
      const headers = contextStore.getContextHeaders;

      // Build query params
      const params = new URLSearchParams();
      
      // Add entity context if not in system context
      if (!contextStore.isSystemContext && contextStore.selectedOrganization) {
        params.append("entity_id", contextStore.selectedOrganization.id);
      }
      
      params.append("include_system", "true");
      params.append("include_inherited", "true");
      params.append("active_only", state.filters.is_active === false ? "false" : "true");

      const apiUrl = `/v1/permissions/available?${params.toString()}`;

      const response = await authStore.apiCall<PermissionListResponse>(apiUrl, {
        headers,
      });

      // Parse permissions to ensure they have the right structure
      state.permissions = response.permissions.map((p) => ({
        ...p,
        conditions: p.conditions || [],
        tags: p.tags || [],
        metadata: p.metadata || {},
      }));

      state.totalPermissions = response.total;
      state.systemCount = response.system_count;
      state.customCount = response.custom_count;
    } catch (error: any) {
      console.error("Failed to fetch permissions:", error);
      state.error = error.message || "Failed to fetch permissions";
      state.permissions = [];
    } finally {
      state.isLoading = false;
    }
  };

  const fetchPermission = async (id: string) => {
    try {
      const headers = contextStore.getContextHeaders;
      const permission = await authStore.apiCall<Permission>(`/v1/permissions/${id}`, { headers });
      state.selectedPermission = permission;
      return permission;
    } catch (error: any) {
      console.error("Failed to fetch permission:", error);
      state.error = error.message || "Failed to fetch permission";
      throw error;
    }
  };

  const createPermission = async (data: {
    name: string;
    display_name: string;
    description?: string;
    tags?: string[];
    conditions?: Condition[];
    metadata?: Record<string, any>;
  }) => {
    try {
      const headers = contextStore.getContextHeaders;
      
      // Add entity_id if not in system context
      const requestData: any = { ...data };
      if (!contextStore.isSystemContext && contextStore.selectedOrganization) {
        requestData.entity_id = contextStore.selectedOrganization.id;
      }

      const permission = await authStore.apiCall<Permission>("/v1/permissions", {
        method: "POST",
        body: requestData,
        headers,
      });

      // Refresh the list
      await fetchPermissions();

      return permission;
    } catch (error: any) {
      console.error("Failed to create permission:", error);
      throw error;
    }
  };

  const updatePermission = async (
    id: string,
    data: {
      display_name?: string;
      description?: string;
      is_active?: boolean;
      tags?: string[];
      conditions?: Condition[];
      metadata?: Record<string, any>;
    }
  ) => {
    try {
      const headers = contextStore.getContextHeaders;
      const permission = await authStore.apiCall<Permission>(`/v1/permissions/${id}`, {
        method: "PUT",
        body: data,
        headers,
      });

      // Update in local state
      const index = state.permissions.findIndex((p) => p.id === id);
      if (index !== -1) {
        state.permissions[index] = permission;
      }

      if (state.selectedPermission?.id === id) {
        state.selectedPermission = permission;
      }

      return permission;
    } catch (error: any) {
      console.error("Failed to update permission:", error);
      throw error;
    }
  };

  const deletePermission = async (id: string) => {
    try {
      const headers = contextStore.getContextHeaders;
      await authStore.apiCall(`/v1/permissions/${id}`, {
        method: "DELETE",
        headers,
      });

      // Remove from local state
      state.permissions = state.permissions.filter((p) => p.id !== id);

      if (state.selectedPermission?.id === id) {
        state.selectedPermission = null;
      }
    } catch (error: any) {
      console.error("Failed to delete permission:", error);
      throw error;
    }
  };

  const validatePermissions = async (permissions: string[]) => {
    try {
      const headers = contextStore.getContextHeaders;
      
      // Add entity context to validation
      const params = new URLSearchParams();
      if (!contextStore.isSystemContext && contextStore.selectedOrganization) {
        params.append("entity_id", contextStore.selectedOrganization.id);
      }

      const response = await authStore.apiCall<{
        valid: boolean;
        permissions: string[];
        count: number;
      }>(`/v1/permissions/validate?${params.toString()}`, {
        method: "POST",
        body: permissions,
        headers,
      });

      return response;
    } catch (error: any) {
      console.error("Failed to validate permissions:", error);
      throw error;
    }
  };

  // UI Actions
  const openDrawer = (mode: "view" | "create" | "edit" = "view", permission: Permission | null = null) => {
    state.ui.drawerMode = mode;
    state.selectedPermission = permission;
    state.ui.drawerOpen = true;
  };

  const closeDrawer = () => {
    state.ui.drawerOpen = false;
    // Reset selected permission after animation
    setTimeout(() => {
      state.selectedPermission = null;
    }, 300);
  };

  const setDrawerMode = (mode: "view" | "create" | "edit") => {
    state.ui.drawerMode = mode;
  };

  const setFilters = (filters: Partial<PermissionsState["filters"]>) => {
    state.filters = { ...state.filters, ...filters };
    // Note: In a real app, you might want to debounce and refetch
  };

  const resetFilters = () => {
    state.filters = {
      search: "",
      resource: null,
      is_system: null,
      is_active: null,
      has_conditions: null,
      tags: [],
    };
  };

  // Computed
  const filteredPermissions = computed(() => {
    let filtered = state.permissions;

    // Search filter
    if (state.filters.search) {
      const search = state.filters.search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.name.toLowerCase().includes(search) ||
          p.display_name.toLowerCase().includes(search) ||
          p.description?.toLowerCase().includes(search) ||
          p.resource.toLowerCase().includes(search) ||
          p.action.toLowerCase().includes(search)
      );
    }

    // Resource filter
    if (state.filters.resource) {
      filtered = filtered.filter((p) => p.resource === state.filters.resource);
    }

    // System filter
    if (state.filters.is_system !== null) {
      filtered = filtered.filter((p) => p.is_system === state.filters.is_system);
    }

    // Active filter
    if (state.filters.is_active !== null) {
      filtered = filtered.filter((p) => p.is_active === state.filters.is_active);
    }

    // Has conditions filter
    if (state.filters.has_conditions !== null) {
      filtered = filtered.filter((p) => 
        state.filters.has_conditions ? p.conditions.length > 0 : p.conditions.length === 0
      );
    }

    // Tags filter
    if (state.filters.tags.length > 0) {
      filtered = filtered.filter((p) =>
        state.filters.tags.some((tag) => p.tags.includes(tag))
      );
    }

    return filtered;
  });

  // Get unique resources for filtering
  const uniqueResources = computed(() => {
    const resources = new Set<string>();
    state.permissions.forEach((p) => {
      if (p.resource) {
        resources.add(p.resource);
      }
    });
    return Array.from(resources).sort();
  });

  // Get all unique tags
  const allTags = computed(() => {
    const tags = new Set<string>();
    state.permissions.forEach((p) => {
      p.tags.forEach((tag) => tags.add(tag));
    });
    return Array.from(tags).sort();
  });

  // Group permissions by resource
  const permissionsByResource = computed(() => {
    const grouped: Record<string, Permission[]> = {};
    
    filteredPermissions.value.forEach((permission) => {
      const resource = permission.resource || "other";
      if (!grouped[resource]) {
        grouped[resource] = [];
      }
      grouped[resource].push(permission);
    });

    // Sort permissions within each group
    Object.keys(grouped).forEach((resource) => {
      grouped[resource].sort((a, b) => {
        // System permissions first
        if (a.is_system !== b.is_system) {
          return a.is_system ? -1 : 1;
        }
        // Then by action
        return a.action.localeCompare(b.action);
      });
    });

    return grouped;
  });

  return {
    // State (as computed for reactivity)
    permissions: computed(() => state.permissions),
    selectedPermission: computed(() => state.selectedPermission),
    isLoading: computed(() => state.isLoading),
    error: computed(() => state.error),
    totalPermissions: computed(() => state.totalPermissions),
    systemCount: computed(() => state.systemCount),
    customCount: computed(() => state.customCount),
    filters: computed(() => state.filters),
    ui: state.ui, // Return reactive reference directly, not computed

    // Computed
    filteredPermissions,
    uniqueResources,
    allTags,
    permissionsByResource,

    // Actions
    fetchPermissions,
    fetchPermission,
    createPermission,
    updatePermission,
    deletePermission,
    validatePermissions,

    // UI Actions
    openDrawer,
    closeDrawer,
    setDrawerMode,
    setFilters,
    resetFilters,
  };
});