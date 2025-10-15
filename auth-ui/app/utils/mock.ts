/**
 * Mock Utilities
 * Controls mock mode for development without backend
 */

/**
 * Check if mock mode is enabled
 * Set NUXT_PUBLIC_USE_REAL_API=true to use real backend
 */
export function useMockMode(): boolean {
  const config = useRuntimeConfig()
  return !config.public.useRealApi
}

/**
 * Get mock mode status (for use in stores)
 * Returns true if using mock data, false if using real API
 */
export function getMockMode(): boolean {
  // Read directly from import.meta.env for SSR/module-level access
  return import.meta.env.NUXT_PUBLIC_USE_REAL_API !== 'true'
}

// Constant for convenience in stores
export const USE_MOCK_DATA = getMockMode()

/**
 * Simulate API delay for realistic mock behavior
 * Random delay between 200-700ms
 */
export const mockDelay = (min = 200, max = 700): Promise<void> => {
  return new Promise(resolve => {
    const delay = Math.floor(Math.random() * (max - min + 1)) + min
    setTimeout(resolve, delay)
  })
}

/**
 * Simulate API error for testing error states
 * @param probability - Chance of error (0-1)
 */
export const mockError = (probability = 0.1): boolean => {
  return Math.random() < probability
}

/**
 * Generate mock ID
 */
export const mockId = (): string => {
  return Math.random().toString(36).substring(2, 15)
}

/**
 * Log mock API call for debugging
 */
export const logMockCall = (method: string, endpoint: string, data?: any) => {
  if (import.meta.dev) {
    console.log(`[MOCK] ${method} ${endpoint}`, data || '')
  }
}
