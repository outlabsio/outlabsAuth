import { useAuth } from "@/hooks/use-auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { authenticatedFetch } from "@/lib/auth";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Copy, AlertCircle, AlertTriangle, Info } from "lucide-react";

// Persistent debug logger
class DebugLogger {
  private static instance: DebugLogger;
  private logs: Array<{ timestamp: string; message: string; level: "info" | "error" | "warn" }> = [];
  private maxLogs = 50; // Reduced from 1000 to prevent localStorage quota issues
  private storageKey = "auth-debug-logs";
  private isLogging = false; // Prevent recursive logging
  private lastLogTime = 0;
  private logCount = 0;
  private rateLimitWindow = 1000; // 1 second
  private maxLogsPerSecond = 10; // Max 10 logs per second

  static getInstance(): DebugLogger {
    if (!DebugLogger.instance) {
      DebugLogger.instance = new DebugLogger();
    }
    return DebugLogger.instance;
  }

  log(message: string, level: "info" | "error" | "warn" = "info") {
    // Prevent recursive logging
    if (this.isLogging) {
      return;
    }

    // Rate limiting
    const now = Date.now();
    if (now - this.lastLogTime > this.rateLimitWindow) {
      this.logCount = 0;
      this.lastLogTime = now;
    }

    if (this.logCount >= this.maxLogsPerSecond) {
      // Skip this log due to rate limiting
      return;
    }

    this.isLogging = true;
    this.logCount++;

    try {
      const timestamp = new Date().toISOString();
      const logEntry = { timestamp, message, level };

      this.logs.push(logEntry);

      // Keep only the last N logs
      if (this.logs.length > this.maxLogs) {
        this.logs = this.logs.slice(-this.maxLogs);
      }

      // Store in localStorage with error handling
      this.saveToStorage();

      // Also log to console (using original console.log to avoid recursion)
      originalConsoleLog(`[LOG] [${timestamp}] ${message}`);
    } finally {
      this.isLogging = false;
    }
  }

  private saveToStorage() {
    try {
      const logsData = JSON.stringify(this.logs);
      localStorage.setItem(this.storageKey, logsData);
    } catch (error) {
      // If localStorage is full, clear old logs and try again
      if (error instanceof DOMException && error.name === "QuotaExceededError") {
        console.warn("[LOG] localStorage quota exceeded, clearing old logs");
        this.clearLogs();

        // Try to save just the last few logs
        const recentLogs = this.logs.slice(-10);
        try {
          localStorage.setItem(this.storageKey, JSON.stringify(recentLogs));
          this.logs = recentLogs;
        } catch (e) {
          console.error("[LOG] Failed to save even minimal logs:", e);
          // Continue without localStorage - logs will still be in memory
        }
      } else {
        console.error("[LOG] Failed to save debug logs:", error);
      }
    }
  }

  getLogs() {
    return this.logs;
  }

  loadLogs() {
    try {
      const stored = localStorage.getItem(this.storageKey);
      if (stored) {
        this.logs = JSON.parse(stored);
      }
    } catch (e) {
      console.error("[LOG] Failed to load debug logs:", e);
      // Clear corrupted data
      this.clearLogs();
    }
  }

  clearLogs() {
    this.logs = [];
    try {
      localStorage.removeItem(this.storageKey);
    } catch (e) {
      console.error("[LOG] Failed to clear debug logs:", e);
    }
  }
}

// Global debug logger instance
const debugLogger = DebugLogger.getInstance();

// Debug mode flag
let debugMode = false;

// Override console methods to capture logs
const originalConsoleLog = console.log;
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

// Flag to prevent recursive console calls
let isConsoleOverriding = false;

console.log = (...args) => {
  originalConsoleLog(...args);

  // Prevent recursive calls and only capture when debug mode is enabled
  if (
    !isConsoleOverriding &&
    debugMode &&
    args[0]?.includes &&
    (args[0].includes("[AUTH STORE]") || args[0].includes("[REFRESH]") || args[0].includes("[FETCH]") || args[0].includes("[TIMING]") || args[0].includes("[DEBUG]"))
  ) {
    isConsoleOverriding = true;
    try {
      debugLogger.log(args.join(" "), "info");
    } finally {
      isConsoleOverriding = false;
    }
  }
};

console.error = (...args) => {
  originalConsoleError(...args);

  // Prevent recursive calls and only capture when debug mode is enabled
  if (
    !isConsoleOverriding &&
    debugMode &&
    args[0]?.includes &&
    (args[0].includes("[AUTH STORE]") || args[0].includes("[REFRESH]") || args[0].includes("[FETCH]") || args[0].includes("[TIMING]") || args[0].includes("[DEBUG]"))
  ) {
    isConsoleOverriding = true;
    try {
      debugLogger.log(args.join(" "), "error");
    } finally {
      isConsoleOverriding = false;
    }
  }
};

console.warn = (...args) => {
  originalConsoleWarn(...args);

  // Prevent recursive calls and only capture when debug mode is enabled
  if (
    !isConsoleOverriding &&
    debugMode &&
    args[0]?.includes &&
    (args[0].includes("[AUTH STORE]") || args[0].includes("[REFRESH]") || args[0].includes("[FETCH]") || args[0].includes("[TIMING]") || args[0].includes("[DEBUG]"))
  ) {
    isConsoleOverriding = true;
    try {
      debugLogger.log(args.join(" "), "warn");
    } finally {
      isConsoleOverriding = false;
    }
  }
};

// Export debug mode controls
export const setDebugMode = (enabled: boolean) => {
  debugMode = enabled;
  localStorage.setItem("auth-debug-mode", enabled.toString());
  debugLogger.log(`Debug mode ${enabled ? "enabled" : "disabled"}`, "info");
};

export const getDebugMode = () => {
  const stored = localStorage.getItem("auth-debug-mode");
  return stored === "true";
};

export function AuthDebug() {
  const { isAuthenticated, isRefreshing, user, tokens, getAccessToken, isTokenExpired, isTokenExpiringSoon, logout } = useAuth();

  const [logs, setLogs] = useState<Array<{ timestamp: string; message: string; level: "info" | "error" | "warn" }>>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [debugModeEnabled, setDebugModeEnabledState] = useState(getDebugMode());

  useEffect(() => {
    debugLogger.loadLogs();
    setLogs(debugLogger.getLogs());

    // Check debug mode from localStorage
    const currentDebugMode = getDebugMode();
    setDebugModeEnabledState(currentDebugMode);
    setDebugMode(currentDebugMode);

    // Update logs periodically (less frequent)
    const interval = setInterval(() => {
      setLogs([...debugLogger.getLogs()]);
      // Also check if debug mode changed
      const newDebugMode = getDebugMode();
      if (newDebugMode !== debugModeEnabled) {
        setDebugModeEnabledState(newDebugMode);
        setDebugMode(newDebugMode);
      }
    }, 3000); // Reduced from 1000ms to 3000ms (3 seconds)

    return () => clearInterval(interval);
  }, []);

  // Test API call mutation
  const testApiCall = useMutation({
    mutationFn: async () => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Testing API call to /auth/me", "info");
      const response = await authenticatedFetch("/auth/me");
      return response.json();
    },
    onSuccess: (data) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: API call successful: " + JSON.stringify(data), "info");
      toast.success("API call successful!");
    },
    onError: (error: any) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: API call failed: " + error.message, "error");
      toast.error(`API call failed: ${error.message}`);
    },
  });

  // Test API connectivity
  const testApiConnectivity = useMutation({
    mutationFn: async () => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Testing API connectivity", "info");
      const url = "/api/v1/system/status";
      debugLogger.log("[DEBUG] AUTH DEBUG: Testing URL: " + url, "info");
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return response.json();
    },
    onSuccess: (data) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: API connectivity test successful: " + JSON.stringify(data), "info");
      toast.success("API is reachable!");
    },
    onError: (error: any) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: API connectivity test failed: " + error.message, "error");
      toast.error(`API unreachable: ${error.message}`);
    },
  });

  // Test expired token call mutation
  const testExpiredTokenCall = useMutation({
    mutationFn: async () => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Testing API call with fake expired token", "info");
      // Make a direct fetch with a fake expired token to test 401 handling
      const response = await fetch("/api/v1/auth/me", {
        headers: {
          Authorization: "Bearer expired_token_for_testing",
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(error?.detail || `HTTP ${response.status}`);
      }

      return response.json();
    },
    onSuccess: (data) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Expired token test successful (unexpected): " + JSON.stringify(data), "info");
      toast.success("Expired token test successful (unexpected)!");
    },
    onError: (error: any) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Expired token test failed (expected): " + error.message, "error");
      toast.error(`Expired token test failed (expected): ${error.message}`);
    },
  });

  // Test refresh endpoint directly without cookie (should fail)
  const testRefreshEndpoint = useMutation({
    mutationFn: async () => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Testing refresh endpoint without cookie (should fail)", "info");
      const url = "/api/v1/auth/refresh";
      debugLogger.log("[DEBUG] AUTH DEBUG: Testing URL: " + url, "info");

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        // No credentials: "include" - should fail
      });

      debugLogger.log("[DEBUG] AUTH DEBUG: Refresh endpoint response status: " + response.status, "info");

      if (!response.ok) {
        const errorText = await response.text();
        debugLogger.log("[DEBUG] AUTH DEBUG: Refresh endpoint error: " + errorText, "error");
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      return response.json();
    },
    onSuccess: (data) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Refresh endpoint test successful (unexpected): " + JSON.stringify(data), "info");
      toast.success("Refresh endpoint is working (unexpected)!");
    },
    onError: (error: any) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Refresh endpoint test failed (expected): " + error.message, "error");
      toast.error(`Refresh endpoint test (expected failure): ${error.message}`);
    },
  });

  // Test refresh endpoint with real cookie
  const testRealRefreshToken = useMutation({
    mutationFn: async () => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Testing refresh endpoint with REAL HTTP-only cookie", "info");

      const url = "/api/v1/auth/refresh";
      debugLogger.log("[DEBUG] AUTH DEBUG: Testing URL: " + url, "info");

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include HTTP-only cookie
      });

      debugLogger.log("[DEBUG] AUTH DEBUG: Real refresh response status: " + response.status, "info");

      if (!response.ok) {
        const errorText = await response.text();
        debugLogger.log("[DEBUG] AUTH DEBUG: Real refresh error: " + errorText, "error");
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      return response.json();
    },
    onSuccess: (data) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Real refresh test successful: " + JSON.stringify(data), "info");
      toast.success("Real refresh token works!");
    },
    onError: (error: any) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Real refresh test failed: " + error.message, "error");
      toast.error(`Real refresh test: ${error.message}`);
    },
  });

  // Force token refresh mutation
  const forceRefresh = useMutation({
    mutationFn: async () => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Forcing token refresh (cookie-based)", "info");
      const store = useAuthStore.getState();

      // Log current token state
      const currentTokens = store.tokens;
      debugLogger.log(
        "[DEBUG] AUTH DEBUG: Current tokens state: " +
          JSON.stringify({
            hasAccessToken: !!currentTokens?.access_token,
            refreshTokenLocation: "HTTP-only cookie (not accessible to JS)",
          }),
        "info"
      );

      await store.refreshTokens();
    },
    onSuccess: () => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Force refresh successful", "info");
      toast.success("Token refresh successful!");
    },
    onError: (error: any) => {
      debugLogger.log("[DEBUG] AUTH DEBUG: Force refresh failed: " + error.message, "error");
      toast.error(`Token refresh failed: ${error.message}`);
    },
  });

  // Get token expiry info (cached to avoid constant logging)
  const [tokenInfo, setTokenInfo] = useState<any>(null);

  const getTokenInfo = () => {
    const token = getAccessToken();
    if (!token) {
      return null;
    }

    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const currentTime = Date.now() / 1000;
      const timeUntilExpiry = payload.exp - currentTime;

      const info = {
        exp: payload.exp,
        currentTime,
        timeUntilExpiry,
        expiresAt: new Date(payload.exp * 1000).toLocaleString(),
        timeUntilExpiryMinutes: Math.floor(timeUntilExpiry / 60),
        timeUntilExpirySeconds: Math.floor(timeUntilExpiry % 60),
        issued: payload.iat ? new Date(payload.iat * 1000).toLocaleString() : "Unknown",
        subject: payload.sub || "Unknown",
      };

      return info;
    } catch (error) {
      return null;
    }
  };

  // Update token info less frequently
  useEffect(() => {
    const updateTokenInfo = () => {
      const info = getTokenInfo();
      setTokenInfo(info);
    };

    updateTokenInfo(); // Initial load
    const interval = setInterval(updateTokenInfo, 10000); // Update every 10 seconds

    return () => clearInterval(interval);
  }, [tokens]);

  const handleLogout = () => {
    debugLogger.log("[DEBUG] AUTH DEBUG: Manual logout triggered", "info");
    if (debugModeEnabled) {
      debugLogger.log("[DEBUG] AUTH DEBUG: Debug mode enabled - preventing automatic redirect", "warn");
      // In debug mode, just clear auth but don't redirect
      const store = useAuthStore.getState();
      store.clearAuth();
      toast.error("Logout called (debug mode - no redirect)");
    } else {
      logout();
    }
  };

  const copyLogsToClipboard = async (recentOnly = false) => {
    try {
      // Get logs to copy (all or recent 20)
      const logsToCopy = recentOnly ? logs.slice(-20) : logs;

      // Format logs for copying
      const logText = logsToCopy
        .map((log) => {
          const levelPrefix = log.level === "error" ? "[ERROR]" : log.level === "warn" ? "[WARN]" : "[INFO]";
          return `${levelPrefix} ${log.timestamp}\n${log.message}\n`;
        })
        .join("\n");

      const header = recentOnly ? "=== outlabsAuth Debug Logs (Recent 20) ===" : "=== outlabsAuth Debug Logs (All) ===";
      const fullText = `${header}\nTotal logs: ${logsToCopy.length}\nCopied at: ${new Date().toISOString()}\n\n${logText}`;

      await navigator.clipboard.writeText(fullText);
      toast.success(`Copied ${logsToCopy.length} logs to clipboard!`);
    } catch (error) {
      toast.error("Failed to copy logs to clipboard");
      console.error("Copy failed:", error);
    }
  };

  return (
    <Card className='w-full max-w-6xl relative'>
      {/* Always visible sticky header */}
      <div className='sticky top-0 z-10 bg-white dark:bg-gray-950 border-b p-4 rounded-t-lg'>
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <span className='text-sm font-medium'>Debug Console</span>
            {debugModeEnabled && (
              <Badge variant='secondary' className='text-xs'>
                Active
              </Badge>
            )}
          </div>
          <div className='flex items-center gap-2'>
            {isCollapsed && logs.length > 0 && (
              <Badge variant='outline' className='text-xs'>
                {logs.length} logs
              </Badge>
            )}
            <Button variant='ghost' size='sm' onClick={() => setIsCollapsed(!isCollapsed)} className='h-6 w-6 p-0'>
              <span className='text-sm'>{isCollapsed ? "▶" : "▼"}</span>
            </Button>
          </div>
        </div>
      </div>

      {!isCollapsed && (
        <CardContent className='space-y-4 max-h-96 overflow-y-auto'>
          {/* Debug Mode Status */}
          {debugModeEnabled && (
            <div className='p-3 bg-yellow-100 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800'>
              <div className='text-sm font-medium text-yellow-800 dark:text-yellow-200 flex items-center gap-2'>
                <AlertTriangle className='h-4 w-4' />
                Debug Mode Active
              </div>
              <div className='text-xs text-yellow-700 dark:text-yellow-300 mt-1'>Automatic logout is disabled. Toggle debug mode in the user menu (top right).</div>
            </div>
          )}

          {/* Authentication Status */}
          <div className='flex items-center gap-2'>
            <span>Status:</span>
            <Badge variant={isAuthenticated ? "default" : "destructive"}>{isAuthenticated ? "Authenticated" : "Not Authenticated"}</Badge>
            {isRefreshing && <Badge variant='secondary'>Refreshing...</Badge>}
          </div>

          {/* User Info */}
          {user && (
            <div>
              <strong>User:</strong> {user.email} ({user.first_name} {user.last_name})
            </div>
          )}

          {/* Token Info */}
          {tokenInfo && (
            <div className='space-y-2'>
              <div>
                <strong>Token expires:</strong> {tokenInfo.expiresAt}
              </div>
              <div>
                <strong>Token issued:</strong> {tokenInfo.issued}
              </div>
              <div>
                <strong>Subject:</strong> {tokenInfo.subject}
              </div>
              <div>
                <strong>Time until expiry:</strong> {tokenInfo.timeUntilExpiryMinutes}m {tokenInfo.timeUntilExpirySeconds}s
              </div>
              <div className='flex items-center gap-2'>
                <span>Token status:</span>
                <Badge variant={isTokenExpired() ? "destructive" : isTokenExpiringSoon() ? "secondary" : "default"}>
                  {isTokenExpired() ? "Expired" : isTokenExpiringSoon() ? "Expiring Soon" : "Valid"}
                </Badge>
              </div>
            </div>
          )}

          {/* Tokens */}
          {tokens && (
            <div className='space-y-2'>
              <div>
                <strong>Access Token (first 50 chars):</strong>
                <code className='block mt-1 p-2 bg-gray-100 dark:bg-gray-800 rounded text-xs break-all'>{tokens.access_token.substring(0, 50)}...</code>
              </div>
              <div>
                <strong>Refresh Token:</strong>
                <code className='block mt-1 p-2 bg-gray-100 dark:bg-gray-800 rounded text-xs break-all'>🔒 HTTP-only cookie (not accessible to JavaScript)</code>
              </div>
            </div>
          )}

          {/* Test Actions */}
          <div className='flex gap-2 flex-wrap'>
            <Button onClick={() => testApiConnectivity.mutate()} disabled={testApiConnectivity.isPending} variant='outline'>
              {testApiConnectivity.isPending ? "Testing..." : "Test API Connection"}
            </Button>

            <Button onClick={() => testRefreshEndpoint.mutate()} disabled={testRefreshEndpoint.isPending} variant='outline'>
              {testRefreshEndpoint.isPending ? "Testing..." : "Test Refresh Endpoint"}
            </Button>

            <Button onClick={() => testRealRefreshToken.mutate()} disabled={testRealRefreshToken.isPending || !isAuthenticated} variant='outline'>
              {testRealRefreshToken.isPending ? "Testing..." : "Test Real Refresh Cookie"}
            </Button>

            <Button onClick={() => testApiCall.mutate()} disabled={testApiCall.isPending} variant='outline'>
              {testApiCall.isPending ? "Testing..." : "Test API Call"}
            </Button>

            <Button onClick={() => testExpiredTokenCall.mutate()} disabled={testExpiredTokenCall.isPending} variant='outline'>
              {testExpiredTokenCall.isPending ? "Testing..." : "Test Expired Token"}
            </Button>

            <Button onClick={() => forceRefresh.mutate()} disabled={forceRefresh.isPending || isRefreshing} variant='outline'>
              {forceRefresh.isPending ? "Refreshing..." : "Force Refresh"}
            </Button>

            <Button onClick={handleLogout} variant='destructive'>
              Logout
            </Button>

            <Button onClick={() => setShowLogs(!showLogs)} variant='outline'>
              {showLogs ? "Hide" : "Show"} Logs ({logs.length})
            </Button>

            <Button
              onClick={() => {
                debugLogger.clearLogs();
                setLogs([]);
                toast.success("Debug logs cleared");
              }}
              variant='outline'
            >
              Clear Logs
            </Button>

            <Button onClick={() => copyLogsToClipboard(true)} variant='outline' disabled={logs.length === 0}>
              <Copy className='w-4 h-4 mr-2' />
              Copy Recent (20)
            </Button>

            <Button onClick={() => copyLogsToClipboard(false)} variant='outline' disabled={logs.length === 0}>
              <Copy className='w-4 h-4 mr-2' />
              Copy All Logs
            </Button>
          </div>

          {/* Debug Logs */}
          {showLogs && (
            <Card>
              <CardHeader>
                <CardTitle className='flex items-center justify-between'>
                  <span>Debug Logs (Persistent)</span>
                  <Button onClick={() => copyLogsToClipboard(false)} variant='outline' size='sm' className='ml-2' disabled={logs.length === 0}>
                    <Copy className='w-4 h-4 mr-2' />
                    Copy All ({logs.length})
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className='h-64'>
                  <div className='space-y-1'>
                    {logs.length === 0 ? (
                      <div className='text-sm text-gray-500'>No logs yet</div>
                    ) : (
                      logs.slice(-50).map((log, index) => (
                        <div
                          key={index}
                          className={`text-xs p-2 rounded ${
                            log.level === "error"
                              ? "bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-200"
                              : log.level === "warn"
                                ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200"
                                : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
                          }`}
                        >
                          <div className='flex items-start gap-2'>
                            <div className='flex-shrink-0 mt-0.5'>
                              {log.level === "error" ? <AlertCircle className='h-3 w-3' /> : log.level === "warn" ? <AlertTriangle className='h-3 w-3' /> : <Info className='h-3 w-3' />}
                            </div>
                            <div className='flex-1'>
                              <span className='font-mono'>{log.timestamp}</span>
                              <br />
                              <span>{log.message}</span>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          )}

          {/* Console Log Info */}
          <div className='mt-4 p-3 bg-gray-100 dark:bg-gray-800 rounded'>
            <div className='text-sm font-medium mb-2'>Debug Information:</div>
            <div className='text-xs text-gray-600 dark:text-gray-400'>
              <div>• Toggle debug mode in the user menu (click your profile picture)</div>
              <div>• All auth logs are captured and persist across logout</div>
              <div>• Look for [auth store], [refresh], [fetch], [timing], [debug] prefixes in logs</div>
              <div>• Use "Show Logs" to see persistent debug history</div>
              <div>
                • <strong>Copy logs:</strong> Use "Copy Recent (20)" or "Copy All Logs" to share debug info
              </div>
              <div>
                • <strong>Debug Token Refresh Issues (Cookie-based):</strong>
                <div className='ml-4 mt-1'>
                  1. Test "API Connection" - ensure backend is running
                  <br />
                  2. Test "Refresh Endpoint" - verify endpoint responds (should fail without cookie)
                  <br />
                  3. Test "Real Refresh Cookie" - test endpoint with your actual HTTP-only cookie
                  <br />
                  4. Try "Force Refresh" - test full refresh flow through auth store
                  <br />
                  5. Copy and share logs to get help with debugging
                  <br />
                  <strong>Note:</strong> Refresh tokens are now HTTP-only cookies (not accessible to JavaScript)
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

// Re-export useAuthStore for testing
import { useAuthStore } from "@/stores/auth-store";
export { useAuthStore };
