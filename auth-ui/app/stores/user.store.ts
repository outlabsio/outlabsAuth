/**
 * User Store (Single User)
 * Manages viewing/editing a SINGLE user
 * Separate from users.store.ts which handles list operations
 */

import { defineStore } from "pinia";
import type { User } from "~/types/auth";
import type { Role, Permission } from "~/types/role";

export interface UserMembership {
  role: Role;
  granted_at: string;
  granted_by?: string;
}

export interface UserPermissionSource {
  permission: Permission;
  source: "role" | "direct";
  source_id?: string; // ID of the role if source is 'role'
  source_name?: string; // Name of the role if source is 'role'
}

// Entity membership response from backend
export interface MembershipResponse {
  id: string;
  entity_id: string;
  user_id: string;
  role_ids: string[];
}

export const useUserStore = defineStore("user", () => {
  const authStore = useAuthStore();

  // State
  const state = reactive({
    // Current user being viewed/edited
    currentUser: null as User | null,

    // User's role memberships
    userRoles: [] as UserMembership[],

    // User's effective permissions (from roles + direct)
    userPermissions: [] as UserPermissionSource[],

    // User's entity memberships (EnterpriseRBAC only)
    userMemberships: [] as MembershipResponse[],

    // Loading states
    isLoadingUser: false,
    isLoadingRoles: false,
    isLoadingPermissions: false,
    isLoadingMemberships: false,

    // Error handling
    error: null as string | null,
  });

  // Getters
  const currentUser = computed(() => state.currentUser);
  const userRoles = computed(() => state.userRoles);
  const userPermissions = computed(() => state.userPermissions);
  const userMemberships = computed(() => state.userMemberships);
  const isLoading = computed(
    () =>
      state.isLoadingUser ||
      state.isLoadingRoles ||
      state.isLoadingPermissions ||
      state.isLoadingMemberships,
  );
  const isLoadingRoles = computed(() => state.isLoadingRoles);
  const isLoadingMemberships = computed(() => state.isLoadingMemberships);
  const error = computed(() => state.error);

  /**
   * Fetch user by ID
   */
  const fetchUser = async (userId: string): Promise<User | null> => {
    try {
      state.isLoadingUser = true;
      state.error = null;

      const user = await authStore.apiCall<User>(`/v1/users/${userId}`);
      state.currentUser = user;
      return user;
    } catch (error: any) {
      state.error = error.message || "Failed to fetch user";
      console.error("[user.store] Failed to fetch user:", error);
      return null;
    } finally {
      state.isLoadingUser = false;
    }
  };

  /**
   * Fetch user's role memberships
   * In SimpleRBAC: global roles assigned to user
   * In EnterpriseRBAC: roles with entity context
   */
  const fetchUserRoles = async (userId: string): Promise<UserMembership[]> => {
    try {
      state.isLoadingRoles = true;
      state.error = null;

      // SimpleRBAC endpoint: /v1/users/:id/roles
      const roles = await authStore.apiCall<Role[]>(
        `/v1/users/${userId}/roles`,
      );

      // Convert to UserMembership format
      state.userRoles = roles.map((role) => ({
        role,
        granted_at: new Date().toISOString(), // TODO: Backend should provide this
      }));

      return state.userRoles;
    } catch (error: any) {
      state.error = error.message || "Failed to fetch user roles";
      console.error("[user.store] Failed to fetch user roles:", error);
      return [];
    } finally {
      state.isLoadingRoles = false;
    }
  };

  /**
   * Fetch user's effective permissions
   * Returns permissions from roles + any directly assigned permissions
   */
  const fetchUserPermissions = async (
    userId: string,
  ): Promise<UserPermissionSource[]> => {
    try {
      state.isLoadingPermissions = true;
      state.error = null;

      // SimpleRBAC endpoint: /v1/users/:id/permissions
      // Backend now returns UserPermissionSource[] with full permission details and source info
      const permissions = await authStore.apiCall<UserPermissionSource[]>(
        `/v1/users/${userId}/permissions`,
      );

      // Store the permissions directly (no mapping needed)
      state.userPermissions = permissions;

      return state.userPermissions;
    } catch (error: any) {
      state.error = error.message || "Failed to fetch user permissions";
      console.error("[user.store] Failed to fetch user permissions:", error);
      return [];
    } finally {
      state.isLoadingPermissions = false;
    }
  };

  /**
   * Assign a role to the user
   * SimpleRBAC: Assigns global role
   * EnterpriseRBAC: Would need entity_id parameter
   */
  const assignRole = async (
    userId: string,
    roleId: string,
  ): Promise<boolean> => {
    try {
      state.error = null;

      await authStore.apiCall(`/v1/users/${userId}/roles`, {
        method: "POST",
        body: {
          role_id: roleId,
        },
      });

      // Refresh user roles
      await fetchUserRoles(userId);

      // Show success toast
      const toast = useToast();
      toast.add({
        title: "Role assigned",
        description: "Role has been assigned to the user successfully",
        color: "success",
      });

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to assign role";
      console.error("[user.store] Failed to assign role:", error);

      const toast = useToast();
      toast.add({
        title: "Error assigning role",
        description: state.error ?? undefined,
        color: "error",
      });

      return false;
    }
  };

  /**
   * Remove a role from the user
   */
  const removeRole = async (
    userId: string,
    roleId: string,
  ): Promise<boolean> => {
    try {
      state.error = null;

      await authStore.apiCall(`/v1/users/${userId}/roles/${roleId}`, {
        method: "DELETE",
      });

      // Refresh user roles
      await fetchUserRoles(userId);

      // Show success toast
      const toast = useToast();
      toast.add({
        title: "Role removed",
        description: "Role has been removed from the user successfully",
        color: "success",
      });

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to remove role";
      console.error("[user.store] Failed to remove role:", error);

      const toast = useToast();
      toast.add({
        title: "Error removing role",
        description: state.error ?? undefined,
        color: "error",
      });

      return false;
    }
  };

  /**
   * Update user basic information
   * Note: This uses the mutation from users.store, but updates local state
   */
  const updateUser = async (
    userId: string,
    data: {
      email?: string;
      first_name?: string;
      last_name?: string;
    },
  ): Promise<boolean> => {
    try {
      state.error = null;

      const updatedUser = await authStore.apiCall<User>(`/v1/users/${userId}`, {
        method: "PATCH",
        body: data,
      });

      state.currentUser = updatedUser;

      // Show success toast
      const toast = useToast();
      toast.add({
        title: "User updated",
        description: "User information has been updated successfully",
        color: "success",
      });

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to update user";
      console.error("[user.store] Failed to update user:", error);

      const toast = useToast();
      toast.add({
        title: "Error updating user",
        description: state.error ?? undefined,
        color: "error",
      });

      return false;
    }
  };

  /**
   * Change user password
   */
  const changePassword = async (
    userId: string,
    currentPassword: string,
    newPassword: string,
  ): Promise<boolean> => {
    try {
      state.error = null;

      const currentUserId = authStore.currentUser?.id;
      const isSelfChange = userId === "me" || userId === currentUserId;

      if (isSelfChange) {
        await authStore.apiCall("/v1/users/me/change-password", {
          method: "POST",
          body: {
            current_password: currentPassword,
            new_password: newPassword,
          },
        });
      } else {
        await authStore.apiCall(`/v1/users/${userId}/password`, {
          method: "PATCH",
          body: {
            new_password: newPassword,
          },
        });
      }

      // Show success toast
      const toast = useToast();
      toast.add({
        title: "Password changed",
        description: "Password has been changed successfully",
        color: "success",
      });

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to change password";
      console.error("[user.store] Failed to change password:", error);

      const toast = useToast();
      toast.add({
        title: "Error changing password",
        description: state.error ?? undefined,
        color: "error",
      });

      return false;
    }
  };

  // ========================
  // Entity Membership Methods (EnterpriseRBAC only)
  // ========================

  /**
   * Fetch user's entity memberships
   * Only available in EnterpriseRBAC mode
   */
  const fetchUserMemberships = async (
    userId: string,
  ): Promise<MembershipResponse[]> => {
    try {
      state.isLoadingMemberships = true;
      state.error = null;

      const memberships = await authStore.apiCall<MembershipResponse[]>(
        `/v1/memberships/user/${userId}`,
      );

      state.userMemberships = memberships;
      return memberships;
    } catch (error: any) {
      state.error = error.message || "Failed to fetch user memberships";
      console.error("[user.store] Failed to fetch user memberships:", error);
      return [];
    } finally {
      state.isLoadingMemberships = false;
    }
  };

  /**
   * Add user to an entity
   * Creates a membership with empty roles (roles assigned separately)
   */
  const addToEntity = async (
    userId: string,
    entityId: string,
  ): Promise<boolean> => {
    try {
      state.error = null;

      await authStore.apiCall("/v1/memberships/", {
        method: "POST",
        body: {
          user_id: userId,
          entity_id: entityId,
          role_ids: [],
        },
      });

      // Refresh memberships
      await fetchUserMemberships(userId);

      const toast = useToast();
      toast.add({
        title: "Added to entity",
        description: "User has been added to the entity successfully",
        color: "success",
      });

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to add user to entity";
      console.error("[user.store] Failed to add user to entity:", error);

      const toast = useToast();
      toast.add({
        title: "Error adding to entity",
        description: state.error ?? undefined,
        color: "error",
      });

      return false;
    }
  };

  /**
   * Remove user from an entity
   */
  const removeFromEntity = async (
    userId: string,
    entityId: string,
  ): Promise<boolean> => {
    try {
      state.error = null;

      await authStore.apiCall(`/v1/memberships/${entityId}/${userId}`, {
        method: "DELETE",
      });

      // Refresh memberships
      await fetchUserMemberships(userId);

      const toast = useToast();
      toast.add({
        title: "Removed from entity",
        description: "User has been removed from the entity successfully",
        color: "success",
      });

      return true;
    } catch (error: any) {
      state.error = error.message || "Failed to remove user from entity";
      console.error("[user.store] Failed to remove user from entity:", error);

      const toast = useToast();
      toast.add({
        title: "Error removing from entity",
        description: state.error ?? undefined,
        color: "error",
      });

      return false;
    }
  };

  /**
   * Clear current user and reset state
   */
  const clearUser = (): void => {
    state.currentUser = null;
    state.userRoles = [];
    state.userPermissions = [];
    state.userMemberships = [];
    state.error = null;
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
    currentUser,
    userRoles,
    userPermissions,
    userMemberships,
    isLoading,
    isLoadingRoles,
    isLoadingMemberships,
    error,

    // Actions
    fetchUser,
    fetchUserRoles,
    fetchUserPermissions,
    assignRole,
    removeRole,
    updateUser,
    changePassword,
    clearUser,
    clearError,

    // Entity membership actions (EnterpriseRBAC)
    fetchUserMemberships,
    addToEntity,
    removeFromEntity,
  };
});
