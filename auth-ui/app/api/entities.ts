/**
 * Entities API
 * API functions for entity management
 */

import type { Entity } from "~/types/entity";
import type { PaginationParams, PaginatedResponse } from "~/types/api";
import type {
  EntityFilters,
  CreateEntityData,
  UpdateEntityData,
  EntityHierarchy,
} from "~/stores/entities.store";
import { createAPIClient } from "./client";

export function createEntitiesAPI() {
  const client = createAPIClient();

  return {
    /**
     * Fetch entities with pagination and filters
     */
    async fetchEntities(
      filters: EntityFilters = {},
      params: PaginationParams = {},
    ): Promise<PaginatedResponse<Entity>> {
      const queryString = client.buildQueryString({
        search: filters.search,
        entity_class: filters.entity_class,
        entity_type: filters.entity_type,
        parent_id: filters.parent_entity_id,
        root_only: filters.root_only,
        page: params.page,
        limit: params.limit,
        sort_by: params.sort_by,
        sort_order: params.sort_order,
      });

      return client.call<PaginatedResponse<Entity>>(
        `/v1/entities/${queryString}`,
      );
    },

    /**
     * Fetch single entity by ID
     */
    async fetchEntity(entityId: string): Promise<Entity> {
      return client.call<Entity>(`/v1/entities/${entityId}`);
    },

    /**
     * Get entity hierarchy (path and descendants)
     */
    async getEntityHierarchy(entityId: string): Promise<EntityHierarchy> {
      const [path, descendants] = await Promise.all([
        client.call<Entity[]>(`/v1/entities/${entityId}/path`),
        client.call<Entity[]>(`/v1/entities/${entityId}/descendants`),
      ]);

      return { path, descendants };
    },

    /**
     * Create new entity
     */
    async createEntity(data: CreateEntityData): Promise<Entity> {
      return client.call<Entity>("/v1/entities/", {
        method: "POST",
        body: data,
      });
    },

    /**
     * Update entity
     */
    async updateEntity(
      entityId: string,
      data: UpdateEntityData,
    ): Promise<Entity> {
      return client.call<Entity>(`/v1/entities/${entityId}`, {
        method: "PATCH",
        body: data,
      });
    },

    /**
     * Move entity to new parent
     */
    async moveEntity(
      entityId: string,
      newParentId: string | null,
    ): Promise<void> {
      return client.call<void>(`/v1/entities/${entityId}/move`, {
        method: "POST",
        body: { new_parent_id: newParentId },
      });
    },

    /**
     * Delete entity
     */
    async deleteEntity(entityId: string): Promise<void> {
      return client.call<void>(`/v1/entities/${entityId}`, {
        method: "DELETE",
      });
    },
  };
}
