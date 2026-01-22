/**
 * Membership Types
 * Based on OutlabsAuth library membership system
 */

import type { RoleSummary } from "./role";

/**
 * Basic membership response (minimal fields).
 */
export interface Membership {
  id: string;
  entity_id: string;
  user_id: string;
  role_ids: string[];
}

/**
 * Rich entity member response with user details and roles.
 * Used for displaying entity members list.
 */
export interface EntityMember {
  id: string; // membership ID
  user_id: string;
  user_email: string;
  user_first_name?: string;
  user_last_name?: string;
  user_status: string;
  roles: RoleSummary[];
  status: string; // membership status
  joined_at: string; // ISO date string
}

/**
 * Create membership request.
 */
export interface CreateMembershipData {
  entity_id: string;
  user_id: string;
  role_ids: string[];
}

/**
 * Update membership request (update roles).
 */
export interface UpdateMembershipData {
  role_ids: string[];
}
