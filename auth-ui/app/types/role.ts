/**
 * Role Types
 * Based on OutlabsAuth library role system - matches backend RoleResponse schema
 */

/**
 * Role scope enum - controls where permissions apply and auto-assignment scope.
 */
export type RoleScope = "entity_only" | "hierarchy";

/**
 * Role summary for embedding in other responses (e.g., membership details).
 */
export interface RoleSummary {
  id: string;
  name: string;
  display_name: string;
}

export interface Role {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  permissions: string[];
  entity_type_permissions?: Record<string, string[]>;
  is_system_role: boolean;
  is_global: boolean;
  assignable_at_types: string[];
  // Root entity scoping (EnterpriseRBAC)
  root_entity_id?: string;
  root_entity_name?: string;
  // Entity-local role fields (DD-053)
  scope_entity_id?: string;
  scope_entity_name?: string;
  scope: RoleScope;
  is_auto_assigned: boolean;
}

export interface CreateRoleData {
  name: string;
  display_name: string;
  description?: string;
  permissions: string[];
  entity_type_permissions?: Record<string, string[]>;
  is_global?: boolean;
  assignable_at_types?: string[];
  // Root entity scoping (EnterpriseRBAC)
  root_entity_id?: string;
  // Entity-local role fields (DD-053)
  scope_entity_id?: string;
  scope?: RoleScope;
  is_auto_assigned?: boolean;
}

export interface UpdateRoleData {
  display_name?: string;
  description?: string;
  permissions?: string[];
  entity_type_permissions?: Record<string, string[]>;
  is_global?: boolean;
  assignable_at_types?: string[];
  // Entity-local role fields (DD-053)
  scope?: RoleScope;
  is_auto_assigned?: boolean;
}

export interface Permission {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  resource: string;
  action: string;
  scope?: string;
  is_system: boolean;
  is_active: boolean;
  tags?: string[];
  metadata?: Record<string, any>;
}
