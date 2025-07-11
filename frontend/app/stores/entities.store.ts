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
      parent_entity_id: null,
      status: "",
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

      // Add context-aware filtering
      if (!contextStore.isSystemContext && contextStore.selectedOrganization) {
        // When in organization context, default to showing children of that org
        if (!state.filters.parent_entity_id) {
          params.append("parent_entity_id", contextStore.selectedOrganization.id);
          console.log("Entities Store: Adding parent filter for organization:", contextStore.selectedOrganization.name);
        }
      } else {
        console.log("Entities Store: Using system context - showing all entities");
      }

      // Add filters
      if (state.filters.search) params.append("search", state.filters.search);
      if (state.filters.entity_class) params.append("entity_class", state.filters.entity_class);
      if (state.filters.entity_type) params.append("entity_type", state.filters.entity_type);
      if (state.filters.parent_entity_id) params.append("parent_entity_id", state.filters.parent_entity_id);
      if (state.filters.status) params.append("status", state.filters.status);

      const apiUrl = `/v1/entities?${params.toString()}`;
      console.log("Entities Store: API call URL:", apiUrl);

      const response = await authStore.apiCall<PaginatedResponse<Entity>>(apiUrl);

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
      const entity = await authStore.apiCall<Entity>(`/v1/entities/${id}`);
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
      const entity = await authStore.apiCall<Entity>("/v1/entities", {
        method: "POST",
        body: data,
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
      const entity = await authStore.apiCall<Entity>(`/v1/entities/${id}`, {
        method: "PATCH",
        body: data,
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
      await authStore.apiCall(`/v1/entities/${id}`, {
        method: "DELETE",
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

  const resetFilters = () => {
    state.filters = {
      search: "",
      entity_class: "",
      entity_type: "",
      parent_entity_id: null,
      status: "",
    };
    state.pagination.page = 1;
    fetchEntities();
  };

  // Fetch entity types for autocomplete
  const fetchEntityTypes = async () => {
    try {
      return await authStore.apiCall<string[]>("/v1/entities/entity-types");
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

      const response = await authStore.apiCall<{
        suggestions: Array<{
          entity_type: string;
          count: number;
          last_used?: string;
          is_predefined?: boolean;
        }>;
        total: number;
      }>(`/v1/entities/entity-types?${queryParams.toString()}`);

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
    resetFilters,
    fetchEntityTypes,
    fetchEntityTypeSuggestions,
  };
});
