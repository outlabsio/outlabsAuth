/**
 * Entity type definitions for the unified entity architecture
 */

export enum EntityClass {
  STRUCTURAL = "STRUCTURAL",
  ACCESS_GROUP = "ACCESS_GROUP"
}

// Keep EntityType enum for predefined suggestions, but entity_type is now a string
export enum EntityType {
  // Structural types
  PLATFORM = "platform",
  ORGANIZATION = "organization",
  DIVISION = "division",
  BRANCH = "branch",
  TEAM = "team",
  
  // Access group types
  FUNCTIONAL_GROUP = "functional_group",
  PERMISSION_GROUP = "permission_group",
  PROJECT_GROUP = "project_group",
  ROLE_GROUP = "role_group",
  ACCESS_GROUP = "access_group"
}

// Type for entity type suggestions from API
export interface EntityTypeSuggestion {
  entity_type: string;
  count: number;
  last_used?: string;
  is_predefined?: boolean;
}

export interface Entity {
  _id: string;
  id: string;
  created_at: string;
  updated_at?: string;
  
  // Identity
  name: string;
  display_name?: string; // API returns this
  slug: string;
  description?: string;
  
  // Classification
  entity_class: EntityClass;
  entity_type: string;  // Now flexible, any string allowed
  
  // Hierarchy
  platform_id: string;
  parent_entity?: Entity | string; // Can be populated or just ID
  parent_entity_id?: string; // The ID when parent_entity is not populated
  
  // Access control
  status: "active" | "inactive" | "archived";
  valid_from?: string;
  valid_until?: string;
  
  // Permissions and configuration
  direct_permissions: string[];
  config?: Record<string, any>; // API returns config, not metadata
  metadata?: Record<string, any>; // Keep for backward compatibility
  allowed_child_classes: EntityClass[];
  allowed_child_types: string[];  // Now flexible array of strings
  max_members?: number;
}

export interface EntityMembership {
  _id: string;
  id: string;
  created_at: string;
  updated_at?: string;
  
  user: User | string;
  entity: Entity | string;
  roles: Role[] | string[];
  
  joined_at: string;
  joined_by?: User | string;
  
  valid_from?: string;
  valid_until?: string;
  status: "active" | "suspended" | "revoked";
}

export interface User {
  id: string;
  email: string;
  profile: {
    first_name: string;
    last_name: string;
    phone?: string;
    avatar_url?: string;
  };
  is_active: boolean;
  is_system_user: boolean;
}

export interface Role {
  _id: string;
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  entity?: Entity | string;
  permissions: string[];
  is_system_role: boolean;
}

// Helper functions
export function getEntityTypeLabel(type: string): string {
  // Convert snake_case to Title Case
  return type
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

// Icon helper functions have been moved to @/lib/entity-icons.tsx
// Import getEntityClassIcon and getEntityTypeIcon from there instead

// Type guards
export function isStructuralEntity(entity: Entity): boolean {
  return entity.entity_class === EntityClass.STRUCTURAL;
}

export function isAccessGroup(entity: Entity): boolean {
  return entity.entity_class === EntityClass.ACCESS_GROUP;
}