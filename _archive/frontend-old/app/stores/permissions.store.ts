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
  // Form State
  formState: {
    display_name: string;
    resource: string;
    action: string;
    description: string;
    is_active: boolean;
    tags: string[];
    conditions: Condition[];
  };
}

export const usePermissionsStore = defineStore("permissions", () => {
  // State
  const state = reactive<PermissionsState>({
    permissions: [],
    selectedPermission: null,
    isLoading: false,
    error: null,
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
    formState: {
      display_name: "",
      resource: "",
      action: "",
      description: "",
      is_active: true,
      tags: [],
      conditions: [],
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
      
      console.log('[PermissionsStore] Fetching permissions with context:', {
        isSystemContext: contextStore.isSystemContext,
        selectedOrg: contextStore.selectedOrganization,
        headers: headers
      });

      // Build query params
      const params = new URLSearchParams();
      
      // Add entity_id if we have a context selected (not system context)
      if (!contextStore.isSystemContext && contextStore.selectedOrganization?.id) {
        params.append("entity_id", contextStore.selectedOrganization.id);
      }
      
      // Always include system permissions and inherited permissions
      // The frontend will filter based on context
      params.append("include_system", "true");
      params.append("include_inherited", "true");
      params.append("active_only", state.filters.is_active === false ? "false" : "true");

      const apiUrl = `/v1/permissions/available?${params.toString()}`;

      const response = await authStore.apiCall<PermissionListResponse>(apiUrl, {
        headers,
      });

      console.log('[PermissionsStore] Raw API response:', {
        total: response.total,
        system_count: response.system_count,
        custom_count: response.custom_count,
        permissions_count: response.permissions.length,
        permissions: response.permissions
      });

      // Parse permissions to ensure they have the right structure
      state.permissions = response.permissions.map((p) => ({
        ...p,
        conditions: p.conditions || [],
        tags: p.tags || [],
        metadata: p.metadata || {},
      }));
      
      console.log('[PermissionsStore] After mapping, total permissions:', state.permissions.length);
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
      const permission = await authStore.apiCall<Permission>(`/v1/permissions/${id}/`, { headers });
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
      
      console.log('[PermissionsStore] Creating permission with data:', requestData);
      console.log('[PermissionsStore] Current context:', {
        isSystemContext: contextStore.isSystemContext,
        selectedOrgId: contextStore.selectedOrganization?.id
      });

      const permission = await authStore.apiCall<Permission>("/v1/permissions/", {
        method: "POST",
        body: requestData,
        headers,
      });

      console.log('[PermissionsStore] Created permission:', permission);

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
      const permission = await authStore.apiCall<Permission>(`/v1/permissions/${id}/`, {
        method: "PUT",
        body: data,
        headers,
      });

      // Update in local state - ensure reactivity by replacing the array
      const index = state.permissions.findIndex((p) => p.id === id);
      if (index !== -1) {
        // Create a new array to trigger Vue's reactivity
        const updatedPermissions = [...state.permissions];
        updatedPermissions[index] = permission;
        state.permissions = updatedPermissions;
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
      await authStore.apiCall(`/v1/permissions/${id}/`, {
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
  const openDrawer = async (mode: "view" | "create" | "edit" = "view", permission: Permission | null = null) => {
    state.ui.drawerMode = mode;
    state.selectedPermission = permission;
    
    // Ensure permissions are loaded
    if (state.permissions.length === 0) {
      await fetchPermissions();
    }
    
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

  // Computed - No frontend filtering needed, backend handles context filtering
  const contextFilteredPermissions = computed(() => {
    // Backend already filters based on entity_id query param
    // Just return all permissions received from the API
    console.log('[PermissionsStore] Total permissions from backend:', state.permissions.length);
    return state.permissions;
  });

  const filteredPermissions = computed(() => {
    // Start with context-filtered permissions
    let filtered = contextFilteredPermissions.value;

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

  // Get unique resources for filtering (context-aware)
  const uniqueResources = computed(() => {
    const resources = new Set<string>();
    // Use context-filtered permissions for consistency
    contextFilteredPermissions.value.forEach((p) => {
      if (p.resource) {
        resources.add(p.resource);
      }
    });
    return Array.from(resources).sort();
  });

  // Get all unique tags (context-aware)
  const allTags = computed(() => {
    const tags = new Set<string>();
    // Use context-filtered permissions for consistency
    contextFilteredPermissions.value.forEach((p) => {
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

  // Get custom resources only (non-system permissions, context-aware)
  const customResources = computed(() => {
    const resources = new Set<string>();
    // Use context-filtered permissions for consistency
    contextFilteredPermissions.value
      .filter(p => !p.is_system && p.resource)
      .forEach(p => resources.add(p.resource));
    return Array.from(resources).sort();
  });

  // Get custom actions, optionally filtered by resource (context-aware)
  const customActions = computed(() => {
    return (resource?: string) => {
      // Use context-filtered permissions for consistency
      let perms = contextFilteredPermissions.value.filter(p => !p.is_system);
      if (resource) {
        perms = perms.filter(p => p.resource === resource);
      }
      const actions = new Set<string>();
      perms.forEach(p => {
        if (p.action) actions.add(p.action);
      });
      return Array.from(actions).sort();
    };
  });

  // Common resource suggestions
  const commonResourceSuggestions = computed(() => ['invoice', 'report', 'document', 'budget', 'expense', 'contract', 'purchase_order']);
  
  // Common action suggestions
  const commonActionSuggestions = computed(() => ['approve', 'submit', 'export', 'import', 'review', 'sign', 'publish', 'archive', 'reject']);
  
  // Context-aware counts
  const contextAwareTotalPermissions = computed(() => contextFilteredPermissions.value.length);
  const contextAwareSystemCount = computed(() => contextFilteredPermissions.value.filter(p => p.is_system).length);
  const contextAwareCustomCount = computed(() => contextFilteredPermissions.value.filter(p => !p.is_system).length);

  // Form Methods
  const resetFormState = () => {
    state.formState = {
      display_name: "",
      resource: "",
      action: "",
      description: "",
      is_active: true,
      tags: [],
      conditions: [],
    };
  };

  const setFormField = <K extends keyof PermissionsState['formState']>(
    field: K,
    value: PermissionsState['formState'][K]
  ) => {
    console.log(`[PermissionsStore] Setting form field '${field}' to:`, value);
    state.formState[field] = value;
    console.log(`[PermissionsStore] Form state after update:`, state.formState);
  };

  const loadFormFromPermission = (permission: Permission) => {
    state.formState = {
      display_name: permission.display_name || "",
      resource: permission.resource || "",
      action: permission.action || "",
      description: permission.description || "",
      is_active: permission.is_active ?? true,
      tags: permission.tags || [],
      conditions: permission.conditions || [],
    };
  };

  // Add a temporary custom permission to the list (for newly created resources/actions)
  const addTemporaryCustomPermission = (resource: string, action?: string) => {
    // Check if we already have a permission with this resource/action combo
    const exists = state.permissions.some(p => 
      p.resource === resource && (!action || p.action === action)
    );
    
    if (!exists && resource) {
      // Create a temporary permission object with proper context
      const tempPermission: Permission = {
        id: `temp_${Date.now()}`,
        name: action ? `${resource}:${action}` : `${resource}:temp`,
        display_name: action ? `${resource} ${action}` : resource,
        resource: resource,
        action: action || 'temp',
        is_system: false,
        is_active: true,
        entity_id: !contextStore.isSystemContext ? contextStore.selectedOrganization?.id : undefined,
        conditions: [],
        tags: [],
        metadata: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
      
      console.log('[PermissionsStore] Adding temporary permission:', tempPermission);
      state.permissions.push(tempPermission);
    }
  };

  // Getters - These are reactive and will update automatically
  const permissions = computed(() => state.permissions);
  const selectedPermission = computed(() => state.selectedPermission);
  const isLoading = computed(() => state.isLoading);
  const error = computed(() => state.error);
  const filters = computed(() => state.filters);
  
  // UI state can be returned as reactive ref directly
  const ui = toRef(state, 'ui');
  const formState = toRef(state, 'formState');

  // Context-aware getters - these will automatically update when context changes
  const currentContext = computed(() => ({
    isSystemContext: contextStore.isSystemContext,
    organizationId: contextStore.selectedOrganization?.id
  }));

  // Use the actual filtered permissions count for display instead of API counts
  const displayCounts = computed(() => ({
    total: contextFilteredPermissions.value.length,
    system: contextFilteredPermissions.value.filter(p => p.is_system).length,
    custom: contextFilteredPermissions.value.filter(p => !p.is_system).length
  }));

  return {
    // State getters
    permissions,
    selectedPermission,
    isLoading,
    error,
    filters,
    ui,
    formState,

    // Context-aware getters
    currentContext,
    displayCounts,
    
    // Filtered/computed data
    filteredPermissions,
    contextFilteredPermissions,
    uniqueResources,
    allTags,
    permissionsByResource,
    customResources,
    customActions,
    commonResourceSuggestions,
    commonActionSuggestions,

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

    // Form Actions
    resetFormState,
    setFormField,
    loadFormFromPermission,
    addTemporaryCustomPermission,
  };
});