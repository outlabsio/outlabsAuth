/**
 * Global Auth Middleware
 * Handles authentication, route protection, and system status
 * Based on proven patterns from archived frontend
 */

export default defineNuxtRouteMiddleware(async (to) => {
  const authStore = useAuthStore()
  const contextStore = useContextStore()

  // Public routes that don't require authentication
  const publicRoutes = [
    '/login',
    '/signup',
    '/verify',
    '/recovery',
    '/setup'
  ]

  const isPublicRoute = publicRoutes.some(route => to.path.startsWith(route))

  // Check system initialization status first
  // This determines if we need to redirect to setup
  const systemStatus = await authStore.checkSystemStatus()

  // If system requires setup and we're not on setup page, redirect
  if (systemStatus.requires_setup && to.path !== '/setup') {
    return navigateTo('/setup')
  }

  // If on setup page but system is initialized, redirect to login
  if (to.path === '/setup' && !systemStatus.requires_setup) {
    return navigateTo('/login')
  }

  // Initialize auth state only on first load for protected routes
  if (!isPublicRoute && !authStore.state.isInitialized) {
    const initResult = await authStore.initialize()

    if (!initResult) {
      // Not authenticated, redirect to login
      return navigateTo({
        path: '/login',
        query: { redirect: to.fullPath }
      })
    }

    // Initialize context after successful auth
    await contextStore.initialize()
  }

  // If user is authenticated and trying to access public route, redirect to dashboard
  if (isPublicRoute && authStore.isAuthenticated) {
    // Exception: allow access to recovery/verify pages even when authenticated
    if (to.path.startsWith('/recovery') || to.path.startsWith('/verify')) {
      return
    }

    return navigateTo('/dashboard')
  }

  // If protected route and not authenticated, redirect to login
  if (!isPublicRoute && !authStore.isAuthenticated) {
    return navigateTo({
      path: '/login',
      query: { redirect: to.fullPath }
    })
  }

  // Check entity membership for protected routes (optional)
  // Uncomment this if you want to enforce entity membership
  /*
  if (!isPublicRoute && authStore.isAuthenticated && !contextStore.selectedEntity) {
    // User is authenticated but has no entity access
    return navigateTo('/no-access')
  }
  */
})
