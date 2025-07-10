import { useAuth } from "@/hooks/use-auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { authenticatedFetch } from "@/lib/auth";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

export function AuthDebug() {
  const { isAuthenticated, isRefreshing, user, tokens, getAccessToken, isTokenExpired, isTokenExpiringSoon, logout } = useAuth();

  // Test API call mutation
  const testApiCall = useMutation({
    mutationFn: async () => {
      console.log("🧪 AUTH DEBUG: Testing API call to /auth/me");
      const response = await authenticatedFetch("/auth/me");
      return response.json();
    },
    onSuccess: (data) => {
      console.log("🧪 AUTH DEBUG: API call successful:", data);
      toast.success("API call successful!");
    },
    onError: (error: any) => {
      console.error("🧪 AUTH DEBUG: API call failed:", error);
      toast.error(`API call failed: ${error.message}`);
    },
  });

  // Test expired token call mutation
  const testExpiredTokenCall = useMutation({
    mutationFn: async () => {
      console.log("🧪 AUTH DEBUG: Testing API call with fake expired token");
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
      console.log("🧪 AUTH DEBUG: Expired token test successful (unexpected):", data);
      toast.success("Expired token test successful (unexpected)!");
    },
    onError: (error: any) => {
      console.error("🧪 AUTH DEBUG: Expired token test failed (expected):", error);
      toast.error(`Expired token test failed (expected): ${error.message}`);
    },
  });

  // Force token refresh mutation
  const forceRefresh = useMutation({
    mutationFn: async () => {
      console.log("🧪 AUTH DEBUG: Forcing token refresh");
      const store = useAuthStore.getState();
      await store.refreshTokens();
    },
    onSuccess: () => {
      console.log("🧪 AUTH DEBUG: Force refresh successful");
      toast.success("Token refresh successful!");
    },
    onError: (error: any) => {
      console.error("🧪 AUTH DEBUG: Force refresh failed:", error);
      toast.error(`Token refresh failed: ${error.message}`);
    },
  });

  // Get token expiry info
  const getTokenInfo = () => {
    const token = getAccessToken();
    if (!token) {
      console.log("🧪 AUTH DEBUG: No token available for info");
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

      console.log("🧪 AUTH DEBUG: Token info:", info);
      return info;
    } catch (error) {
      console.error("🧪 AUTH DEBUG: Error parsing token:", error);
      return null;
    }
  };

  const tokenInfo = getTokenInfo();

  return (
    <Card className='w-full max-w-4xl'>
      <CardHeader>
        <CardTitle>Authentication Debug Console</CardTitle>
      </CardHeader>
      <CardContent className='space-y-4'>
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

          <Button
            onClick={() => {
              console.log("🧪 AUTH DEBUG: Manual logout triggered");
              logout();
            }}
            variant='destructive'
          >
            Logout
          </Button>
        </div>

        {/* Console Log Info */}
        <div className='mt-4 p-3 bg-gray-100 dark:bg-gray-800 rounded'>
          <div className='text-sm font-medium mb-2'>Debug Information:</div>
          <div className='text-xs text-gray-600 dark:text-gray-400'>
            <div>• Check browser console for detailed logs</div>
            <div>• Look for 🔐 (auth store), 🔄 (refresh), 🌐 (fetch), 🕒 (timing), 🧪 (debug) emojis</div>
            <div>• All token operations are logged with timestamps</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Re-export useAuthStore for testing
import { useAuthStore } from "@/stores/auth-store";
export { useAuthStore };
