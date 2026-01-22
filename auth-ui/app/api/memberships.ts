/**
 * Memberships API
 * API functions for entity membership management
 */

import { createAPIClient } from "./client";
import type {
  Membership,
  EntityMember,
  CreateMembershipData,
  UpdateMembershipData,
} from "~/types/membership";

/**
 * Create memberships API client
 */
export function createMembershipsAPI() {
  const api = createAPIClient();

  return {
    /**
     * Fetch members of an entity (basic response)
     */
    fetchEntityMembers: async (
      entityId: string,
      params: { page?: number; limit?: number } = {}
    ): Promise<Membership[]> => {
      const qs = api.buildQueryString({
        page: params.page || 1,
        limit: params.limit || 50,
      });
      return api.call<Membership[]>(`/v1/memberships/entity/${entityId}${qs}`);
    },

    /**
     * Fetch members of an entity with user details
     */
    fetchEntityMembersWithDetails: async (
      entityId: string,
      params: { page?: number; limit?: number } = {}
    ): Promise<EntityMember[]> => {
      const qs = api.buildQueryString({
        page: params.page || 1,
        limit: params.limit || 50,
      });
      return api.call<EntityMember[]>(
        `/v1/memberships/entity/${entityId}/details${qs}`
      );
    },

    /**
     * Fetch memberships for a user
     */
    fetchUserMemberships: async (
      userId: string,
      params: { page?: number; limit?: number } = {}
    ): Promise<Membership[]> => {
      const qs = api.buildQueryString({
        page: params.page || 1,
        limit: params.limit || 50,
      });
      return api.call<Membership[]>(`/v1/memberships/user/${userId}${qs}`);
    },

    /**
     * Fetch current user's memberships
     */
    fetchMyMemberships: async (): Promise<Membership[]> => {
      return api.call<Membership[]>("/v1/memberships/me");
    },

    /**
     * Add member to entity
     */
    addMember: async (data: CreateMembershipData): Promise<Membership> => {
      return api.call<Membership>("/v1/memberships/", {
        method: "POST",
        body: JSON.stringify(data),
      });
    },

    /**
     * Update member roles in entity
     */
    updateMemberRoles: async (
      entityId: string,
      userId: string,
      data: UpdateMembershipData
    ): Promise<Membership> => {
      return api.call<Membership>(`/v1/memberships/${entityId}/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      });
    },

    /**
     * Remove member from entity
     */
    removeMember: async (entityId: string, userId: string): Promise<void> => {
      await api.call<void>(`/v1/memberships/${entityId}/${userId}`, {
        method: "DELETE",
      });
    },
  };
}
