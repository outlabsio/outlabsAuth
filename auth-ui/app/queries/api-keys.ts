/**
 * API Keys Queries & Mutations
 * Pinia Colada queries and mutations for API key management
 */

import { defineQueryOptions, useMutation, useQueryCache } from "@pinia/colada";
import { createApiKeysAPI } from "~/api/api-keys";
import type {
  ApiKey,
  CreateApiKeyRequest,
  UpdateApiKeyRequest,
  ApiKeyCreateResponse,
  ApiKeyStatus,
} from "~/types/api-key";

/**
 * Query Keys for API keys
 * Hierarchical structure for cache management
 */
export const API_KEY_KEYS = {
  all: ["api-keys"] as const,
  list: () => [...API_KEY_KEYS.all, "list"] as const,
  detail: (id: string) => [...API_KEY_KEYS.all, "detail", id] as const,
};

/**
 * API Keys Query Options
 * Reusable query definitions
 */
export const apiKeysQueries = {
  /**
   * Query for all API keys for the current user
   * Shorter staleTime since keys might be created/revoked frequently
   */
  list: () =>
    defineQueryOptions({
      key: API_KEY_KEYS.list(),
      query: async () => {
        const apiKeysAPI = createApiKeysAPI();
        return apiKeysAPI.listApiKeys();
      },
      staleTime: 30000, // 30 seconds - keys might be created/revoked
    }),

  /**
   * Query for a specific API key by ID
   */
  detail: (id: string) =>
    defineQueryOptions({
      key: API_KEY_KEYS.detail(id),
      query: async () => {
        const apiKeysAPI = createApiKeysAPI();
        return apiKeysAPI.getApiKey(id);
      },
      staleTime: 30000,
    }),
};

/**
 * Create API Key Mutation
 * Use this composable in components for proper Pinia Colada integration
 * IMPORTANT: The full API key is only returned ONCE! Save it immediately.
 */
export function useCreateApiKeyMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async (
      data: CreateApiKeyRequest,
    ): Promise<ApiKeyCreateResponse> => {
      const apiKeysAPI = createApiKeysAPI();
      return apiKeysAPI.createApiKey(data);
    },
    onSuccess: (data) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: API_KEY_KEYS.list() });

      toast.add({
        title: "API key created",
        description: `API key "${data.name}" has been created successfully`,
        color: "success",
      });
    },
    onError: (error: any) => {
      // Extract error message from response body
      let errorMessage = "Failed to create API key";
      if (error.data?.detail) {
        if (Array.isArray(error.data.detail)) {
          // FastAPI validation errors
          errorMessage = error.data.detail
            .map((e: any) => e.msg || JSON.stringify(e))
            .join(", ");
        } else {
          errorMessage = error.data.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      toast.add({
        title: "Error creating API key",
        description: errorMessage,
        color: "error",
      });
    },
  });
}

/**
 * Update API Key Mutation
 * Use this composable in components for proper Pinia Colada integration
 */
export function useUpdateApiKeyMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async ({
      id,
      data,
    }: {
      id: string;
      data: UpdateApiKeyRequest;
    }): Promise<ApiKey> => {
      const apiKeysAPI = createApiKeysAPI();
      return apiKeysAPI.updateApiKey(id, data);
    },
    onSuccess: (data, variables) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: API_KEY_KEYS.list() });
      queryCache.invalidateQueries({ key: API_KEY_KEYS.detail(variables.id) });

      toast.add({
        title: "API key updated",
        description: `API key "${data.name}" has been updated successfully`,
        color: "success",
      });
    },
    onError: (error: any) => {
      // Extract error message from response body
      let errorMessage = "Failed to update API key";
      if (error.data?.detail) {
        if (Array.isArray(error.data.detail)) {
          errorMessage = error.data.detail
            .map((e: any) => e.msg || JSON.stringify(e))
            .join(", ");
        } else {
          errorMessage = error.data.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      toast.add({
        title: "Error updating API key",
        description: errorMessage,
        color: "error",
      });
    },
  });
}

/**
 * Revoke API Key Mutation
 * Use this composable in components for proper Pinia Colada integration
 * Note: This sets status to REVOKED - this action cannot be undone
 */
export function useRevokeApiKeyMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async (keyId: string): Promise<void> => {
      const apiKeysAPI = createApiKeysAPI();
      return apiKeysAPI.revokeApiKey(keyId);
    },
    onSuccess: (_data, keyId) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: API_KEY_KEYS.list() });
      queryCache.invalidateQueries({ key: API_KEY_KEYS.detail(keyId) });

      toast.add({
        title: "API key revoked",
        description: "The API key has been revoked successfully",
        color: "success",
      });
    },
    onError: (error: any) => {
      // Extract error message from response body
      let errorMessage = "Failed to revoke API key";
      if (error.data?.detail) {
        if (Array.isArray(error.data.detail)) {
          errorMessage = error.data.detail
            .map((e: any) => e.msg || JSON.stringify(e))
            .join(", ");
        } else {
          errorMessage = error.data.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      toast.add({
        title: "Error revoking API key",
        description: errorMessage,
        color: "error",
      });
    },
  });
}

/**
 * Rotate API Key Mutation
 */
export function useRotateApiKeyMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async (keyId: string): Promise<ApiKeyCreateResponse> => {
      const apiKeysAPI = createApiKeysAPI();
      return apiKeysAPI.rotateApiKey(keyId);
    },
    onSuccess: (data, keyId) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: API_KEY_KEYS.list() });
      queryCache.invalidateQueries({ key: API_KEY_KEYS.detail(keyId) });

      toast.add({
        title: "API key rotated",
        description:
          "A replacement API key was created and the previous key was revoked.",
        color: "success",
      });
    },
    onError: (error: any) => {
      let errorMessage = "Failed to rotate API key";
      if (error.data?.detail) {
        if (Array.isArray(error.data.detail)) {
          errorMessage = error.data.detail
            .map((e: any) => e.msg || JSON.stringify(e))
            .join(", ");
        } else {
          errorMessage = error.data.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      toast.add({
        title: "Error rotating API key",
        description: errorMessage,
        color: "error",
      });
    },
  });
}

/**
 * Suspend API Key Mutation
 * Sets API key status to SUSPENDED (can be resumed later)
 */
export function useSuspendApiKeyMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async (keyId: string): Promise<ApiKey> => {
      const apiKeysAPI = createApiKeysAPI();
      return apiKeysAPI.updateApiKey(keyId, {
        status: "suspended" as ApiKeyStatus,
      });
    },
    onSuccess: (_data, keyId) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: API_KEY_KEYS.list() });
      queryCache.invalidateQueries({ key: API_KEY_KEYS.detail(keyId) });

      toast.add({
        title: "API key suspended",
        description:
          "The API key has been suspended and is temporarily disabled",
        color: "success",
      });
    },
    onError: (error: any) => {
      let errorMessage = "Failed to suspend API key";
      if (error.data?.detail) {
        if (Array.isArray(error.data.detail)) {
          errorMessage = error.data.detail
            .map((e: any) => e.msg || JSON.stringify(e))
            .join(", ");
        } else {
          errorMessage = error.data.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      toast.add({
        title: "Error suspending API key",
        description: errorMessage,
        color: "error",
      });
    },
  });
}

/**
 * Resume API Key Mutation
 * Sets API key status back to ACTIVE
 */
export function useResumeApiKeyMutation() {
  const queryCache = useQueryCache();
  const toast = useToast();

  return useMutation({
    mutation: async (keyId: string): Promise<ApiKey> => {
      const apiKeysAPI = createApiKeysAPI();
      return apiKeysAPI.updateApiKey(keyId, {
        status: "active" as ApiKeyStatus,
      });
    },
    onSuccess: (_data, keyId) => {
      // Invalidate to refetch fresh data
      queryCache.invalidateQueries({ key: API_KEY_KEYS.list() });
      queryCache.invalidateQueries({ key: API_KEY_KEYS.detail(keyId) });

      toast.add({
        title: "API key resumed",
        description: "The API key has been activated and is now operational",
        color: "success",
      });
    },
    onError: (error: any) => {
      let errorMessage = "Failed to resume API key";
      if (error.data?.detail) {
        if (Array.isArray(error.data.detail)) {
          errorMessage = error.data.detail
            .map((e: any) => e.msg || JSON.stringify(e))
            .join(", ");
        } else {
          errorMessage = error.data.detail;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      toast.add({
        title: "Error resuming API key",
        description: errorMessage,
        color: "error",
      });
    },
  });
}
