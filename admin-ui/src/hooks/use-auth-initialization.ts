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
        window.location.href = '/login';
      } else {
        console.log('Token is valid, initializing refresh mechanism...');
        initializeTokenRefresh();
      }
    }
  }, []); // Only run on mount
}