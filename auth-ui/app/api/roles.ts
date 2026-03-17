/**
 * Roles API
 * API functions for role management
 */

import type { Role, CreateRoleData, UpdateRoleData } from "~/types/role";
import type { PaginationParams, PaginatedResponse } from "~/types/api";
import type { RoleFilters } from "~/stores/roles.store";
import type {
  AbacCondition,
  AbacConditionCreateData,
  AbacConditionUpdateData,
  ConditionGroup,
  ConditionGroupCreateData,
  ConditionGroupUpdateData,
} from "~/types/abac";
import { createAPIClient } from "./client";

export function createRolesAPI() {
  const client = createAPIClient();

  return {
    /**
     * Fetch roles with pagination and filters
     */
    async fetchRoles(
      filters: RoleFilters = {},
      params: PaginationParams = {},
    ): Promise<PaginatedResponse<Role>> {
      const forEntityId = filters.for_entity_id;

      if (forEntityId) {
        const entityQuery = client.buildQueryString({
          page: params.page,
          limit: params.limit,
        });

        return client.call<PaginatedResponse<Role>>(
          `/v1/roles/entity/${forEntityId}${entityQuery}`
        );
      }

      const queryString = client.buildQueryString({
        search: filters.search,
        is_global: filters.is_global,
        root_entity_id: filters.root_entity_id,
        page: params.page,
        limit: params.limit,
      });

      return client.call<PaginatedResponse<Role>>(`/v1/roles/${queryString}`);
    },

    /**
     * Fetch single role by ID
     */
    async fetchRole(roleId: string): Promise<Role> {
      return client.call<Role>(`/v1/roles/${roleId}`);
    },

    /**
     * Create new role
     */
    async createRole(data: CreateRoleData): Promise<Role> {
      return client.call<Role>("/v1/roles", {
        method: "POST",
        body: data,
      });
    },

    /**
     * Update role
     */
    async updateRole(roleId: string, data: UpdateRoleData): Promise<Role> {
      return client.call<Role>(`/v1/roles/${roleId}`, {
        method: "PATCH",
        body: data,
      });
    },

    /**
     * Delete role
     */
    async deleteRole(roleId: string): Promise<void> {
      return client.call<void>(`/v1/roles/${roleId}`, {
        method: "DELETE",
      });
    },

    /**
     * Assign permissions to role
     */
    async assignPermissions(
      roleId: string,
      permissions: string[],
    ): Promise<Role> {
      return client.call<Role>(`/v1/roles/${roleId}/permissions`, {
        method: "POST",
        body: JSON.stringify(permissions),
      });
    },

    /**
     * Remove permissions from role
     */
    async removePermissions(
      roleId: string,
      permissions: string[],
    ): Promise<Role> {
      return client.call<Role>(`/v1/roles/${roleId}/permissions`, {
        method: "DELETE",
        body: JSON.stringify(permissions),
      });
    },

    /**
     * ABAC - Condition groups
     */
    async fetchConditionGroups(roleId: string): Promise<ConditionGroup[]> {
      return client.call<ConditionGroup[]>(`/v1/roles/${roleId}/condition-groups`);
    },
    async createConditionGroup(
      roleId: string,
      data: ConditionGroupCreateData,
    ): Promise<ConditionGroup> {
      return client.call<ConditionGroup>(`/v1/roles/${roleId}/condition-groups`, {
        method: "POST",
        body: data,
      });
    },
    async updateConditionGroup(
      roleId: string,
      groupId: string,
      data: ConditionGroupUpdateData,
    ): Promise<ConditionGroup> {
      return client.call<ConditionGroup>(`/v1/roles/${roleId}/condition-groups/${groupId}`, {
        method: "PATCH",
        body: data,
      });
    },
    async deleteConditionGroup(roleId: string, groupId: string): Promise<void> {
      return client.call<void>(`/v1/roles/${roleId}/condition-groups/${groupId}`, {
        method: "DELETE",
      });
    },

    /**
     * ABAC - Conditions
     */
    async fetchConditions(roleId: string): Promise<AbacCondition[]> {
      return client.call<AbacCondition[]>(`/v1/roles/${roleId}/conditions`);
    },
    async createCondition(
      roleId: string,
      data: AbacConditionCreateData,
    ): Promise<AbacCondition> {
      return client.call<AbacCondition>(`/v1/roles/${roleId}/conditions`, {
        method: "POST",
        body: data,
      });
    },
    async updateCondition(
      roleId: string,
      conditionId: string,
      data: AbacConditionUpdateData,
    ): Promise<AbacCondition> {
      return client.call<AbacCondition>(`/v1/roles/${roleId}/conditions/${conditionId}`, {
        method: "PATCH",
        body: data,
      });
    },
    async deleteCondition(roleId: string, conditionId: string): Promise<void> {
      return client.call<void>(`/v1/roles/${roleId}/conditions/${conditionId}`, {
        method: "DELETE",
      });
    },
  };
}
