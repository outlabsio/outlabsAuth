/**
 * Entity Types
 * For entity hierarchy and context management
 *
 * Matches backend schemas in outlabs_auth/schemas/entity.py
 */

/**
 * Entity class - lowercase to match backend enum
 */
export type EntityClass = "structural" | "access_group";

/**
 * Entity response from backend - matches EntityResponse schema
 */
export interface Entity {
  id: string;
  name: string;
  display_name: string;
  slug: string;
  description?: string;
  entity_class: EntityClass;
  entity_type: string;
  parent_entity_id?: string; // Backend uses parent_entity_id, not parent_id
  status: string; // "active" | "inactive" | "archived"
  valid_from?: string;
  valid_until?: string;
  direct_permissions: string[];
  metadata: Record<string, any>;
  allowed_child_classes: string[];
  allowed_child_types: string[];
  max_members?: number;
}

/**
 * Entity creation request - matches EntityCreateRequest schema
 */
export interface CreateEntityData {
  name: string;
  display_name: string;
  slug: string;
  description?: string;
  entity_class: EntityClass;
  entity_type: string;
  parent_entity_id?: string;
  status?: string;
  valid_from?: string;
  valid_until?: string;
  direct_permissions?: string[];
  metadata?: Record<string, any>;
  allowed_child_classes?: string[];
  allowed_child_types?: string[];
  max_members?: number;
}

/**
 * Entity update request - matches EntityUpdateRequest schema
 */
export interface UpdateEntityData {
  display_name?: string;
  description?: string;
  status?: string;
  valid_from?: string;
  valid_until?: string;
  direct_permissions?: string[];
  metadata?: Record<string, any>;
  allowed_child_classes?: string[];
  allowed_child_types?: string[];
  max_members?: number;
}

/**
 * Entity move request - matches EntityMoveRequest schema
 */
export interface MoveEntityData {
  parent_entity_id?: string;
}

/**
 * Entity context for context switching in UI
 */
export interface EntityContext {
  id: string;
  name: string;
  display_name?: string;
  entity_type: string;
  entity_class: EntityClass;
  is_system?: boolean;
}

/**
 * System context for platform-level admin (superusers)
 */
export const SYSTEM_CONTEXT: EntityContext = {
  id: "system",
  name: "System Administration",
  display_name: "System Administration",
  entity_type: "system",
  entity_class: "structural",
  is_system: true,
};
