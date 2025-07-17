import type { Entity, PaginatedResponse } from "~/types/auth.types";

interface EntitiesState {
  entities: Entity[];
  selectedEntity: Entity | null;
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
    entity_class: string;
    entity_type: string;
    parent_entity_id: string | null;
    status: string;
    include_children: boolean;
  };
}

export const useEntitiesStore = defineStore("entities", () => {
  // State
  const state = reactive<EntitiesState>({
    entities: [],
    selectedEntity: null,
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
      entity_class: "",
      entity_type: "",
      parent_entity_id: null, // Will be set based on context
      status: "",
      include_children: false,
    },
  });

  // Use auth store for API calls
  const authStore = useAuthStore();

  // Actions
  const fetchEntities = async () => {
    state.isLoading = true;
    state.error = null;

    try {
      // Get context information
      const contextStore = useContextStore();

      console.log("Entities Store: Fetching entities with context:", {
        isSystemContext: contextStore.isSystemContext,
        selectedOrg: contextStore.selectedOrganization?.name,
        currentParentFilter: state.filters.parent_entity_id,
      });

      // Build query params
      const params = new URLSearchParams();
      params.append("page", state.pagination.page.toString());
      params.append("page_size", state.pagination.pageSize.toString());

      // Let the filters determine what to show - don't override based on context
      console.log("Entities Store: Context aware fetch with filters:", {
        isSystemContext: contextStore.isSystemContext,
        selectedOrg: contextStore.selectedOrganization?.name,
        parentFilter: state.filters.parent_entity_id,
      });

      // Add filters
      if (state.filters.search) params.append("search", state.filters.search);
      if (state.filters.entity_class) params.append("entity_class", state.filters.entity_class);
      if (state.filters.entity_type) params.append("entity_type", state.filters.entity_type);
      
      // Handle parent_entity_id filter
      if (state.filters.parent_entity_id === "null") {
        // Special case for filtering top-level entities (no parent)
        params.append("parent_entity_id", "null");
      } else if (state.filters.parent_entity_id) {
        params.append("parent_entity_id", state.filters.parent_entity_id);
      }
      
      // Include children flag
      if (state.filters.include_children) {
        params.append("include_children", "true");
      }
      
      if (state.filters.status) params.append("status", state.filters.status);

      const apiUrl = `/v1/entities?${params.toString()}`;
      console.log("Entities Store: API call URL:", apiUrl);

      // Include context headers from context store
      const headers = contextStore.getContextHeaders;
      const response = await authStore.apiCall<PaginatedResponse<Entity>>(apiUrl, {
        headers
      });

      state.entities = response.items;
      state.pagination = {
        page: response.page,
        pageSize: response.page_size,
        total: response.total,
        totalPages: response.total_pages,
      };
    } catch (error: any) {
      console.error("Failed to fetch entities:", error);
      state.error = error.message || "Failed to fetch entities";
    } finally {
      state.isLoading = false;
    }
  };

  const fetchEntity = async (id: string) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      const entity = await authStore.apiCall<Entity>(`/v1/entities/${id}`, { headers });
      state.selectedEntity = entity;
      return entity;
    } catch (error: any) {
      console.error("Failed to fetch entity:", error);
      state.error = error.message || "Failed to fetch entity";
      throw error;
    }
  };

  const createEntity = async (data: Partial<Entity>) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      const entity = await authStore.apiCall<Entity>("/v1/entities", {
        method: "POST",
        body: data,
        headers
      });

      // Refresh the list
      await fetchEntities();

      return entity;
    } catch (error: any) {
      console.error("Failed to create entity:", error);
      throw error;
    }
  };

  const updateEntity = async (id: string, data: Partial<Entity>) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      const entity = await authStore.apiCall<Entity>(`/v1/entities/${id}`, {
        method: "PATCH",
        body: data,
        headers
      });

      // Update in local state
      const index = state.entities.findIndex((e) => e.id === id);
      if (index !== -1) {
        state.entities[index] = entity;
      }

      if (state.selectedEntity?.id === id) {
        state.selectedEntity = entity;
      }

      return entity;
    } catch (error: any) {
      console.error("Failed to update entity:", error);
      throw error;
    }
  };

  const deleteEntity = async (id: string) => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      await authStore.apiCall(`/v1/entities/${id}`, {
        method: "DELETE",
        headers
      });

      // Remove from local state
      state.entities = state.entities.filter((e) => e.id !== id);

      if (state.selectedEntity?.id === id) {
        state.selectedEntity = null;
      }
    } catch (error: any) {
      console.error("Failed to delete entity:", error);
      throw error;
    }
  };

  const setPage = (page: number) => {
    state.pagination.page = page;
    fetchEntities();
  };

  const setPageSize = (pageSize: number) => {
    state.pagination.pageSize = pageSize;
    state.pagination.page = 1; // Reset to first page
    fetchEntities();
  };

  const setFilters = (filters: Partial<EntitiesState["filters"]>) => {
    state.filters = { ...state.filters, ...filters };
    state.pagination.page = 1; // Reset to first page
    fetchEntities();
  };
  
  // Set specific filter for hierarchy level
  const setHierarchyLevel = (level: "top" | "all") => {
    const contextStore = useContextStore();
    
    if (level === "top") {
      if (contextStore.isSystemContext) {
        // In system context, show top-level entities (no parent)
        state.filters.parent_entity_id = "null";
        state.filters.include_children = false;
      } else if (contextStore.selectedOrganization) {
        // In organization context, show direct children of the organization
        state.filters.parent_entity_id = contextStore.selectedOrganization.id;
        state.filters.include_children = false;
      }
    } else {
      // Show all entities within the context
      if (contextStore.isSystemContext) {
        // In system context, show all entities
        state.filters.parent_entity_id = null;
        state.filters.include_children = false;
      } else if (contextStore.selectedOrganization) {
        // In organization context, show the org and all its descendants
        state.filters.parent_entity_id = contextStore.selectedOrganization.id;
        state.filters.include_children = true;
      }
    }
    state.pagination.page = 1;
    fetchEntities();
  };

  const resetFilters = () => {
    const contextStore = useContextStore();
    
    // Set default parent filter based on context
    let defaultParentFilter: string | null;
    if (contextStore.isSystemContext) {
      // In system context, default to top-level entities
      defaultParentFilter = "null";
    } else if (contextStore.selectedOrganization) {
      // In organization context, default to direct children of the org
      defaultParentFilter = contextStore.selectedOrganization.id;
    } else {
      defaultParentFilter = null;
    }
    
    state.filters = {
      search: "",
      entity_class: "",
      entity_type: "",
      parent_entity_id: defaultParentFilter,
      status: "",
      include_children: false,
    };
    state.pagination.page = 1;
    fetchEntities();
  };

  // Fetch entity types for autocomplete
  const fetchEntityTypes = async () => {
    try {
      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      return await authStore.apiCall<string[]>("/v1/entities/entity-types", { headers });
    } catch (error: any) {
      console.error("Failed to fetch entity types:", error);
      return [];
    }
  };

  // Fetch entity type suggestions with usage counts and predefined types
  const fetchEntityTypeSuggestions = async (
    params: {
      platformId?: string;
      entityClass?: "STRUCTURAL" | "ACCESS_GROUP";
      search?: string;
    } = {}
  ) => {
    try {
      const queryParams = new URLSearchParams();
      if (params.platformId) queryParams.append("platform_id", params.platformId);
      if (params.entityClass) queryParams.append("entity_class", params.entityClass);
      if (params.search) queryParams.append("search", params.search);

      console.log("Fetching entity type suggestions with params:", params);

      const contextStore = useContextStore();
      const headers = contextStore.getContextHeaders;
      const response = await authStore.apiCall<{
        suggestions: Array<{
          entity_type: string;
          count: number;
          last_used?: string;
          is_predefined?: boolean;
        }>;
        total: number;
      }>(`/v1/entities/entity-types?${queryParams.toString()}`, { headers });

      console.log("Entity type suggestions response:", response);

      return response;
    } catch (error: any) {
      console.error("Failed to fetch entity type suggestions:", error);
      // Return fallback structure
      return {
        suggestions: [],
        total: 0,
      };
    }
  };

  return {
    // State (as computed for reactivity)
    entities: computed(() => state.entities),
    selectedEntity: computed(() => state.selectedEntity),
    isLoading: computed(() => state.isLoading),
    error: computed(() => state.error),
    pagination: computed(() => state.pagination),
    filters: computed(() => state.filters),

    // Actions
    fetchEntities,
    fetchEntity,
    createEntity,
    updateEntity,
    deleteEntity,
    setPage,
    setPageSize,
    setFilters,
    setHierarchyLevel,
    resetFilters,
    fetchEntityTypes,
    fetchEntityTypeSuggestions,
  };
});
