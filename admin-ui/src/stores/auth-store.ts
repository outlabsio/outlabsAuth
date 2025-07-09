import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { isTokenExpired, willTokenExpireSoon, getTokenRemainingTime } from '@/lib/jwt';
import { apiUrl } from '@/config';

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  roles: any[];
  permissions?: string[];
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface AuthState {
  // State
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isRefreshing: boolean;
  refreshInterval: NodeJS.Timeout | null;
  
  // Actions
  login: (tokens: AuthTokens, user?: User) => Promise<void>;
  logout: () => void;
  refreshTokens: () => Promise<void>;
  setUser: (user: User) => void;
  clearAuth: () => void;
  initializeTokenRefresh: () => void;
  clearRefreshInterval: () => void;
  
  // Computed
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  isTokenValid: () => boolean;
  shouldRefreshToken: () => boolean;
}

// Create the store with persistence
export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      tokens: null,
      isAuthenticated: false,
      isRefreshing: false,
      refreshInterval: null,

      // Login action
      login: async (tokens: AuthTokens, user?: User) => {
        // Clear any existing refresh interval
        get().clearRefreshInterval();
        
        set({ 
          tokens, 
          isAuthenticated: true 
        });

        // If user is provided, set it, otherwise fetch it
        if (user) {
          set({ user });
        } else {
          try {
            const response = await fetch(apiUrl('/auth/me'), {
              headers: {
                Authorization: `Bearer ${tokens.access_token}`,
              },
            });
            
            if (response.ok) {
              const userData = await response.json();
              set({ user: userData });
            }
          } catch (error) {
            console.error('Failed to fetch user data:', error);
          }
        }
        
        // Initialize automatic token refresh
        // Use setTimeout to avoid blocking the login flow
        setTimeout(() => {
          get().initializeTokenRefresh();
        }, 0);
      },

      // Logout action
      logout: () => {
        // Clear refresh interval
        get().clearRefreshInterval();
        
        set({ 
          user: null, 
          tokens: null, 
          isAuthenticated: false 
        });
        // Clear all persisted data
        localStorage.removeItem('auth-storage');
        // Redirect to login
        window.location.href = '/login';
      },

      // Refresh tokens action
      refreshTokens: async () => {
        const { tokens, isRefreshing } = get();
        
        // Prevent multiple simultaneous refresh attempts
        if (isRefreshing || !tokens?.refresh_token) {
          console.log('[Auth] Skipping refresh - already refreshing or no refresh token');
          return;
        }

        console.log('[Auth] Starting token refresh...');
        set({ isRefreshing: true });

        try {
          const response = await fetch(apiUrl('/auth/refresh'), {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
              refresh_token: tokens.refresh_token 
            }),
          });

          if (response.ok) {
            const newTokens: AuthTokens = await response.json();
            console.log('[Auth] Token refresh successful');
            set({ 
              tokens: newTokens, 
              isAuthenticated: true 
            });
          } else {
            console.error('[Auth] Token refresh failed with status:', response.status);
            const errorText = await response.text();
            console.error('[Auth] Error response:', errorText);
            // Refresh failed, logout
            get().logout();
          }
        } catch (error) {
          console.error('[Auth] Token refresh failed with error:', error);
          get().logout();
        } finally {
          set({ isRefreshing: false });
        }
      },

      // Set user data
      setUser: (user: User) => {
        set({ user });
      },

      // Clear auth data (without redirect)
      clearAuth: () => {
        set({ 
          user: null, 
          tokens: null, 
          isAuthenticated: false 
        });
      },

      // Get access token
      getAccessToken: () => {
        return get().tokens?.access_token || null;
      },

      // Get refresh token
      getRefreshToken: () => {
        return get().tokens?.refresh_token || null;
      },

      // Check if token is valid (not expired)
      isTokenValid: () => {
        const token = get().tokens?.access_token;
        if (!token) return false;
        return !isTokenExpired(token);
      },

      // Check if token should be refreshed (expires in less than 5 minutes)
      shouldRefreshToken: () => {
        const token = get().tokens?.access_token;
        if (!token) return false;
        return willTokenExpireSoon(token, 300); // 5 minutes
      },

      // Initialize automatic token refresh
      initializeTokenRefresh: () => {
        const { refreshInterval } = get();
        
        // Clear existing interval if any
        if (refreshInterval) {
          clearInterval(refreshInterval);
        }

        // Do an immediate check (async to not block)
        setTimeout(() => {
          const state = get();
          if (state.tokens && state.shouldRefreshToken() && !state.isRefreshing) {
            console.log('[Auth] Token expiring soon, refreshing immediately...');
            state.refreshTokens();
          }
        }, 100);

        // Set up interval to check token every 30 seconds
        const interval = setInterval(async () => {
          const currentState = get();
          
          if (!currentState.tokens) {
            console.log('[Auth] No tokens, skipping refresh check');
            return;
          }

          const token = currentState.tokens.access_token;
          const remainingTime = getTokenRemainingTime(token);
          console.log(`[Auth] Token check - ${remainingTime}s remaining`);
          
          // Only refresh if we have tokens and should refresh
          if (currentState.shouldRefreshToken() && !currentState.isRefreshing) {
            console.log('[Auth] Token expiring soon, refreshing...');
            await currentState.refreshTokens();
          }
        }, 30000); // Check every 30 seconds

        set({ refreshInterval: interval });
      },

      // Clear refresh interval
      clearRefreshInterval: () => {
        const { refreshInterval } = get();
        if (refreshInterval) {
          clearInterval(refreshInterval);
          set({ refreshInterval: null });
        }
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ 
        tokens: state.tokens,
        user: state.user,
        isAuthenticated: state.isAuthenticated
      }),
    }
  )
);