/**
 * Pinia Colada Global Configuration
 *
 * These options are passed to the PiniaColada plugin and apply to all queries/mutations
 * unless overridden at the query level.
 */
import type { PiniaColadaOptions } from '@pinia/colada'

export default {
  // Query defaults
  query: {
    // How long data stays fresh before being considered stale (5 seconds default)
    staleTime: 5000,

    // Refetch queries when window regains focus
    refetchOnWindowFocus: true,

    // Refetch queries when network reconnects
    refetchOnReconnect: true,

    // Refetch queries when component mounts (if stale)
    refetchOnMount: true,

    // Number of retry attempts for failed queries
    retry: 1,

    // Delay between retries (exponential backoff)
    retryDelay: (attemptIndex: number) => Math.min(1000 * 2 ** attemptIndex, 30000),
  },

  // Mutation defaults
  mutation: {
    // Retry failed mutations once
    retry: 1,
  },
} satisfies PiniaColadaOptions
