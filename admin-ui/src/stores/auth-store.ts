import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
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
  
  // Actions
  login: (tokens: AuthTokens, user?: User) => Promise<void>;
  logout: () => void;
  refreshTokens: () => Promise<void>;
  setUser: (user: User) => void;
  clearAuth: () => void;
  
  // Computed
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
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

      // Login action
      login: async (tokens: AuthTokens, user?: User) => {
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
      },

      // Logout action
      logout: () => {
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
          return;
        }

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
            set({ 
              tokens: newTokens, 
              isAuthenticated: true 
            });
          } else {
            // Refresh failed, logout
            get().logout();
          }
        } catch (error) {
          // Refresh failed, logout
          get().logout();
          throw error;
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