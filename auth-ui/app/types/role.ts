/**
 * Role Types
 * Based on OutlabsAuth library role system - matches backend RoleResponse schema
 */

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
}

export interface CreateRoleData {
  name: string;
  display_name: string;
  description?: string;
  permissions: string[];
  entity_type_permissions?: Record<string, string[]>;
  is_global?: boolean;
  assignable_at_types?: string[];
}

export interface UpdateRoleData {
  display_name?: string;
  description?: string;
  permissions?: string[];
  entity_type_permissions?: Record<string, string[]>;
  is_global?: boolean;
  assignable_at_types?: string[];
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
