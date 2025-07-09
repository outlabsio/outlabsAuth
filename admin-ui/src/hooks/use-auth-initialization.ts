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
    tokens,
    getAccessToken
  } = useAuthStore();

  useEffect(() => {
    // Add global debug function
    (window as any).checkAuthStatus = () => {
      const token = getAccessToken();
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const exp = new Date(payload.exp * 1000);
        const now = new Date();
        const remaining = Math.floor((exp.getTime() - now.getTime()) / 1000);
        console.log('[Auth Debug] Token expires at:', exp.toLocaleString());
        console.log('[Auth Debug] Time remaining:', remaining, 'seconds (', Math.floor(remaining/60), 'minutes)');
        console.log('[Auth Debug] Token payload:', payload);
      } else {
        console.log('[Auth Debug] No access token found');
      }
    };
    console.log('[Auth] Debug function available - run checkAuthStatus() in console');

    // On mount, check if we have valid authentication
    if (isAuthenticated && tokens) {
      if (!isTokenValid()) {
        console.log('[Auth] Stored token is expired, clearing auth...');
        clearAuth();
        // Don't redirect here - let the routing logic handle it
        // This allows the platform status check to run properly
      } else {
        console.log('[Auth] Token is valid, initializing refresh mechanism...');
        initializeTokenRefresh();
      }
    }
  }, []); // Only run on mount
}