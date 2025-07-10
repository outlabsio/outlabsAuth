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
      const response = await authenticatedFetch("/auth/me");
      return response.json();
    },
    onSuccess: (data) => {
      toast.success("API call successful!");
      console.log("API Response:", data);
    },
    onError: (error: any) => {
      toast.error(`API call failed: ${error.message}`);
      console.error("API Error:", error);
    },
  });

  // Get token expiry info
  const getTokenInfo = () => {
    const token = getAccessToken();
    if (!token) return null;

    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const currentTime = Date.now() / 1000;
      const timeUntilExpiry = payload.exp - currentTime;

      return {
        exp: payload.exp,
        currentTime,
        timeUntilExpiry,
        expiresAt: new Date(payload.exp * 1000).toLocaleString(),
        timeUntilExpiryMinutes: Math.floor(timeUntilExpiry / 60),
      };
    } catch {
      return null;
    }
  };

  const tokenInfo = getTokenInfo();

  return (
    <Card className='w-full max-w-2xl'>
      <CardHeader>
        <CardTitle>Authentication Debug</CardTitle>
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
              <strong>Time until expiry:</strong> {tokenInfo.timeUntilExpiryMinutes} minutes
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
              <strong>Access Token:</strong>
              <code className='block mt-1 p-2 bg-gray-100 rounded text-xs break-all'>{tokens.access_token.substring(0, 50)}...</code>
            </div>
            <div>
              <strong>Refresh Token:</strong>
              <code className='block mt-1 p-2 bg-gray-100 rounded text-xs break-all'>{tokens.refresh_token.substring(0, 50)}...</code>
            </div>
          </div>
        )}

        {/* Test Actions */}
        <div className='flex gap-2'>
          <Button onClick={() => testApiCall.mutate()} disabled={testApiCall.isPending} variant='outline'>
            {testApiCall.isPending ? "Testing..." : "Test API Call"}
          </Button>
          <Button onClick={logout} variant='destructive'>
            Logout
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
