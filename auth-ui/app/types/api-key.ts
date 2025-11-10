/**
 * API Key types matching backend schemas
 * Based on outlabs_auth/schemas/api_key.py
 */

/**
 * API Key status enum
 * Matches ApiKeyStatus in outlabs_auth/models/api_key.py
 */
export enum ApiKeyStatus {
  ACTIVE = 'active',
  SUSPENDED = 'suspended',
  REVOKED = 'revoked',
  EXPIRED = 'expired',
}

/**
 * API Key response
 * Matches ApiKeyResponse in outlabs_auth/schemas/api_key.py (lines 36-55)
 */
export interface ApiKey {
  id: string
  prefix: string // First 12 characters (e.g., "sk_live_abc1")
  name: string
  scopes: string[]
  ip_whitelist?: string[]
  rate_limit_per_minute: number
  rate_limit_per_hour?: number
  rate_limit_per_day?: number
  status: ApiKeyStatus
  usage_count: number
  created_at: string // ISO 8601 datetime
  expires_at?: string | null // ISO 8601 datetime or null
  last_used_at?: string | null // ISO 8601 datetime or null
  description?: string | null
  entity_ids?: string[] // EnterpriseRBAC only
  owner_id?: string
}

/**
 * Create API Key request
 * Matches ApiKeyCreateRequest in outlabs_auth/schemas/api_key.py (lines 11-33)
 */
export interface CreateApiKeyRequest {
  name: string // Required
  scopes?: string[] // Default: []
  prefix_type?: string // Default: "sk_live"
  ip_whitelist?: string[]
  rate_limit_per_minute?: number // Default: 60
  rate_limit_per_hour?: number
  rate_limit_per_day?: number
  expires_in_days?: number // Service converts to expires_at datetime
  description?: string
  entity_ids?: string[] // EnterpriseRBAC only
}

/**
 * Create API Key response
 * Matches ApiKeyCreateResponse in outlabs_auth/schemas/api_key.py (lines 58-61)
 * IMPORTANT: The full api_key is only shown ONCE at creation!
 */
export interface ApiKeyCreateResponse extends ApiKey {
  api_key: string // Full API key - only returned once!
}

/**
 * Update API Key request
 * Matches ApiKeyUpdateRequest in outlabs_auth/schemas/api_key.py (lines 64-73)
 * All fields are optional
 */
export interface UpdateApiKeyRequest {
  name?: string
  scopes?: string[]
  ip_whitelist?: string[]
  rate_limit_per_minute?: number
  rate_limit_per_hour?: number
  rate_limit_per_day?: number
  status?: ApiKeyStatus
  description?: string
  entity_ids?: string[] // EnterpriseRBAC only
  expires_at?: string | null // ISO 8601 datetime or null
}

/**
 * Prefix type options for API key generation
 */
export type PrefixType = 'sk_live' | 'sk_test' | 'sk_prod' | 'sk_dev'
