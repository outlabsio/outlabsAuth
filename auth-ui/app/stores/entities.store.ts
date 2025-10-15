/**
 * Entities Store
 * Manages entity hierarchy, CRUD operations, and tree queries
 */

import { defineStore } from 'pinia'
import type { Entity, EntityClass } from '~/types/entity'
import type { PaginationParams, PaginatedResponse } from '~/types/api'
import { USE_MOCK_DATA, mockDelay, logMockCall, mockId } from '~/utils/mock'
import { mockEntities, getMockEntityHierarchy } from '~/utils/mockData'

export interface EntityFilters {
  search?: string
  entity_class?: EntityClass
  entity_type?: string
  parent_id?: string
  root_only?: boolean
}

export interface CreateEntityData {
  name: string
  entity_type: string
  entity_class: EntityClass
  parent_id?: string
  description?: string
  metadata?: Record<string, any>
}

export interface UpdateEntityData {
  name?: string
  entity_type?: string
  description?: string
  metadata?: Record<string, any>
}

export interface EntityTreeNode extends Entity {
  children: EntityTreeNode[]
  depth: number
}

export interface EntityHierarchy {
  path: Entity[]
  descendants: Entity[]
}

export const useEntitiesStore = defineStore('entities', () => {
  const authStore = useAuthStore()

  // State
  const state = reactive({
    entities: [] as Entity[],
    selectedEntity: null as Entity | null,
    entityTree: [] as EntityTreeNode[],
    isLoading: false,
    error: null as string | null,
    pagination: {
      total: 0,
      page: 1,
      limit: 50,
      pages: 0
    }
  })

  // Mock entities storage (in-memory for mock mode)
  const mockEntitiesData = ref<Entity[]>([...mockEntities])

  // Getters
  const entities = computed(() => state.entities)
  const selectedEntity = computed(() => state.selectedEntity)
  const entityTree = computed(() => state.entityTree)
  const isLoading = computed(() => state.isLoading)
  const error = computed(() => state.error)
  const pagination = computed(() => state.pagination)

  // Get root entities (no parent)
  const rootEntities = computed(() => state.entities.filter(e => !e.parent_id))

  // Get STRUCTURAL entities
  const structuralEntities = computed(() =>
    state.entities.filter(e => e.entity_class === 'STRUCTURAL')
  )

  // Get ACCESS_GROUP entities
  const accessGroupEntities = computed(() =>
    state.entities.filter(e => e.entity_class === 'ACCESS_GROUP')
  )

  /**
   * Build tree structure from flat entity list
   */
  const buildTree = (entities: Entity[], parentId?: string, depth = 0): EntityTreeNode[] => {
    return entities
      .filter(e => e.parent_id === parentId)
      .map(entity => ({
        ...entity,
        depth,
        children: buildTree(entities, entity.id, depth + 1)
      }))
  }

  /**
   * Fetch entities with pagination, search, and filters
   */
  const fetchEntities = async (
    filters: EntityFilters = {},
    params: PaginationParams = {}
  ): Promise<void> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('GET', '/v1/entities', { filters, params })
        await mockDelay()

        // Apply filters
        let filtered = [...mockEntitiesData.value]

        // Search filter (name, description)
        if (filters.search) {
          const search = filters.search.toLowerCase()
          filtered = filtered.filter(
            entity =>
              entity.name.toLowerCase().includes(search) ||
              entity.description?.toLowerCase().includes(search)
          )
        }

        // Entity class filter
        if (filters.entity_class) {
          filtered = filtered.filter(e => e.entity_class === filters.entity_class)
        }

        // Entity type filter
        if (filters.entity_type) {
          filtered = filtered.filter(e => e.entity_type === filters.entity_type)
        }

        // Parent filter
        if (filters.parent_id !== undefined) {
          if (filters.parent_id === null || filters.parent_id === '') {
            filtered = filtered.filter(e => !e.parent_id)
          } else {
            filtered = filtered.filter(e => e.parent_id === filters.parent_id)
          }
        }

        // Root only filter
        if (filters.root_only) {
          filtered = filtered.filter(e => !e.parent_id)
        }

        // Sorting
        const sortBy = params.sort_by || 'name'
        const sortOrder = params.sort_order || 'asc'
        filtered.sort((a: any, b: any) => {
          const aVal = a[sortBy]
          const bVal = b[sortBy]
          if (sortOrder === 'asc') {
            return aVal > bVal ? 1 : -1
          } else {
            return aVal < bVal ? 1 : -1
          }
        })

        // Pagination
        const page = params.page || 1
        const limit = params.limit || 50
        const total = filtered.length
        const pages = Math.ceil(total / limit)
        const startIndex = (page - 1) * limit
        const endIndex = startIndex + limit

        state.entities = filtered.slice(startIndex, endIndex)
        state.pagination = {
          total,
          page,
          limit,
          pages
        }

        // Build tree structure
        state.entityTree = buildTree(filtered)
        return
      }

      // Real API call
      const queryParams = new URLSearchParams()
      if (filters.search) queryParams.append('search', filters.search)
      if (filters.entity_class) queryParams.append('entity_class', filters.entity_class)
      if (filters.entity_type) queryParams.append('entity_type', filters.entity_type)
      if (filters.parent_id !== undefined) queryParams.append('parent_id', filters.parent_id)
      if (filters.root_only) queryParams.append('root_only', 'true')
      if (params.page) queryParams.append('page', String(params.page))
      if (params.limit) queryParams.append('limit', String(params.limit))
      if (params.sort_by) queryParams.append('sort_by', params.sort_by)
      if (params.sort_order) queryParams.append('sort_order', params.sort_order)

      const response = await authStore.apiCall<PaginatedResponse<Entity>>(
        `/v1/entities?${queryParams.toString()}`
      )

      state.entities = response.items
      state.pagination = {
        total: response.total,
        page: response.page,
        limit: response.limit,
        pages: response.pages
      }

      // Build tree structure
      state.entityTree = buildTree(response.items)
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch entities'
      console.error('Failed to fetch entities:', error)
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Fetch single entity by ID
   */
  const fetchEntity = async (entityId: string): Promise<Entity | null> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('GET', `/v1/entities/${entityId}`)
        await mockDelay()

        const entity = mockEntitiesData.value.find(e => e.id === entityId)
        if (!entity) {
          throw new Error('Entity not found')
        }

        state.selectedEntity = entity
        return entity
      }

      // Real API call
      const entity = await authStore.apiCall<Entity>(`/v1/entities/${entityId}`)
      state.selectedEntity = entity
      return entity
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch entity'
      console.error('Failed to fetch entity:', error)
      return null
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Get entity hierarchy (path and descendants)
   */
  const getEntityHierarchy = async (entityId: string): Promise<EntityHierarchy | null> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('GET', `/v1/entities/${entityId}/hierarchy`)
        await mockDelay()

        const hierarchy = getMockEntityHierarchy(entityId)
        if (!hierarchy) {
          throw new Error('Entity not found')
        }

        return hierarchy
      }

      // Real API call
      const hierarchy = await authStore.apiCall<EntityHierarchy>(
        `/v1/entities/${entityId}/hierarchy`
      )
      return hierarchy
    } catch (error: any) {
      state.error = error.message || 'Failed to fetch entity hierarchy'
      console.error('Failed to fetch entity hierarchy:', error)
      return null
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Get entity path (all ancestors)
   */
  const getEntityPath = async (entityId: string): Promise<Entity[]> => {
    const hierarchy = await getEntityHierarchy(entityId)
    return hierarchy?.path || []
  }

  /**
   * Get entity descendants (all children recursively)
   */
  const getEntityDescendants = async (entityId: string): Promise<Entity[]> => {
    const hierarchy = await getEntityHierarchy(entityId)
    return hierarchy?.descendants || []
  }

  /**
   * Create new entity
   */
  const createEntity = async (data: CreateEntityData): Promise<Entity | null> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('POST', '/v1/entities', data)
        await mockDelay()

        // Validate parent exists
        if (data.parent_id) {
          const parentExists = mockEntitiesData.value.some(e => e.id === data.parent_id)
          if (!parentExists) {
            throw new Error('Parent entity not found')
          }
        }

        const newEntity: Entity = {
          id: mockId(),
          name: data.name,
          entity_type: data.entity_type,
          entity_class: data.entity_class,
          parent_id: data.parent_id,
          description: data.description || '',
          metadata: data.metadata || {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }

        mockEntitiesData.value.push(newEntity)
        return newEntity
      }

      // Real API call
      const entity = await authStore.apiCall<Entity>('/v1/entities', {
        method: 'POST',
        body: JSON.stringify(data)
      })

      return entity
    } catch (error: any) {
      state.error = error.message || 'Failed to create entity'
      console.error('Failed to create entity:', error)
      throw error
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Update entity
   */
  const updateEntity = async (entityId: string, data: UpdateEntityData): Promise<Entity | null> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('PATCH', `/v1/entities/${entityId}`, data)
        await mockDelay()

        const entityIndex = mockEntitiesData.value.findIndex(e => e.id === entityId)
        if (entityIndex === -1) {
          throw new Error('Entity not found')
        }

        const currentEntity = mockEntitiesData.value[entityIndex]
        if (!currentEntity) {
          throw new Error('Entity not found')
        }

        const updatedEntity: Entity = {
          ...currentEntity,
          name: data.name ?? currentEntity.name,
          entity_type: data.entity_type ?? currentEntity.entity_type,
          description: data.description ?? currentEntity.description,
          metadata: data.metadata ?? currentEntity.metadata,
          updated_at: new Date().toISOString()
        }

        mockEntitiesData.value[entityIndex] = updatedEntity
        state.selectedEntity = updatedEntity
        return updatedEntity
      }

      // Real API call
      const entity = await authStore.apiCall<Entity>(`/v1/entities/${entityId}`, {
        method: 'PATCH',
        body: JSON.stringify(data)
      })

      state.selectedEntity = entity
      return entity
    } catch (error: any) {
      state.error = error.message || 'Failed to update entity'
      console.error('Failed to update entity:', error)
      throw error
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Move entity to new parent
   */
  const moveEntity = async (entityId: string, newParentId: string | null): Promise<boolean> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('POST', `/v1/entities/${entityId}/move`, { parent_id: newParentId })
        await mockDelay()

        const entityIndex = mockEntitiesData.value.findIndex(e => e.id === entityId)
        if (entityIndex === -1) {
          throw new Error('Entity not found')
        }

        // Validate new parent exists
        if (newParentId) {
          const parentExists = mockEntitiesData.value.some(e => e.id === newParentId)
          if (!parentExists) {
            throw new Error('Parent entity not found')
          }

          // Prevent circular reference
          if (newParentId === entityId) {
            throw new Error('Cannot move entity to itself')
          }
        }

        const entity = mockEntitiesData.value[entityIndex]
        if (entity) {
          entity.parent_id = newParentId || undefined
          entity.updated_at = new Date().toISOString()
        }

        if (state.selectedEntity?.id === entityId) {
          state.selectedEntity.parent_id = newParentId || undefined
          state.selectedEntity.updated_at = new Date().toISOString()
        }

        return true
      }

      // Real API call
      await authStore.apiCall(`/v1/entities/${entityId}/move`, {
        method: 'POST',
        body: JSON.stringify({ parent_id: newParentId })
      })

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to move entity'
      console.error('Failed to move entity:', error)
      return false
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Delete entity
   */
  const deleteEntity = async (entityId: string): Promise<boolean> => {
    try {
      state.isLoading = true
      state.error = null

      // Mock mode
      if (USE_MOCK_DATA) {
        logMockCall('DELETE', `/v1/entities/${entityId}`)
        await mockDelay()

        const entityIndex = mockEntitiesData.value.findIndex(e => e.id === entityId)
        if (entityIndex === -1) {
          throw new Error('Entity not found')
        }

        // Check for children
        const hasChildren = mockEntitiesData.value.some(e => e.parent_id === entityId)
        if (hasChildren) {
          throw new Error('Cannot delete entity with children')
        }

        mockEntitiesData.value.splice(entityIndex, 1)

        // Remove from state.entities if present
        const stateIndex = state.entities.findIndex(e => e.id === entityId)
        if (stateIndex !== -1) {
          state.entities.splice(stateIndex, 1)
        }

        // Clear selected entity if it was deleted
        if (state.selectedEntity?.id === entityId) {
          state.selectedEntity = null
        }

        return true
      }

      // Real API call
      await authStore.apiCall(`/v1/entities/${entityId}`, {
        method: 'DELETE'
      })

      // Remove from local state
      const stateIndex = state.entities.findIndex(e => e.id === entityId)
      if (stateIndex !== -1) {
        state.entities.splice(stateIndex, 1)
      }

      if (state.selectedEntity?.id === entityId) {
        state.selectedEntity = null
      }

      return true
    } catch (error: any) {
      state.error = error.message || 'Failed to delete entity'
      console.error('Failed to delete entity:', error)
      return false
    } finally {
      state.isLoading = false
    }
  }

  /**
   * Get children of entity
   */
  const getChildren = (entityId: string): Entity[] => {
    return state.entities.filter(e => e.parent_id === entityId)
  }

  /**
   * Check if entity has children
   */
  const hasChildren = (entityId: string): boolean => {
    return state.entities.some(e => e.parent_id === entityId)
  }

  /**
   * Clear selected entity
   */
  const clearSelectedEntity = (): void => {
    state.selectedEntity = null
  }

  /**
   * Clear error
   */
  const clearError = (): void => {
    state.error = null
  }

  /**
   * Reset mock data (useful for testing)
   */
  const resetMockData = (): void => {
    if (USE_MOCK_DATA) {
      mockEntitiesData.value = [...mockEntities]
      state.entities = []
      state.selectedEntity = null
      state.entityTree = []
      state.error = null
    }
  }

  return {
    // State (do not use readonly - prevents Pinia mutations)
    state,

    // Getters
    entities,
    selectedEntity,
    entityTree,
    isLoading,
    error,
    pagination,
    rootEntities,
    structuralEntities,
    accessGroupEntities,

    // Actions
    fetchEntities,
    fetchEntity,
    getEntityHierarchy,
    getEntityPath,
    getEntityDescendants,
    createEntity,
    updateEntity,
    moveEntity,
    deleteEntity,
    getChildren,
    hasChildren,
    clearSelectedEntity,
    clearError,
    resetMockData
  }
})
