import type { PiniaColadaOptions } from '@pinia/colada'
import { PiniaColadaRetry } from '@pinia/colada-plugin-retry'

export default {
  plugins: [
    PiniaColadaRetry({
      retry: 1,
      delay: (attemptIndex: number) => Math.min(1000 * 2 ** attemptIndex, 30000),
    }),
  ],

  queryOptions: {
    staleTime: 5000,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    refetchOnMount: true,
  },
} satisfies PiniaColadaOptions
