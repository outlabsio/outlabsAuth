const DEFAULT_AUTH_API_PREFIX = "/v1";

const OUTLABS_PATH_SEGMENTS = [
  "/auth",
  "/users",
  "/roles",
  "/permissions",
  "/entities",
  "/memberships",
  "/api-keys",
  "/config",
];

function ensureLeadingSlash(value: string): string {
  return value.startsWith("/") ? value : `/${value}`;
}

function trimTrailingSlash(value: string): string {
  if (value === "/") {
    return value;
  }
  return value.replace(/\/+$/, "");
}

function isAbsoluteUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

function isOutlabsRoute(value: string): boolean {
  return OUTLABS_PATH_SEGMENTS.some(
    (segment) => value === segment || value.startsWith(`${segment}/`),
  );
}

export function normalizeAuthApiPrefix(prefix?: string | null): string {
  const raw = (prefix ?? DEFAULT_AUTH_API_PREFIX).trim();
  const resolved = raw.length > 0 ? raw : DEFAULT_AUTH_API_PREFIX;
  return trimTrailingSlash(ensureLeadingSlash(resolved));
}

export function resolveAuthEndpoint(
  endpoint: string,
  authApiPrefix?: string | null,
): string {
  if (!endpoint) {
    return normalizeAuthApiPrefix(authApiPrefix);
  }

  if (isAbsoluteUrl(endpoint)) {
    return endpoint;
  }

  const normalizedEndpoint = ensureLeadingSlash(endpoint);
  const prefix = normalizeAuthApiPrefix(authApiPrefix);

  if (normalizedEndpoint === prefix || normalizedEndpoint.startsWith(`${prefix}/`)) {
    return normalizedEndpoint;
  }

  if (normalizedEndpoint === "/v1") {
    return prefix;
  }

  if (normalizedEndpoint.startsWith("/v1/")) {
    return `${prefix}${normalizedEndpoint.slice(3)}`;
  }

  if (isOutlabsRoute(normalizedEndpoint)) {
    return `${prefix}${normalizedEndpoint}`;
  }

  return normalizedEndpoint;
}
