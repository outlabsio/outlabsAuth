/**
 * Configuration API
 * API functions for system configuration management
 */

import { createAPIClient } from './client'

/**
 * Default child types organized by entity class
 */
export interface DefaultChildTypes {
  structural: string[]
  access_group: string[]
}

/**
 * Entity type configuration response
 */
export interface EntityTypeConfig {
  allowed_root_types: string[]
  default_child_types: DefaultChildTypes
  updated_at?: string
}

/**
 * Entity type configuration update request
 */
export interface EntityTypeConfigUpdateRequest {
  allowed_root_types?: string[]
  default_child_types?: DefaultChildTypes
}

export function createConfigAPI() {
  const client = createAPIClient()

  return {
    /**
     * Fetch entity type configuration
     * This endpoint is public (no auth required)
     */
    async fetchEntityTypeConfig(): Promise<EntityTypeConfig> {
      return client.call<EntityTypeConfig>('/v1/config/entity-types')
    },

    /**
     * Update entity type configuration
     * Requires superuser permissions
     */
    async updateEntityTypeConfig(data: EntityTypeConfigUpdateRequest): Promise<EntityTypeConfig> {
      return client.call<EntityTypeConfig>('/v1/config/entity-types', {
        method: 'PUT',
        body: data
      })
    }
  }
}
