/**
 * Application configuration
 * Uses Vite environment variables with proper defaults
 */

export const config = {
  api: {
    baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8030',
    version: 'v1'
  },
  app: {
    name: 'outlabsAuth',
    environment: import.meta.env.VITE_APP_ENV || 'development'
  }
} as const;

// Helper to construct API URLs
export function apiUrl(path: string): string {
  const base = config.api.baseUrl.replace(/\/$/, ''); // Remove trailing slash
  const version = config.api.version;
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  
  // If path already includes version, don't add it again
  if (cleanPath.startsWith(`/${version}/`)) {
    return `${base}${cleanPath}`;
  }
  
  return `${base}/${version}${cleanPath}`;
}