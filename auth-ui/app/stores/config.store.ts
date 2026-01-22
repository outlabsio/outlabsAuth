/**
 * Configuration Store
 * Manages system-level configuration including entity types
 */

import { defineStore } from 'pinia'
import type { EntityTypeConfig, DefaultChildTypes, EntityTypeConfigUpdateRequest } from '~/api/config'
import { createConfigAPI } from '~/api/config'

export const useConfigStore = defineStore('config', () => {
  const authStore = useAuthStore()

  // State
  const state = reactive({
    entityTypeConfig: null as EntityTypeConfig | null,
    isLoading: false,
    error: null as string | null
  })

  // API client
  const api = createConfigAPI()

  // Getters
  const entityTypeConfig = computed(() => state.entityTypeConfig)
  const isLoading = computed(() => state.isLoading)
  const error = computed(() => state.error)

  /**
   * Get allowed root entity types
   * Returns defaults if config not loaded
   */
  const allowedRootTypes = computed(() => {
    return state.entityTypeConfig?.allowed_root_types ?? ['organization']
  })

  /**
   * Get default child types for structural entities
   */
  const defaultStructuralChildTypes = computed(() => {
    return state.entityTypeConfig?.default_child_types?.structural ?? ['department', 'team', 'branch']
  })

  /**
   * Get default child types for access group entities
   */
  const defaultAccessGroupChildTypes = computed(() => {
    return state.entityTypeConfig?.default_child_types?.access_group ?? ['permission_group', 'admin_group']
  })

  /**
   * Get all default child types combined
   */
  const allDefaultChildTypes = computed(() => {
    return [
      ...defaultStructuralChildTypes.value,
      ...defaultAccessGroupChildTypes.value
    ]
  })

  /**
   * Fetch entity type configuration from backend
   */
  const fetchEntityTypeConfig = async (): Promise<void> => {
    try {
      state.isLoading = true
      state.error = null
      state.entityTypeConfig = await api.fetchEntityTypeConfig()
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch entity type configuration'
      console.error('Failed to fetch entity type config:', error)
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Update entity type configuration
   * Requires superuser permissions
   */
  const updateEntityTypeConfig = async (data: EntityTypeConfigUpdateRequest): Promise<boolean> => {
    try {
      state.isLoading = true
      state.error = null
      state.entityTypeConfig = await api.updateEntityTypeConfig(data)
      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to update entity type configuration'
      console.error('Failed to update entity type config:', error)
      return false
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Set allowed root types
   */
  const setAllowedRootTypes = async (types: string[]): Promise<boolean> => {
    return updateEntityTypeConfig({ allowed_root_types: types })
  }

  /**
   * Set default child types
   */
  const setDefaultChildTypes = async (childTypes: DefaultChildTypes): Promise<boolean> => {
    return updateEntityTypeConfig({ default_child_types: childTypes })
  }

  /**
   * Add a new allowed root type
   */
  const addAllowedRootType = async (type: string): Promise<boolean> => {
    const currentTypes = [...allowedRootTypes.value]
    if (!currentTypes.includes(type)) {
      currentTypes.push(type)
      return setAllowedRootTypes(currentTypes)
    }
    return true
  }

  /**
   * Remove an allowed root type
   */
  const removeAllowedRootType = async (type: string): Promise<boolean> => {
    const currentTypes = allowedRootTypes.value.filter(t => t !== type)
    if (currentTypes.length === 0) {
      state.error = 'At least one root entity type must be configured'
      return false
    }
    return setAllowedRootTypes(currentTypes)
  }

  /**
   * Check if a type is an allowed root type
   */
  const isAllowedRootType = (type: string): boolean => {
    return allowedRootTypes.value.includes(type)
  }

  /**
   * Get available child types for an entity
   * If the entity has custom allowed_child_types, use those
   * Otherwise, fall back to system defaults
   */
  const getAvailableChildTypes = (entityAllowedChildTypes?: string[]): string[] => {
    if (entityAllowedChildTypes && entityAllowedChildTypes.length > 0) {
      return entityAllowedChildTypes
    }
    return allDefaultChildTypes.value
  }

  /**
   * Clear error
   */
  const clearError = (): void => {
    state.error = null
  }

  /**
   * Initialize config store
   * Fetches configuration on app startup
   */
  const initialize = async (): Promise<void> => {
    await fetchEntityTypeConfig()
  }

  return {
    // State
    state: readonly(state),

    // Getters
    entityTypeConfig,
    isLoading,
    error,
    allowedRootTypes,
    defaultStructuralChildTypes,
    defaultAccessGroupChildTypes,
    allDefaultChildTypes,

    // Actions
    fetchEntityTypeConfig,
    updateEntityTypeConfig,
    setAllowedRootTypes,
    setDefaultChildTypes,
    addAllowedRootType,
    removeAllowedRootType,
    isAllowedRootType,
    getAvailableChildTypes,
    clearError,
    initialize
  }
})
