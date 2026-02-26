/**
 * Entities Store
 * Manages entity hierarchy, CRUD operations, and tree queries
 */

import { defineStore } from "pinia";
import type { Entity, EntityClass } from "~/types/entity";
import type { PaginationParams, PaginatedResponse } from "~/types/api";

export interface EntityFilters {
  search?: string;
  entity_class?: EntityClass;
  entity_type?: string;
  parent_entity_id?: string;
  root_only?: boolean;
}

export interface CreateEntityData {
  name: string;
  display_name: string;
  entity_type: string;
  entity_class: EntityClass;
  parent_entity_id?: string;
  description?: string;
  metadata?: Record<string, any>;
  allowed_child_classes?: string[];
  allowed_child_types?: string[];
  max_members?: number;
}

export interface UpdateEntityData {
  name?: string;
  display_name?: string;
  entity_type?: string;
  description?: string;
  metadata?: Record<string, any>;
  status?: string;
  allowed_child_classes?: string[];
  allowed_child_types?: string[];
  max_members?: number;
}

export interface EntityTreeNode extends Entity {
  children: EntityTreeNode[];
  depth: number;
}

export interface EntityHierarchy {
  path: Entity[];
  descendants: Entity[];
}

export const useEntitiesStore = defineStore("entities", () => {
  const authStore = useAuthStore();

  // State
  const state = reactive({
    entities: [] as Entity[],
    selectedEntity: null as Entity | null,
    entityTree: [] as EntityTreeNode[],
    isLoading: false,
    error: null as string | null,
    pagination: {
      total: 0,
      page: 1,
      limit: 50,
      pages: 0,
    },
  });

  // Getters
  const entities = computed(() => state.entities);
  const selectedEntity = computed(() => state.selectedEntity);
  const entityTree = computed(() => state.entityTree);
  const isLoading = computed(() => state.isLoading);
  const error = computed(() => state.error);
  const pagination = computed(() => state.pagination);

  // Get root entities (no parent)
  const rootEntities = computed(() =>
    state.entities.filter((e) => !e.parent_entity_id),
  );

  // Get STRUCTURAL entities
  const structuralEntities = computed(() =>
    state.entities.filter((e) => e.entity_class === "structural"),
  );

  // Get ACCESS_GROUP entities
  const accessGroupEntities = computed(() =>
    state.entities.filter((e) => e.entity_class === "access_group"),
  );

  /**
   * Build tree structure from flat entity list
   */
  const buildTree = (
    entities: Entity[],
    parentEntityId?: string,
    depth = 0,
  ): EntityTreeNode[] => {
    return entities
      .filter((e) => e.parent_entity_id === parentEntityId)
      .map((entity) => ({
        ...entity,
        depth,
        children: buildTree(entities, entity.id, depth + 1),
      }));
  };

  /**
   * Fetch entities with pagination, search, and filters
   */
  const fetchEntities = async (
    filters: EntityFilters = {},
    params: PaginationParams = {},
  ): Promise<void> => {
    try {
      state.isLoading = true;
      state.error = null;

      const queryParams = new URLSearchParams();
      if (filters.search) queryParams.append("search", filters.search);
      if (filters.entity_class)
        queryParams.append("entity_class", filters.entity_class);
      if (filters.entity_type)
        queryParams.append("entity_type", filters.entity_type);
      if (filters.parent_entity_id !== undefined)
        queryParams.append("parent_id", filters.parent_entity_id);
      if (filters.root_only) queryParams.append("root_only", "true");
      if (params.page) queryParams.append("page", String(params.page));
      if (params.limit) queryParams.append("limit", String(params.limit));
      if (params.sort_by) queryParams.append("sort_by", params.sort_by);
      if (params.sort_order)
        queryParams.append("sort_order", params.sort_order);

      const response = await authStore.apiCall<PaginatedResponse<Entity>>(
        `/v1/entities/?${queryParams.toString()}`,
      );

      state.entities = response.items;
      state.pagination = {
        total: response.total,
        page: response.page,
        limit: response.limit,
        pages: response.pages,
      };

      // Build tree structure
      state.entityTree = buildTree(response.items);
    } catch (error: any) {
      state.error = error.message || "Failed to fetch entities";
      console.error("Failed to fetch entities:", error);
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Fetch single entity by ID
   */
  const fetchEntity = async (entityId: string): Promise<Entity | null> => {
    try {
      state.isLoading = true;
      state.error = null;

      const entity = await authStore.apiCall<Entity>(
        `/v1/entities/${entityId}`,
      );
      state.selectedEntity = entity;
      return entity;
    } catch (error: any) {
      state.error = error.message || "Failed to fetch entity";
      console.error("Failed to fetch entity:", error);
      return null;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Get entity hierarchy (path and descendants)
   */
  const getEntityHierarchy = async (
    entityId: string,
  ): Promise<EntityHierarchy | null> => {
    try {
      state.isLoading = true;
      state.error = null;

      const [path, descendants] = await Promise.all([
        authStore.apiCall<Entity[]>(`/v1/entities/${entityId}/path`),
        authStore.apiCall<Entity[]>(`/v1/entities/${entityId}/descendants`),
      ]);

      return { path, descendants };
    } catch (error: any) {
      state.error = error.message || "Failed to fetch entity hierarchy";
      console.error("Failed to fetch entity hierarchy:", error);
      return null;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Get entity path (all ancestors)
   */
  const getEntityPath = async (entityId: string): Promise<Entity[]> => {
    const hierarchy = await getEntityHierarchy(entityId);
    return hierarchy?.path || [];
  };

  /**
   * Get entity descendants (all children recursively)
   */
  const getEntityDescendants = async (entityId: string): Promise<Entity[]> => {
    const hierarchy = await getEntityHierarchy(entityId);
    return hierarchy?.descendants || [];
  };

  /**
   * Create new entity
   */
  const createEntity = async (
    data: CreateEntityData,
  ): Promise<Entity | null> => {
    try {
      state.isLoading = true;
      state.error = null;

      const entity = await authStore.apiCall<Entity>("/v1/entities/", {
        method: "POST",
        body: JSON.stringify(data),
      });

      return entity;
    } catch (error: any) {
      state.error = error.message || "Failed to create entity";
      console.error("Failed to create entity:", error);
      throw error;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Update entity
   */
  const updateEntity = async (
    entityId: string,
    data: UpdateEntityData,
  ): Promise<Entity | null> => {
    try {
      state.isLoading = true;
      state.error = null;

      const entity = await authStore.apiCall<Entity>(
        `/v1/entities/${entityId}`,
        {
          method: "PATCH",
          body: JSON.stringify(data),
        },
      );

      state.selectedEntity = entity;
      return entity;
    } catch (error: any) {
      state.error = error.message || "Failed to update entity";
      console.error("Failed to update entity:", error);
      throw error;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Move entity to new parent
   */
  const moveEntity = async (
    entityId: string,
    newParentId: string | null,
  ): Promise<boolean> => {
    try {
      state.isLoading = true;
      state.error = null;

      await authStore.apiCall(`/v1/entities/${entityId}/move`, {
        method: "POST",
        body: JSON.stringify({ new_parent_id: newParentId }),
      });

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to move entity";
      console.error("Failed to move entity:", error);
      return false;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Delete entity
   */
  const deleteEntity = async (entityId: string): Promise<boolean> => {
    try {
      state.isLoading = true;
      state.error = null;

      await authStore.apiCall(`/v1/entities/${entityId}`, {
        method: "DELETE",
      });

      // Remove from local state
      const stateIndex = state.entities.findIndex((e) => e.id === entityId);
      if (stateIndex !== -1) {
        state.entities.splice(stateIndex, 1);
      }

      if (state.selectedEntity?.id === entityId) {
        state.selectedEntity = null;
      }

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to delete entity";
      console.error("Failed to delete entity:", error);
      return false;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Get children of entity
   */
  const getChildren = (entityId: string): Entity[] => {
    return state.entities.filter((e) => e.parent_entity_id === entityId);
  };

  /**
   * Check if entity has children
   */
  const hasChildren = (entityId: string): boolean => {
    return state.entities.some((e) => e.parent_entity_id === entityId);
  };

  /**
   * Clear selected entity
   */
  const clearSelectedEntity = (): void => {
    state.selectedEntity = null;
  };

  /**
   * Clear error
   */
  const clearError = (): void => {
    state.error = null;
  };

  return {
    // State (do not use readonly - prevents Pinia mutations)
    state,

    // Getters
    entities,
    selectedEntity,
    entityTree,
    isLoading,
    error,
    pagination,
    rootEntities,
    structuralEntities,
    accessGroupEntities,

    // Actions
    fetchEntities,
    fetchEntity,
    getEntityHierarchy,
    getEntityPath,
    getEntityDescendants,
    createEntity,
    updateEntity,
    moveEntity,
    deleteEntity,
    getChildren,
    hasChildren,
    clearSelectedEntity,
    clearError,
  };
});
