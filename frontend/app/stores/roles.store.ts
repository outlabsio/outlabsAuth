import type { Role, PaginatedResponse } from "~/types/auth.types";

interface RolesState {
  roles: Role[];
  selectedRole: Role | null;
  isLoading: boolean;
  error: string | null;
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
  };
  filters: {
    search: string;
    entity_id: string | null;
    is_global: boolean | null;
    is_system_role: boolean | null;
    assignable_at_type: string | null;
  };
  // UI State
  ui: {
    drawerOpen: boolean;
    drawerMode: 'view' | 'create' | 'edit';
  };
}

export const useRolesStore = defineStore("roles", () => {
  // State
  const state = reactive<RolesState>({
    roles: [],
    selectedRole: null,
    isLoading: false,
    error: null,
    pagination: {
      page: 1,
      pageSize: 20,
      total: 0,
      totalPages: 0,
    },
    filters: {
      search: "",
      entity_id: null,
      is_global: null,
      is_system_role: null,
      assignable_at_type: null,
    },
    ui: {
      drawerOpen: false,
      drawerMode: 'view',
    },
  });

  // Use auth store for API calls
  const authStore = useAuthStore();

  // Actions
  const fetchRoles = async () => {
    state.isLoading = true;
    state.error = null;

    try {
      // Get context information
      const contextStore = useContextStore();

      // Build query params
      const params = new URLSearchParams();
      params.append("page", state.pagination.page.toString());
      params.append("page_size", state.pagination.pageSize.toString());

      // Add entity_id if we have a context selected (not system context)
      if (!contextStore.isSystemContext && contextStore.selectedOrganization?.id) {
        params.append("entity_id", contextStore.selectedOrganization.id);
        console.log('[RolesStore] Adding entity_id to query:', contextStore.selectedOrganization.id);
      } else {
        console.log('[RolesStore] No entity context - isSystemContext:', contextStore.isSystemContext, 'selectedOrg:', contextStore.selectedOrganization);
      }
      
      // Add filters
      if (state.filters.search) params.append("query", state.filters.search);
      // Don't add entity_id from filters if we already added it from context
      if (state.filters.entity_id && (!contextStore.selectedOrganization?.id || contextStore.isSystemContext)) {
        params.append("entity_id", state.filters.entity_id);
      }
      if (state.filters.is_global !== null) params.append("is_global", state.filters.is_global.toString());
      if (state.filters.is_system_role !== null) params.append("is_system_role", state.filters.is_system_role.toString());
      if (state.filters.assignable_at_type) params.append("assignable_at_type", state.filters.assignable_at_type);

      const apiUrl = `/v1/roles?${params.toString()}`;
      console.log('[RolesStore] Fetching roles with URL:', apiUrl);

      // Include context headers from context store
      const headers = contextStore.getContextHeaders;
      console.log('[RolesStore] Context headers:', headers);
      const response = await authStore.apiCall<PaginatedResponse<Role>>(apiUrl, {
        headers
      });

      state.roles = response.items;
      state.pagination = {
        page: response.page,
        pageSize: response.page_size,
        total: response.total,
        totalPages: response.total_pages,
      };
    } catch (error: any) {
      console.error("Failed to fetch roles:", error);
      state.error = error.message || "Failed to fetch roles";
    } finally {
      state.isLoading = false;
    }
  };

  const fetchRole = async (id: string) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      const role = await authStore.apiCall<Role>(`/v1/roles/${id}`, { headers });
      state.selectedRole = role;
      return role;
    } catch (error: any) {
      console.error("Failed to fetch role:", error);
      state.error = error.message || "Failed to fetch role";
      throw error;
    }
  };

  const createRole = async (data: {
    name: string;
    display_name: string;
    description?: string;
    permissions: string[];
    entity_id?: string;
    assignable_at_types?: string[];
    is_global?: boolean;
  }) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      
      // Add entity_id if not in system context and not provided
      const requestData = { ...data };
      if (!contextStore.isSystemContext && contextStore.selectedOrganization && !requestData.entity_id) {
        requestData.entity_id = contextStore.selectedOrganization.id;
      }
      
      const role = await authStore.apiCall<Role>("/v1/roles", {
        method: "POST",
        body: requestData,
        headers
      });

      // Refresh the list
      await fetchRoles();

      return role;
    } catch (error: any) {
      console.error("Failed to create role:", error);
      throw error;
    }
  };

  const updateRole = async (id: string, data: {
    display_name?: string;
    description?: string;
    permissions?: string[];
    assignable_at_types?: string[];
  }) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      const role = await authStore.apiCall<Role>(`/v1/roles/${id}`, {
        method: "PUT",
        body: data,
        headers
      });

      // Update in local state
      const index = state.roles.findIndex((r) => r.id === id);
      if (index !== -1) {
        state.roles[index] = role;
      }

      if (state.selectedRole?.id === id) {
        state.selectedRole = role;
      }

      return role;
    } catch (error: any) {
      console.error("Failed to update role:", error);
      throw error;
    }
  };

  const deleteRole = async (id: string) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      await authStore.apiCall(`/v1/roles/${id}`, {
        method: "DELETE",
        headers
      });

      // Remove from local state
      state.roles = state.roles.filter((r) => r.id !== id);

      if (state.selectedRole?.id === id) {
        state.selectedRole = null;
      }
    } catch (error: any) {
      console.error("Failed to delete role:", error);
      throw error;
    }
  };

  const setPage = (page: number) => {
    state.pagination.page = page;
    fetchRoles();
  };

  const setPageSize = (pageSize: number) => {
    state.pagination.pageSize = pageSize;
    state.pagination.page = 1; // Reset to first page
    fetchRoles();
  };

  const setFilters = (filters: Partial<RolesState["filters"]>) => {
    state.filters = { ...state.filters, ...filters };
    state.pagination.page = 1; // Reset to first page
    fetchRoles();
  };

  const resetFilters = () => {
    state.filters = {
      search: "",
      entity_id: null,
      is_global: null,
      is_system_role: null,
      assignable_at_type: null,
    };
    state.pagination.page = 1;
    fetchRoles();
  };

  // Fetch role templates for creating new roles
  const fetchRoleTemplates = async () => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      return await authStore.apiCall<any[]>("/v1/roles/templates", { headers });
    } catch (error: any) {
      console.error("Failed to fetch role templates:", error);
      return [];
    }
  };

  // Get role usage statistics
  const fetchRoleUsage = async (roleId: string) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      return await authStore.apiCall<any>(`/v1/roles/${roleId}/usage`, { headers });
    } catch (error: any) {
      console.error("Failed to fetch role usage:", error);
      return null;
    }
  };

  // UI Actions
  const openDrawer = (mode: 'view' | 'create' | 'edit' = 'view', role: Role | null = null) => {
    state.ui.drawerMode = mode;
    state.selectedRole = role;
    state.ui.drawerOpen = true;
  };

  const closeDrawer = () => {
    state.ui.drawerOpen = false;
    // Reset selected role after animation
    setTimeout(() => {
      state.selectedRole = null;
    }, 300);
  };

  const setDrawerMode = (mode: 'view' | 'create' | 'edit') => {
    state.ui.drawerMode = mode;
  };

  return {
    // State (as computed for reactivity)
    roles: computed(() => state.roles),
    selectedRole: computed(() => state.selectedRole),
    isLoading: computed(() => state.isLoading),
    error: computed(() => state.error),
    pagination: computed(() => state.pagination),
    filters: computed(() => state.filters),
    ui: computed(() => state.ui),

    // Actions
    fetchRoles,
    fetchRole,
    createRole,
    updateRole,
    deleteRole,
    setPage,
    setPageSize,
    setFilters,
    resetFilters,
    fetchRoleTemplates,
    fetchRoleUsage,

    // UI Actions
    openDrawer,
    closeDrawer,
    setDrawerMode,
  };
});