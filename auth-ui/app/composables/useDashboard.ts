import { createSharedComposable } from '@vueuse/core'

const _useDashboard = () => {
  const route = useRoute()
  const router = useRouter()

  // UI state
  const isNotificationsSlideoverOpen = ref(false)

  // Keyboard shortcuts
  defineShortcuts({
    'g-d': () => router.push('/'),
    'g-u': () => router.push('/users'),
    'g-r': () => router.push('/roles'),
    'g-e': () => router.push('/entities'),
    'g-p': () => router.push('/permissions'),
    'g-k': () => router.push('/api-keys'),
    'g-s': () => router.push('/settings'),
    'n': () => isNotificationsSlideoverOpen.value = !isNotificationsSlideoverOpen.value
  })

  // Close slideaways on route change
  watch(() => route.fullPath, () => {
    isNotificationsSlideoverOpen.value = false
  })

  return {
    isNotificationsSlideoverOpen
  }
}

export const useDashboard = createSharedComposable(_useDashboard)
