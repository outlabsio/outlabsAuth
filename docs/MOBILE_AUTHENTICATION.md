# Mobile & Native Application Authentication

## Overview

While web applications can use secure HttpOnly cookies for authentication, mobile and native applications require a different approach. This document outlines secure authentication patterns for non-browser clients including iOS, Android, Flutter, and desktop applications.

## Authentication Flows

### 1. Token-Based Authentication for Native Apps

Native applications cannot use HttpOnly cookies effectively. Instead, they receive tokens in the response body and must store them securely using platform-specific secure storage.

#### Login Request

```http
POST /v1/auth/login
Content-Type: application/json
X-Client-Type: mobile  # Identifies this as a mobile client

{
  "email": "user@example.com",
  "password": "secure_password",
  "platform_id": "plat_diverse_leads"
}
```

#### Login Response (Mobile)

```json
{
  "user": {
    "id": "user_123",
    "email": "user@example.com",
    "profile": {
      "first_name": "Maria",
      "last_name": "Garcia"
    }
  },
  "tokens": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh_token": "f47c4d3b-1a2e-4e3d-9f6a...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

### 2. Secure Token Storage

#### iOS (Swift)

```swift
import Security

class TokenManager {
    static let shared = TokenManager()
    
    func saveTokens(access: String, refresh: String) {
        // Save to iOS Keychain
        let accessData = access.data(using: .utf8)!
        let refreshData = refresh.data(using: .utf8)!
        
        let accessQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: "access_token",
            kSecValueData as String: accessData
        ]
        
        let refreshQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: "refresh_token",
            kSecValueData as String: refreshData
        ]
        
        SecItemAdd(accessQuery as CFDictionary, nil)
        SecItemAdd(refreshQuery as CFDictionary, nil)
    }
    
    func getAccessToken() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: "access_token",
            kSecReturnData as String: true
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        if status == errSecSuccess,
           let data = result as? Data,
           let token = String(data: data, encoding: .utf8) {
            return token
        }
        return nil
    }
}
```

#### Android (Kotlin)

```kotlin
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys

class TokenManager(context: Context) {
    private val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
    
    private val sharedPreferences = EncryptedSharedPreferences.create(
        "secure_prefs",
        masterKeyAlias,
        context,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
    
    fun saveTokens(accessToken: String, refreshToken: String) {
        sharedPreferences.edit().apply {
            putString("access_token", accessToken)
            putString("refresh_token", refreshToken)
            apply()
        }
    }
    
    fun getAccessToken(): String? {
        return sharedPreferences.getString("access_token", null)
    }
}
```

#### Flutter

```dart
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenManager {
  static const _storage = FlutterSecureStorage();
  
  static Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(key: 'access_token', value: accessToken);
    await _storage.write(key: 'refresh_token', value: refreshToken);
  }
  
  static Future<String?> getAccessToken() async {
    return await _storage.read(key: 'access_token');
  }
  
  static Future<void> deleteTokens() async {
    await _storage.deleteAll();
  }
}
```

### 3. Making Authenticated Requests

Mobile clients must include the access token in the Authorization header for all authenticated requests.

#### Flutter Example

```dart
class AuthenticatedApiClient {
  final String baseUrl;
  final TokenManager tokenManager;
  
  AuthenticatedApiClient({required this.baseUrl, required this.tokenManager});
  
  Future<http.Response> authenticatedRequest(
    String endpoint, {
    String method = 'GET',
    Map<String, dynamic>? body,
  }) async {
    String? accessToken = await TokenManager.getAccessToken();
    
    if (accessToken == null) {
      throw Exception('No access token available');
    }
    
    final headers = {
      'Authorization': 'Bearer $accessToken',
      'Content-Type': 'application/json',
    };
    
    final uri = Uri.parse('$baseUrl$endpoint');
    
    switch (method) {
      case 'GET':
        return await http.get(uri, headers: headers);
      case 'POST':
        return await http.post(
          uri,
          headers: headers,
          body: body != null ? json.encode(body) : null,
        );
      // ... other methods
    }
  }
  
  Future<void> refreshToken() async {
    String? refreshToken = await TokenManager.getRefreshToken();
    
    if (refreshToken == null) {
      throw Exception('No refresh token available');
    }
    
    final response = await http.post(
      Uri.parse('$baseUrl/v1/auth/refresh'),
      headers: {
        'Content-Type': 'application/json',
        'X-Client-Type': 'mobile',
      },
      body: json.encode({'refresh_token': refreshToken}),
    );
    
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      await TokenManager.saveTokens(
        accessToken: data['access_token'],
        refreshToken: data['refresh_token'], // New refresh token
      );
    } else {
      // Handle refresh failure - user must login again
      await TokenManager.deleteTokens();
      throw Exception('Token refresh failed');
    }
  }
}
```

### 4. Token Refresh with Rotation

Mobile apps implement refresh token rotation for enhanced security:

```python
# Backend implementation
@router.post("/v1/auth/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    client_type: str = Header(None, alias="X-Client-Type")
):
    # Validate the refresh token
    old_refresh_token = await validate_refresh_token(request.refresh_token)
    
    if not old_refresh_token:
        raise HTTPException(401, "Invalid refresh token")
    
    # Invalidate the old refresh token (one-time use)
    await revoke_refresh_token(request.refresh_token)
    
    # Generate new tokens
    new_access_token = create_access_token(old_refresh_token.user_id)
    new_refresh_token = create_refresh_token(old_refresh_token.user_id)
    
    # Store the new refresh token
    await store_refresh_token(new_refresh_token, old_refresh_token.user_id)
    
    if client_type == "mobile":
        # Return tokens in body for mobile clients
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 900
        }
    else:
        # Set cookies for web clients
        response = Response()
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=900
        )
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=2592000
        )
        return response
```

### 5. Security Best Practices for Mobile

#### Token Expiration Handling

```dart
class TokenInterceptor {
  final TokenManager tokenManager;
  final AuthService authService;
  
  Future<http.Response> intercept(Future<http.Response> request) async {
    try {
      final response = await request;
      
      if (response.statusCode == 401) {
        // Token expired, try to refresh
        await authService.refreshToken();
        
        // Retry the original request with new token
        return await retryRequest(request);
      }
      
      return response;
    } catch (e) {
      // Network error or other issue
      throw e;
    }
  }
}
```

#### Biometric Authentication

```swift
// iOS - Face ID / Touch ID
import LocalAuthentication

class BiometricAuth {
    static func authenticate(completion: @escaping (Bool) -> Void) {
        let context = LAContext()
        var error: NSError?
        
        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: "Access your secure data"
            ) { success, error in
                DispatchQueue.main.async {
                    completion(success)
                }
            }
        } else {
            completion(false)
        }
    }
}

// Use before accessing tokens
BiometricAuth.authenticate { success in
    if success {
        let token = TokenManager.shared.getAccessToken()
        // Use token
    }
}
```

### 6. Advanced: PKCE Flow (Recommended for Public Clients)

For maximum security, implement the OAuth 2.0 PKCE (Proof Key for Code Exchange) flow:

```dart
import 'dart:convert';
import 'dart:math';
import 'package:crypto/crypto.dart';

class PKCEFlow {
  static String _generateCodeVerifier() {
    final random = Random.secure();
    final bytes = List<int>.generate(32, (_) => random.nextInt(256));
    return base64Url.encode(bytes).replaceAll('=', '');
  }
  
  static String _generateCodeChallenge(String verifier) {
    final bytes = utf8.encode(verifier);
    final digest = sha256.convert(bytes);
    return base64Url.encode(digest.bytes).replaceAll('=', '');
  }
  
  static Future<AuthTokens> authenticate() async {
    // 1. Generate PKCE parameters
    final codeVerifier = _generateCodeVerifier();
    final codeChallenge = _generateCodeChallenge(codeVerifier);
    
    // 2. Redirect to authorization endpoint
    final authUrl = Uri.parse('https://auth.outlabs.com/authorize').replace(
      queryParameters: {
        'client_id': 'mobile_app',
        'redirect_uri': 'outlabsauth://callback',
        'response_type': 'code',
        'code_challenge': codeChallenge,
        'code_challenge_method': 'S256',
      },
    );
    
    // 3. Open in-app browser or external browser
    final authCode = await launchAuthFlow(authUrl);
    
    // 4. Exchange code for tokens
    final tokenResponse = await http.post(
      Uri.parse('https://api.auth.outlabs.com/v1/auth/token'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'grant_type': 'authorization_code',
        'code': authCode,
        'redirect_uri': 'outlabsauth://callback',
        'code_verifier': codeVerifier,
      }),
    );
    
    return AuthTokens.fromJson(json.decode(tokenResponse.body));
  }
}
```

## Client Detection Strategy

The backend can detect mobile clients through multiple methods:

```python
from fastapi import Header, Request
from typing import Optional

def detect_client_type(
    user_agent: Optional[str] = Header(None),
    x_client_type: Optional[str] = Header(None),
    request: Request = None
) -> str:
    # 1. Explicit client type header (preferred)
    if x_client_type:
        return x_client_type
    
    # 2. User-Agent parsing
    if user_agent:
        mobile_patterns = [
            'iOS', 'Android', 'iPhone', 'iPad',
            'Mobile', 'Flutter', 'React Native'
        ]
        if any(pattern in user_agent for pattern in mobile_patterns):
            return 'mobile'
    
    # 3. Check for specific mobile headers
    if 'X-Requested-With' in request.headers:
        return 'mobile'
    
    return 'web'
```

## Security Checklist for Mobile Apps

- [ ] Use platform-specific secure storage (Keychain/Keystore)
- [ ] Implement certificate pinning for API calls
- [ ] Use biometric authentication for sensitive operations
- [ ] Implement token refresh with rotation
- [ ] Handle token expiration gracefully
- [ ] Clear tokens on logout
- [ ] Implement jailbreak/root detection
- [ ] Use obfuscation for production builds
- [ ] Implement app attestation (iOS) / SafetyNet (Android)
- [ ] Monitor for abnormal token usage patterns

## Migration from Web to Mobile

For platforms supporting both web and mobile:

1. **Dual Authentication Endpoints**: The same endpoints support both patterns based on client detection
2. **Consistent User Experience**: Users can switch between web and mobile seamlessly
3. **Token Sharing**: Tokens are valid across all client types
4. **Security Isolation**: Compromise of one client doesn't affect others

This approach ensures that outlabsAuth can securely support any client type while maintaining the highest security standards for each platform.