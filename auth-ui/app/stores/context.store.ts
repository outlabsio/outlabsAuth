/**
 * Context Store
 * Manages entity context switching for hierarchical permissions
 * Based on proven patterns from archived frontend
 */

import { defineStore } from 'pinia'
import type { EntityContext } from '~/types/entity'
import { SYSTEM_CONTEXT } from '~/types/entity'

const SELECTED_ENTITY_KEY = 'outlabs_auth_selected_entity'

export const useContextStore = defineStore('context', () => {
  const authStore = useAuthStore()

  // State
  const state = reactive({
    selectedEntity: null as EntityContext | null,
    availableEntities: [] as EntityContext[],
    isLoading: false
  })

  // Getters
  const selectedEntity = computed(() => state.selectedEntity)
  const availableEntities = computed(() => state.availableEntities)
  const isSystemContext = computed(() =>
    state.selectedEntity?.is_system === true ||
    state.selectedEntity?.id === 'system'
  )

  /**
   * Get context headers for API requests
   * Used by auth store's apiCall method
   */
  const getContextHeaders = (): Record<string, string> => {
    if (!state.selectedEntity || state.selectedEntity.is_system) {
      return {}
    }

    return {
      'X-Entity-Context': state.selectedEntity.id
    }
  }

  /**
   * Initialize context from localStorage
   * Called after auth initialization
   */
  const initialize = async (): Promise<void> => {
    if (!authStore.isAuthenticated) {
      return
    }

    // Skip on server-side
    if (import.meta.server) {
      return
    }

    try {
      // Load available entities
      await fetchAvailableEntities()

      // Try to restore selected entity from localStorage
      const storedEntity = localStorage.getItem(SELECTED_ENTITY_KEY)
      if (storedEntity) {
        try {
          const entity = JSON.parse(storedEntity)

          // Verify entity still exists in available entities
          const entityExists = state.availableEntities.some(e => e.id === entity.id)
          if (entityExists) {
            state.selectedEntity = entity
            return
          }
        } catch (error) {
          console.error('Failed to parse stored entity:', error)
        }
      }

      // Default to first available entity or system context
      if (state.availableEntities.length > 0) {
        state.selectedEntity = state.availableEntities[0] || null
      } else {
        // If user is superuser and no entities, use system context
        if (authStore.currentUser?.is_superuser) {
          state.selectedEntity = SYSTEM_CONTEXT
        } else {
          state.selectedEntity = null
        }
      }

      // Persist selection
      if (state.selectedEntity) {
        localStorage.setItem(SELECTED_ENTITY_KEY, JSON.stringify(state.selectedEntity))
      }
    } catch (error) {
      console.error('Failed to initialize context:', error)
    }
  }

  /**
   * Fetch available entities for current user
   * Gets entities where user has any membership
   */
  const fetchAvailableEntities = async (): Promise<void> => {
    try {
      state.isLoading = true

      // Get user's memberships to determine available entities
      const memberships = await authStore.apiCall<any>('/v1/memberships/me')

      // Handle SimpleRBAC (returns array) vs EnterpriseRBAC (returns object with items)
      const membershipList = Array.isArray(memberships) ? memberships : (memberships?.items || [])

      // Extract unique entities from memberships
      const entities: EntityContext[] = membershipList.map((m: any) => ({
        id: m.entity.id,
        name: m.entity.name,
        entity_type: m.entity.entity_type,
        entity_class: m.entity.entity_class,
        is_system: false
      }))

      // Add system context if user is superuser
      if (authStore.currentUser?.is_superuser) {
        entities.unshift(SYSTEM_CONTEXT)
      }

      state.availableEntities = entities
    } catch (error) {
      console.error('Failed to fetch available entities:', error)

      // If user is superuser, at least give them system context
      if (authStore.currentUser?.is_superuser) {
        state.availableEntities = [SYSTEM_CONTEXT]
      } else {
        state.availableEntities = []
      }
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Switch to a different entity context
   */
  const switchContext = (entity: EntityContext): void => {
    state.selectedEntity = entity
    if (import.meta.client) {
      localStorage.setItem(SELECTED_ENTITY_KEY, JSON.stringify(entity))
    }
  }

  /**
   * Switch to system context (platform admin)
   * Only available for superusers
   */
  const switchToSystemContext = (): void => {
    if (!authStore.currentUser?.is_superuser) {
      console.warn('Only superusers can access system context')
      return
    }

    switchContext(SYSTEM_CONTEXT)
  }

  /**
   * Clear context (used on logout)
   */
  const clearContext = (): void => {
    state.selectedEntity = null
    state.availableEntities = []
    if (import.meta.client) {
      localStorage.removeItem(SELECTED_ENTITY_KEY)
    }
  }

  /**
   * Refresh available entities
   * Call this after creating/deleting entities or memberships
   */
  const refresh = async (): Promise<void> => {
    await fetchAvailableEntities()

    // Verify current selection is still valid
    if (state.selectedEntity && !state.selectedEntity.is_system) {
      const stillExists = state.availableEntities.some(
        e => e.id === state.selectedEntity?.id
      )

      if (!stillExists) {
        // Current entity no longer available, switch to first available
        const firstEntity = state.availableEntities[0]
        if (firstEntity) {
          switchContext(firstEntity)
        } else {
          state.selectedEntity = null
          localStorage.removeItem(SELECTED_ENTITY_KEY)
        }
      }
    }
  }

  return {
    // State (do not use readonly - prevents Pinia mutations)
    state,

    // Getters
    selectedEntity,
    availableEntities,
    isSystemContext,

    // Actions
    initialize,
    getContextHeaders,
    fetchAvailableEntities,
    switchContext,
    switchToSystemContext,
    clearContext,
    refresh
  }
})
