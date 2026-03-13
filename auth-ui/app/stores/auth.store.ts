/**
 * Auth Store
 * Handles JWT authentication, token refresh, and API calls
 * Based on proven patterns from archived frontend
 */

import { defineStore } from "pinia";
import type {
  User,
  LoginCredentials,
  AuthTokens,
  AuthState,
  SystemStatus,
  AuthConfig,
} from "~/types/auth";
import type { ApiRequestOptions, JsonRequestBody } from "~/types/http";
import { normalizeAuthApiPrefix, resolveAuthEndpoint } from "~/utils/auth-endpoint";

const ACCESS_TOKEN_KEY = "outlabs_auth_access_token";
const REFRESH_TOKEN_KEY = "outlabs_auth_refresh_token";
const USER_KEY = "outlabs_auth_user";

export const useAuthStore = defineStore("auth", () => {
  const config = useRuntimeConfig();
  const authApiPrefix = computed(() =>
    normalizeAuthApiPrefix(config.public.authApiPrefix as string | undefined),
  );

  const resolveEndpoint = (endpoint: string): string =>
    resolveAuthEndpoint(endpoint, authApiPrefix.value);

  const defaultFeatures: AuthConfig["features"] = {
    entity_hierarchy: false,
    context_aware_roles: false,
    abac: false,
    tree_permissions: false,
    api_keys: true,
    user_status: true,
    activity_tracking: true,
    invitations: true,
  };

  // State
  const state = reactive<AuthState>({
    accessToken: null,
    refreshToken: null,
    user: null,
    isAuthenticated: false,
    isInitialized: false,
    config: null,
    isConfigLoaded: false,
  });

  // Helper to safely access localStorage
  const safeLocalStorage = {
    getItem: (key: string) =>
      import.meta.client ? localStorage.getItem(key) : null,
    setItem: (key: string, value: string) =>
      import.meta.client && localStorage.setItem(key, value),
    removeItem: (key: string) =>
      import.meta.client && localStorage.removeItem(key),
  };

  // Getters
  const isAuthenticated = computed(() => state.isAuthenticated);
  const currentUser = computed(() => state.user);
  const accessToken = computed(() => state.accessToken);
  const isSimpleRBAC = computed(() => state.config?.preset === "SimpleRBAC");
  const isEnterpriseRBAC = computed(
    () => state.config?.preset === "EnterpriseRBAC",
  );
  const features = computed<AuthConfig["features"]>(
    () => state.config?.features || defaultFeatures,
  );
  const availablePermissions = computed(
    () => state.config?.available_permissions || [],
  );

  const isJsonRequestBody = (body: unknown): body is JsonRequestBody => {
    if (body == null) {
      return false;
    }

    if (Array.isArray(body)) {
      return true;
    }

    if (typeof body !== "object") {
      return false;
    }

    const prototype = Object.getPrototypeOf(body);
    return prototype === Object.prototype || prototype === null;
  };

  /**
   * Initialize auth state from localStorage
   * Called on app startup
   */
  const initialize = async (): Promise<boolean> => {
    if (state.isInitialized) {
      return state.isAuthenticated;
    }

    // Skip initialization on server-side
    if (import.meta.server) {
      state.isInitialized = true;
      return false;
    }

    try {
      // Load tokens and user from localStorage
      const storedAccessToken = safeLocalStorage.getItem(ACCESS_TOKEN_KEY);
      const storedRefreshToken = safeLocalStorage.getItem(REFRESH_TOKEN_KEY);
      const storedUser = safeLocalStorage.getItem(USER_KEY);

      if (storedAccessToken && storedUser) {
        state.accessToken = storedAccessToken;
        state.refreshToken = storedRefreshToken;
        state.user = JSON.parse(storedUser);
        state.isAuthenticated = true;

        // Verify token is still valid by fetching current user
        try {
          await fetchCurrentUser();
        } catch (error) {
          // Token expired or invalid, try to refresh
          if (state.refreshToken) {
            try {
              await refreshAccessToken();
              await fetchCurrentUser();
            } catch {
              // Refresh failed, clear auth state
              clearAuthState();
            }
          } else {
            clearAuthState();
          }
        }
      }

      // Fetch config regardless of auth state (it's a public endpoint)
      // This allows the UI to adapt before user logs in
      await fetchConfig();

      state.isInitialized = true;
      return state.isAuthenticated;
    } catch (error) {
      console.error("Failed to initialize auth:", error);
      state.isInitialized = true;
      return false;
    }
  };

  /**
   * Make authenticated API call with automatic token refresh
   * This is the main method for all API requests
   */
  const apiCall = async <T>(
    endpoint: string,
    options: ApiRequestOptions = {},
  ): Promise<T> => {
    const contextStore = useContextStore();
    const { baseURL = config.public.apiBaseUrl, ...fetchOptions } = options;

    // Get context headers if available
    const contextHeaders = contextStore?.getContextHeaders() || {};

    const makeRequest = async (token: string | null): Promise<T> => {
      const { body, ...requestInitOptions } = fetchOptions;
      const headers = new Headers(contextHeaders);
      if (fetchOptions.headers) {
        new Headers(fetchOptions.headers).forEach((value, key) => {
          headers.set(key, value);
        });
      }
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }

      const isJsonBody = isJsonRequestBody(body);
      if (isJsonBody && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }

      const requestOptions: RequestInit = {
        ...requestInitOptions,
        headers,
        credentials: "include", // Important for httpOnly cookies
      };

      if (isJsonBody) {
        requestOptions.body = JSON.stringify(body);
      } else if (body !== undefined) {
        requestOptions.body = body;
      }

      const response = await fetch(
        `${baseURL}${resolveEndpoint(endpoint)}`,
        requestOptions,
      );

      if (!response.ok) {
        const error: any = new Error(`HTTP ${response.status}`);
        error.status = response.status;
        error.statusText = response.statusText;

        try {
          error.data = await response.json();
        } catch {
          error.data = { detail: response.statusText };
        }

        throw error;
      }

      // Handle empty responses (204 No Content, 205 Reset Content have no body)
      if (response.status === 204 || response.status === 205) {
        return {} as T;
      }

      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        return await response.json();
      }

      return {} as T;
    };

    try {
      return await makeRequest(state.accessToken);
    } catch (error: any) {
      // If 401 and we have a refresh token, try to refresh and retry
      if (error.status === 401 && state.refreshToken) {
        try {
          const newToken = await refreshAccessToken();
          return await makeRequest(newToken);
        } catch (refreshError) {
          // Refresh failed, logout user
          await logout();
          throw error;
        }
      }
      throw error;
    }
  };

  /**
   * Login with email and password
   */
  const login = async (credentials: LoginCredentials): Promise<void> => {
    try {
      // Real API call - OutlabsAuth format
      const response = await fetch(
        `${config.public.apiBaseUrl}${resolveEndpoint("/auth/login")}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(credentials),
          credentials: "include",
        },
      );

      if (!response.ok) {
        const error: any = await response.json();
        throw new Error(error.detail || "Login failed");
      }

      const data: AuthTokens = await response.json();

      // Store tokens
      state.accessToken = data.access_token;
      state.refreshToken = data.refresh_token;
      state.isAuthenticated = true;

      safeLocalStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
      if (data.refresh_token) {
        safeLocalStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
      }

      // Fetch current user
      await fetchCurrentUser();

      // Fetch auth config
      await fetchConfig();
    } catch (error) {
      clearAuthState();
      throw error;
    }
  };

  /**
   * Logout user
   */
  const logout = async (): Promise<void> => {
    try {
      // Call logout endpoint if authenticated (direct fetch, not apiCall to avoid infinite loop)
      if (state.refreshToken && state.accessToken) {
        await fetch(
          `${config.public.apiBaseUrl}${resolveEndpoint("/auth/logout")}`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${state.accessToken}`,
            },
            body: JSON.stringify({ refresh_token: state.refreshToken }),
            credentials: "include",
          },
        ).catch(() => {
          // Ignore logout errors - we're clearing state anyway
        });
      }
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      clearAuthState();

      // Navigate to login
      await navigateTo("/login");
    }
  };

  /**
   * Refresh access token using refresh token
   */
  const refreshAccessToken = async (): Promise<string> => {
    if (!state.refreshToken) {
      throw new Error("No refresh token available");
    }

    try {
      const response = await fetch(
        `${config.public.apiBaseUrl}${resolveEndpoint("/auth/refresh")}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ refresh_token: state.refreshToken }),
          credentials: "include",
        },
      );

      if (!response.ok) {
        throw new Error("Token refresh failed");
      }

      const data: AuthTokens = await response.json();

      state.accessToken = data.access_token;
      if (data.refresh_token) {
        state.refreshToken = data.refresh_token;
      }

      safeLocalStorage.setItem(ACCESS_TOKEN_KEY, data.access_token);
      if (data.refresh_token) {
        safeLocalStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);
      }

      return data.access_token;
    } catch (error) {
      clearAuthState();
      throw error;
    }
  };

  /**
   * Fetch current user
   */
  const fetchCurrentUser = async (): Promise<void> => {
    const user = await apiCall<User>("/users/me");
    if (user) {
      // Enrich user with computed fields
      const { enrichUser } = useUserHelpers();
      state.user = enrichUser(user);
      safeLocalStorage.setItem(USER_KEY, JSON.stringify(state.user));
    }
  };

  /**
   * Fetch auth configuration
   * Detects SimpleRBAC vs EnterpriseRBAC and available features
   *
   * This is a public endpoint (no auth required)
   */
  const fetchConfig = async (): Promise<void> => {
    try {
      // Make unauthenticated request to config endpoint
      const response = await fetch(
        `${config.public.apiBaseUrl}${resolveEndpoint("/auth/config")}`,
        {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        },
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch config: ${response.status}`);
      }

      const configData = await response.json();

      // Transform available_permissions to PermissionOption[]
      // Backend may return strings: ["user:read", ...] or objects: [{value, label, category}, ...]
      const transformedPermissions = (
        configData.available_permissions || []
      ).map((perm: string | { value: string; label: string; category: string }) => {
        // If already an object, use it as-is
        if (typeof perm === "object" && perm.value) {
          return perm;
        }
        // If string, transform it
        const permStr = perm as string;
        const [resource, action] = permStr.split(":");
        return {
          value: permStr,
          label: action
            ? action.charAt(0).toUpperCase() + action.slice(1)
            : permStr,
          category: resource || "other",
          description: `${action || "access"} ${resource || "resource"}`,
        };
      });

      state.config = {
        ...configData,
        features: { ...defaultFeatures, ...configData.features },
        available_permissions: transformedPermissions,
      };
      state.isConfigLoaded = true;

      console.log(`✅ Auth config loaded: ${configData.preset}`, {
        features: configData.features,
        permissions: transformedPermissions.length,
      });
    } catch (error) {
      console.error("Failed to fetch auth config:", error);
      // Set defaults if config fetch fails (assume SimpleRBAC)
      state.config = {
        preset: "SimpleRBAC",
        features: defaultFeatures,
        available_permissions: [],
      };
      state.isConfigLoaded = true;
    }
  };

  /**
   * Clear auth state and localStorage
   */
  const clearAuthState = (): void => {
    state.accessToken = null;
    state.refreshToken = null;
    state.user = null;
    state.isAuthenticated = false;

    safeLocalStorage.removeItem(ACCESS_TOKEN_KEY);
    safeLocalStorage.removeItem(REFRESH_TOKEN_KEY);
    safeLocalStorage.removeItem(USER_KEY);
  };

  return {
    // State (do not use readonly - prevents Pinia mutations)
    state,

    // Getters
    isAuthenticated,
    currentUser,
    accessToken,
    isSimpleRBAC,
    isEnterpriseRBAC,
    features,
    availablePermissions,

    // Actions
    initialize,
    apiCall,
    login,
    logout,
    refreshAccessToken,
    fetchCurrentUser,
    fetchConfig,
  };
});
