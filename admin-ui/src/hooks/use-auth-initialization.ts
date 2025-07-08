import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';

/**
 * Hook to initialize authentication on app startup
 * - Checks if stored tokens are still valid
 * - Initializes automatic token refresh
 * - Clears auth if tokens are invalid
 */
export function useAuthInitialization() {
  const { 
    isAuthenticated, 
    isTokenValid, 
    clearAuth, 
    initializeTokenRefresh,
    tokens 
  } = useAuthStore();

  useEffect(() => {
    // On mount, check if we have valid authentication
    if (isAuthenticated && tokens) {
      if (!isTokenValid()) {
        console.log('Stored token is expired, clearing auth...');
        clearAuth();
        // Don't redirect here - let the routing logic handle it
        // This allows the platform status check to run properly
      } else {
        console.log('Token is valid, initializing refresh mechanism...');
        initializeTokenRefresh();
      }
    }
  }, []); // Only run on mount
}