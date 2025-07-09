import { useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';

/**
 * Hook to initialize authentication on app startup
 * Simply validates that we have tokens on mount
 */
export function useAuthInitialization() {
  const { isAuthenticated, clearAuth } = useAuthStore();

  useEffect(() => {
    // Add debug function
    (window as any).checkAuthStatus = () => {
      const store = useAuthStore.getState();
      const token = store.getAccessToken();
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const exp = new Date(payload.exp * 1000);
        const now = new Date();
        const remaining = Math.floor((exp.getTime() - now.getTime()) / 1000);
        console.log('[Auth Debug] Token expires at:', exp.toLocaleString());
        console.log('[Auth Debug] Time remaining:', remaining, 'seconds (', Math.floor(remaining/60), 'minutes)');
        console.log('[Auth Debug] Is authenticated:', store.isAuthenticated);
      } else {
        console.log('[Auth Debug] No access token found');
      }
    };
    
    console.log('[Auth] Debug: Run checkAuthStatus() to see token info');

    // Simply check if we're authenticated on mount
    if (isAuthenticated && !useAuthStore.getState().getAccessToken()) {
      console.log('[Auth] No access token found, clearing auth...');
      clearAuth();
    }
  }, []); // Only run on mount
}