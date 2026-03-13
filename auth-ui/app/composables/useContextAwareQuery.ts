/**
 * Context-Aware Query Composable
 *
 * For EnterpriseRBAC mode: Automatically includes context in query keys
 * When context switches, queries auto-refetch with new context
 *
 * Example Usage:
 *
 * ```typescript
 * // Instead of:
 * const { data } = useQuery(() => usersQueries.list(filters.value, params.value))
 *
 * // Use:
 * const { data } = useContextAwareQuery(() => usersQueries.list(filters.value, params.value))
 * ```
 *
 * This automatically adds context to the query key:
 * - Before: ['users', 'list', { filters, params }]
 * - After:  ['users', 'list', { filters, params }, { contextId: 'entity-123' }]
 *
 * When context switches from entity-123 to entity-456:
 * - Query key changes
 * - Pinia Colada sees new key
 * - Auto-refetches with new context
 * - NO manual refetch needed!
 */

import { useQuery } from '@pinia/colada'
import type { UseQueryOptions } from '@pinia/colada'
import { toValue } from 'vue'

/**
 * Wraps useQuery to automatically include context in query keys
 *
 * When selectedEntity changes, the query key changes, triggering auto-refetch
 */
export function useContextAwareQuery<TData = unknown, TError = Error>(
  optionsFn: () => UseQueryOptions<TData, TError>
) {
  const contextStore = useContextStore()

  return useQuery((() => {
    const options = optionsFn()
    const originalKey = toValue(options.key)

    return {
      ...options,
      key: [
        ...(Array.isArray(originalKey) ? originalKey : [originalKey]),
        { contextId: contextStore.selectedEntity?.id ?? null }
      ]
    }
  }) as any)
}

/**
 * Example: Context-aware user list query
 *
 * ```typescript
 * const { data: users } = useContextAwareQuery(
 *   () => usersQueries.list(filters.value, params.value)
 * )
 *
 * // When user switches from "Acme Corp" to "Tech Startup":
 * // 1. contextStore.selectedEntity changes
 * // 2. Query key includes new contextId
 * // 3. Pinia Colada detects new key
 * // 4. Auto-refetches users for new context
 * // 5. UI updates automatically
 * ```
 */

/**
 * Alternative Pattern: Manually include context in filters
 *
 * For more explicit control, include context directly in query keys:
 *
 * ```typescript
 * const contextStore = useContextStore()
 *
 * const filters = computed(() => ({
 *   search: search.value,
 *   // Context included in filters
 *   entity_id: contextStore.selectedEntity?.id
 * }))
 *
 * const { data } = useQuery(
 *   () => usersQueries.list(filters.value, params.value)
 * )
 *
 * // Query key automatically includes entity_id
 * // When context switches, filters change, key changes, auto-refetch!
 * ```
 */
