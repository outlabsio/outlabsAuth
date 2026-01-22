/**
 * Roles Store
 * Manages role CRUD operations and permission assignments
 */

import { defineStore } from "pinia";
import type { Role, CreateRoleData, UpdateRoleData } from "~/types/role";
import type { PaginationParams, PaginatedResponse } from "~/types/api";

export interface RoleFilters {
  search?: string;
  is_global?: boolean;
  entity_id?: string;
  entity_type?: string;
  for_entity_id?: string; // Get roles available for assignment at this entity
}

export const useRolesStore = defineStore("roles", () => {
  const authStore = useAuthStore();

  // State
  const state = reactive({
    roles: [] as Role[],
    selectedRole: null as Role | null,
    isLoading: false,
    error: null as string | null,
    pagination: {
      total: 0,
      page: 1,
      limit: 20,
      pages: 0,
    },
  });

  // Getters
  const roles = computed(() => state.roles);
  const selectedRole = computed(() => state.selectedRole);
  const isLoading = computed(() => state.isLoading);
  const error = computed(() => state.error);
  const pagination = computed(() => state.pagination);

  // Get global roles
  const globalRoles = computed(() => state.roles.filter((r) => r.is_global));

  // Get context-specific roles
  const contextRoles = computed(() => state.roles.filter((r) => !r.is_global));

  /**
   * Fetch roles with pagination, search, and filters
   */
  const fetchRoles = async (
    filters: RoleFilters = {},
    params: PaginationParams = {},
  ): Promise<void> => {
    try {
      state.isLoading = true;
      state.error = null;

      const queryParams = new URLSearchParams();
      if (filters.search) queryParams.append("search", filters.search);
      if (filters.is_global !== undefined)
        queryParams.append("is_global", String(filters.is_global));
      if (filters.entity_id) queryParams.append("entity_id", filters.entity_id);
      if (filters.entity_type)
        queryParams.append("entity_type", filters.entity_type);
      if (params.page) queryParams.append("page", String(params.page));
      if (params.limit) queryParams.append("limit", String(params.limit));
      if (params.sort_by) queryParams.append("sort_by", params.sort_by);
      if (params.sort_order)
        queryParams.append("sort_order", params.sort_order);

      const response = await authStore.apiCall<PaginatedResponse<Role>>(
        `/v1/roles/?${queryParams.toString()}`,
      );

      state.roles = response.items;
      state.pagination = {
        total: response.total,
        page: response.page,
        limit: response.limit,
        pages: response.pages,
      };
    } catch (error: any) {
      state.error = error.message || "Failed to fetch roles";
      console.error("Failed to fetch roles:", error);
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Fetch single role by ID
   */
  const fetchRole = async (roleId: string): Promise<Role | null> => {
    try {
      state.isLoading = true;
      state.error = null;

      const role = await authStore.apiCall<Role>(`/v1/roles/${roleId}`);
      state.selectedRole = role;
      return role;
    } catch (error: any) {
      state.error = error.message || "Failed to fetch role";
      console.error("Failed to fetch role:", error);
      return null;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Create new role
   */
  const createRole = async (data: CreateRoleData): Promise<Role | null> => {
    try {
      state.isLoading = true;
      state.error = null;

      const role = await authStore.apiCall<Role>("/v1/roles", {
        method: "POST",
        body: JSON.stringify(data),
      });

      return role;
    } catch (error: any) {
      state.error = error.message || "Failed to create role";
      console.error("Failed to create role:", error);
      throw error;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Update role
   */
  const updateRole = async (
    roleId: string,
    data: UpdateRoleData,
  ): Promise<Role | null> => {
    try {
      state.isLoading = true;
      state.error = null;

      const role = await authStore.apiCall<Role>(`/v1/roles/${roleId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });

      state.selectedRole = role;
      return role;
    } catch (error: any) {
      state.error = error.message || "Failed to update role";
      console.error("Failed to update role:", error);
      throw error;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Delete role
   */
  const deleteRole = async (roleId: string): Promise<boolean> => {
    try {
      state.isLoading = true;
      state.error = null;

      await authStore.apiCall(`/v1/roles/${roleId}`, {
        method: "DELETE",
      });

      // Remove from local state
      const stateIndex = state.roles.findIndex((r) => r.id === roleId);
      if (stateIndex !== -1) {
        state.roles.splice(stateIndex, 1);
      }

      if (state.selectedRole?.id === roleId) {
        state.selectedRole = null;
      }

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to delete role";
      console.error("Failed to delete role:", error);
      return false;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Assign permissions to role
   */
  const assignPermissions = async (
    roleId: string,
    permissions: string[],
  ): Promise<boolean> => {
    try {
      state.isLoading = true;
      state.error = null;

      await authStore.apiCall(`/v1/roles/${roleId}/permissions`, {
        method: "POST",
        body: JSON.stringify({ permissions }),
      });

      // Refresh role data
      await fetchRole(roleId);
      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to assign permissions";
      console.error("Failed to assign permissions:", error);
      return false;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Remove permissions from role
   */
  const removePermissions = async (
    roleId: string,
    permissions: string[],
  ): Promise<boolean> => {
    try {
      state.isLoading = true;
      state.error = null;

      await authStore.apiCall(`/v1/roles/${roleId}/permissions`, {
        method: "DELETE",
        body: JSON.stringify({ permissions }),
      });

      // Refresh role data
      await fetchRole(roleId);
      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to remove permissions";
      console.error("Failed to remove permissions:", error);
      return false;
    } finally {
      state.isLoading = false;
    }
  };

  /**
   * Clear selected role
   */
  const clearSelectedRole = (): void => {
    state.selectedRole = null;
  };

  /**
   * Clear error
   */
  const clearError = (): void => {
    state.error = null;
  };

  return {
    // State
    state: readonly(state),

    // Getters
    roles,
    selectedRole,
    isLoading,
    error,
    pagination,
    globalRoles,
    contextRoles,

    // Actions
    fetchRoles,
    fetchRole,
    createRole,
    updateRole,
    deleteRole,
    assignPermissions,
    removePermissions,
    clearSelectedRole,
    clearError,
  };
});
