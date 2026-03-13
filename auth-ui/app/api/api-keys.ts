/**
 * API Keys API
 * API functions for API key management
 * Based on outlabs_auth/routers/api_keys.py
 */

import type {
  ApiKey,
  CreateApiKeyRequest,
  UpdateApiKeyRequest,
  ApiKeyCreateResponse,
} from '~/types/api-key'
import { createAPIClient } from './client'

export function createApiKeysAPI() {
  const client = createAPIClient()

  return {
    /**
     * List all API keys for the current user
     * GET /v1/api-keys/
     * Returns all keys (no pagination - backend returns user's keys only)
     */
    async listApiKeys(): Promise<ApiKey[]> {
      return client.call<ApiKey[]>('/v1/api-keys/')
    },

    /**
     * Create a new API key
     * POST /v1/api-keys/
     * IMPORTANT: The full API key is only returned ONCE in this response!
     */
    async createApiKey(data: CreateApiKeyRequest): Promise<ApiKeyCreateResponse> {
      return client.call<ApiKeyCreateResponse>('/v1/api-keys/', {
        method: 'POST',
        body: data,
      })
    },

    /**
     * Get API key details by ID
     * GET /v1/api-keys/{id}
     * Note: Full key is NOT returned, only prefix and metadata
     */
    async getApiKey(keyId: string): Promise<ApiKey> {
      return client.call<ApiKey>(`/v1/api-keys/${keyId}`)
    },

    /**
     * Update API key
     * PATCH /v1/api-keys/{id}
     * Can update: name, description, scopes, rate_limit_per_minute, IP whitelist, status
     */
    async updateApiKey(
      keyId: string,
      data: UpdateApiKeyRequest
    ): Promise<ApiKey> {
      return client.call<ApiKey>(`/v1/api-keys/${keyId}`, {
        method: 'PATCH',
        body: data,
      })
    },

    /**
     * Revoke (delete) API key
     * DELETE /v1/api-keys/{id}
     * Sets status to REVOKED - this action cannot be undone
     */
    async revokeApiKey(keyId: string): Promise<void> {
      return client.call<void>(`/v1/api-keys/${keyId}`, {
        method: 'DELETE',
      })
    },

    /**
     * Rotate API key (create new, revoke old)
     * POST /v1/api-keys/{id}/rotate
     */
    async rotateApiKey(keyId: string): Promise<ApiKeyCreateResponse> {
      return client.call<ApiKeyCreateResponse>(`/v1/api-keys/${keyId}/rotate`, {
        method: 'POST',
      })
    },
  }
}
