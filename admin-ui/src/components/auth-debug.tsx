import { useAuth } from "@/hooks/use-auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { authenticatedFetch } from "@/lib/auth";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";

// Persistent debug logger
class DebugLogger {
  private static instance: DebugLogger;
  private logs: Array<{ timestamp: string; message: string; level: "info" | "error" | "warn" }> = [];
  private maxLogs = 1000;

  static getInstance(): DebugLogger {
    if (!DebugLogger.instance) {
      DebugLogger.instance = new DebugLogger();
    }
    return DebugLogger.instance;
  }

  log(message: string, level: "info" | "error" | "warn" = "info") {
    const timestamp = new Date().toISOString();
    const logEntry = { timestamp, message, level };

    this.logs.push(logEntry);

    // Keep only the last N logs
    if (this.logs.length > this.maxLogs) {
      this.logs = this.logs.slice(-this.maxLogs);
    }

    // Store in localStorage
    localStorage.setItem("auth-debug-logs", JSON.stringify(this.logs));

    // Also log to console
    console.log(`🔍 [${timestamp}] ${message}`);
  }

  getLogs() {
    return this.logs;
  }

  loadLogs() {
    try {
      const stored = localStorage.getItem("auth-debug-logs");
      if (stored) {
        this.logs = JSON.parse(stored);
      }
    } catch (e) {
      console.error("Failed to load debug logs:", e);
    }
  }

  clearLogs() {
    this.logs = [];
    localStorage.removeItem("auth-debug-logs");
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

console.log = (...args) => {
  originalConsoleLog(...args);
  if (debugMode && args[0]?.includes && (args[0].includes("🔐") || args[0].includes("🔄") || args[0].includes("🌐") || args[0].includes("🕒") || args[0].includes("🧪"))) {
    debugLogger.log(args.join(" "), "info");
  }
};

console.error = (...args) => {
  originalConsoleError(...args);
  if (debugMode && args[0]?.includes && (args[0].includes("🔐") || args[0].includes("🔄") || args[0].includes("🌐") || args[0].includes("🕒") || args[0].includes("🧪"))) {
    debugLogger.log(args.join(" "), "error");
  }
};

console.warn = (...args) => {
  originalConsoleWarn(...args);
  if (debugMode && args[0]?.includes && (args[0].includes("🔐") || args[0].includes("🔄") || args[0].includes("🌐") || args[0].includes("🕒") || args[0].includes("🧪"))) {
    debugLogger.log(args.join(" "), "warn");
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
  const [debugModeEnabled, setDebugModeEnabledState] = useState(getDebugMode());

  useEffect(() => {
    debugLogger.loadLogs();
    setLogs(debugLogger.getLogs());

    // Check debug mode from localStorage
    const currentDebugMode = getDebugMode();
    setDebugModeEnabledState(currentDebugMode);
    setDebugMode(currentDebugMode);

    // Update logs periodically
    const interval = setInterval(() => {
      setLogs([...debugLogger.getLogs()]);
      // Also check if debug mode changed
      const newDebugMode = getDebugMode();
      if (newDebugMode !== debugModeEnabled) {
        setDebugModeEnabledState(newDebugMode);
        setDebugMode(newDebugMode);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Test API call mutation
  const testApiCall = useMutation({
    mutationFn: async () => {
      debugLogger.log("🧪 AUTH DEBUG: Testing API call to /auth/me", "info");
      const response = await authenticatedFetch("/auth/me");
      return response.json();
    },
    onSuccess: (data) => {
      debugLogger.log("🧪 AUTH DEBUG: API call successful: " + JSON.stringify(data), "info");
      toast.success("API call successful!");
    },
    onError: (error: any) => {
      debugLogger.log("🧪 AUTH DEBUG: API call failed: " + error.message, "error");
      toast.error(`API call failed: ${error.message}`);
    },
  });

  // Test expired token call mutation
  const testExpiredTokenCall = useMutation({
    mutationFn: async () => {
      debugLogger.log("🧪 AUTH DEBUG: Testing API call with fake expired token", "info");
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
      debugLogger.log("🧪 AUTH DEBUG: Expired token test successful (unexpected): " + JSON.stringify(data), "info");
      toast.success("Expired token test successful (unexpected)!");
    },
    onError: (error: any) => {
      debugLogger.log("🧪 AUTH DEBUG: Expired token test failed (expected): " + error.message, "error");
      toast.error(`Expired token test failed (expected): ${error.message}`);
    },
  });

  // Force token refresh mutation
  const forceRefresh = useMutation({
    mutationFn: async () => {
      debugLogger.log("🧪 AUTH DEBUG: Forcing token refresh", "info");
      const store = useAuthStore.getState();
      await store.refreshTokens();
    },
    onSuccess: () => {
      debugLogger.log("🧪 AUTH DEBUG: Force refresh successful", "info");
      toast.success("Token refresh successful!");
    },
    onError: (error: any) => {
      debugLogger.log("🧪 AUTH DEBUG: Force refresh failed: " + error.message, "error");
      toast.error(`Token refresh failed: ${error.message}`);
    },
  });

  // Get token expiry info
  const getTokenInfo = () => {
    const token = getAccessToken();
    if (!token) {
      debugLogger.log("🧪 AUTH DEBUG: No token available for info", "warn");
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

      debugLogger.log("🧪 AUTH DEBUG: Token info: " + JSON.stringify(info), "info");
      return info;
    } catch (error) {
      debugLogger.log("🧪 AUTH DEBUG: Error parsing token: " + error, "error");
      return null;
    }
  };

  const tokenInfo = getTokenInfo();

  const handleLogout = () => {
    debugLogger.log("🧪 AUTH DEBUG: Manual logout triggered", "info");
    if (debugModeEnabled) {
      debugLogger.log("🧪 AUTH DEBUG: Debug mode enabled - preventing automatic redirect", "warn");
      // In debug mode, just clear auth but don't redirect
      const store = useAuthStore.getState();
      store.clearAuth();
      toast.error("Logout called (debug mode - no redirect)");
    } else {
      logout();
    }
  };

  return (
    <Card className='w-full max-w-6xl'>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          Authentication Debug Console
          {debugModeEnabled && <Badge variant='secondary'>Debug Mode Active</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className='space-y-4'>
        {/* Debug Mode Status */}
        {debugModeEnabled && (
          <div className='p-3 bg-yellow-100 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800'>
            <div className='text-sm font-medium text-yellow-800 dark:text-yellow-200'>🐛 Debug Mode Active</div>
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
              <strong>Refresh Token (first 50 chars):</strong>
              <code className='block mt-1 p-2 bg-gray-100 dark:bg-gray-800 rounded text-xs break-all'>{tokens.refresh_token.substring(0, 50)}...</code>
            </div>
          </div>
        )}

        {/* Test Actions */}
        <div className='flex gap-2 flex-wrap'>
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
        </div>

        {/* Debug Logs */}
        {showLogs && (
          <Card>
            <CardHeader>
              <CardTitle>Debug Logs (Persistent)</CardTitle>
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
                        <span className='font-mono'>{log.timestamp}</span>
                        <br />
                        <span>{log.message}</span>
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
            <div>• Look for 🔐 (auth store), 🔄 (refresh), 🌐 (fetch), 🕒 (timing), 🧪 (debug) emojis</div>
            <div>• Use "Show Logs" to see persistent debug history</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Re-export useAuthStore for testing
import { useAuthStore } from "@/stores/auth-store";
export { useAuthStore };
