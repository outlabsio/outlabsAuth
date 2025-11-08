/**
 * API Client
 * Base HTTP client for making authenticated API requests
 * Wraps auth store's apiCall method for use in query functions
 */

/**
 * Create API client
 * Returns a function that makes authenticated API calls
 * Must be called within Vue context (where stores are available)
 */
export function createAPIClient() {
  const authStore = useAuthStore()

  return {
    /**
     * Make authenticated API call
     * Automatically includes auth token and context headers
     */
    call: async <T>(endpoint: string, options?: RequestInit): Promise<T> => {
      return authStore.apiCall<T>(endpoint, options)
    },

    /**
     * Build query string from params object
     */
    buildQueryString: (params: Record<string, any>): string => {
      const queryParams = new URLSearchParams()

      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          queryParams.append(key, String(value))
        }
      })

      const qs = queryParams.toString()
      return qs ? `?${qs}` : ''
    }
  }
}

/**
 * Type helper for API responses
 */
export interface APIResponse<T> {
  data?: T
  error?: Error
  status: number
}

/**
 * Type helper for paginated responses
 */
export interface PaginatedAPIResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
}
