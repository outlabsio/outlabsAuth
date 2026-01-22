/**
 * Memberships Queries
 * Pinia Colada queries and mutations for membership management
 */

import { defineQueryOptions, useMutation, useQueryCache } from "@pinia/colada";
import { createMembershipsAPI } from "~/api/memberships";
import type {
  CreateMembershipData,
  UpdateMembershipData,
} from "~/types/membership";

/**
 * Query Keys for memberships
 */
export const MEMBERSHIP_KEYS = {
  all: ["memberships"] as const,
  entityMembers: () => [...MEMBERSHIP_KEYS.all, "entity"] as const,
  entityMember: (entityId: string) =>
    [...MEMBERSHIP_KEYS.entityMembers(), entityId] as const,
  entityMembersWithDetails: (entityId: string) =>
    [...MEMBERSHIP_KEYS.entityMembers(), entityId, "details"] as const,
  userMemberships: () => [...MEMBERSHIP_KEYS.all, "user"] as const,
  userMembership: (userId: string) =>
    [...MEMBERSHIP_KEYS.userMemberships(), userId] as const,
  myMemberships: () => [...MEMBERSHIP_KEYS.all, "me"] as const,
};

/**
 * Memberships Query Options
 */
export const membershipsQueries = {
  /**
   * Query for entity members (basic)
   */
  entityMembers: (
    entityId: string,
    params: { page?: number; limit?: number } = {}
  ) =>
    defineQueryOptions({
      key: MEMBERSHIP_KEYS.entityMember(entityId),
      query: async () => {
        const api = createMembershipsAPI();
        return api.fetchEntityMembers(entityId, params);
      },
      staleTime: 10000,
    }),

  /**
   * Query for entity members with user details
   */
  entityMembersWithDetails: (
    entityId: string,
    params: { page?: number; limit?: number } = {}
  ) =>
    defineQueryOptions({
      key: MEMBERSHIP_KEYS.entityMembersWithDetails(entityId),
      query: async () => {
        const api = createMembershipsAPI();
        return api.fetchEntityMembersWithDetails(entityId, params);
      },
      staleTime: 10000,
    }),

  /**
   * Query for user memberships
   */
  userMemberships: (
    userId: string,
    params: { page?: number; limit?: number } = {}
  ) =>
    defineQueryOptions({
      key: MEMBERSHIP_KEYS.userMembership(userId),
      query: async () => {
        const api = createMembershipsAPI();
        return api.fetchUserMemberships(userId, params);
      },
      staleTime: 10000,
    }),

  /**
   * Query for current user's memberships
   */
  myMemberships: () =>
    defineQueryOptions({
      key: MEMBERSHIP_KEYS.myMemberships(),
      query: async () => {
        const api = createMembershipsAPI();
        return api.fetchMyMemberships();
      },
      staleTime: 30000,
    }),
};

/**
 * Add Member Mutation
 */
export function useAddMemberMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async (data: CreateMembershipData) => {
      const api = createMembershipsAPI();
      return api.addMember(data);
    },
    onSuccess: (_data, variables) => {
      // Invalidate entity members queries
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.entityMember(variables.entity_id),
      });
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.entityMembersWithDetails(variables.entity_id),
      });
      // Invalidate user memberships
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.userMembership(variables.user_id),
      });

      toast.add({
        title: "Member added",
        description: "The member has been added successfully",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error adding member",
        description: error.message || "Failed to add member",
        color: "error",
      });
    },
  });
}

/**
 * Update Member Roles Mutation
 */
export function useUpdateMemberRolesMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      entityId,
      userId,
      data,
    }: {
      entityId: string;
      userId: string;
      data: UpdateMembershipData;
    }) => {
      const api = createMembershipsAPI();
      return api.updateMemberRoles(entityId, userId, data);
    },
    onSuccess: (_data, { entityId, userId }) => {
      // Invalidate entity members queries
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.entityMember(entityId),
      });
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.entityMembersWithDetails(entityId),
      });
      // Invalidate user memberships
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.userMembership(userId),
      });

      toast.add({
        title: "Member updated",
        description: "Member roles have been updated successfully",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error updating member",
        description: error.message || "Failed to update member roles",
        color: "error",
      });
    },
  });
}

/**
 * Remove Member Mutation
 */
export function useRemoveMemberMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      entityId,
      userId,
    }: {
      entityId: string;
      userId: string;
    }) => {
      const api = createMembershipsAPI();
      await api.removeMember(entityId, userId);
      return { entityId, userId };
    },
    onSuccess: ({ entityId, userId }) => {
      // Invalidate entity members queries
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.entityMember(entityId),
      });
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.entityMembersWithDetails(entityId),
      });
      // Invalidate user memberships
      queryCache.invalidateQueries({
        key: MEMBERSHIP_KEYS.userMembership(userId),
      });

      toast.add({
        title: "Member removed",
        description: "The member has been removed successfully",
        color: "success",
      });
    },
    onError: (error: any) => {
      toast.add({
        title: "Error removing member",
        description: error.message || "Failed to remove member",
        color: "error",
      });
    },
  });
}
