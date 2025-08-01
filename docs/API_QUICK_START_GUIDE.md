# API Quick Start Guide

Get up and running with OutlabsAuth in minutes. This guide provides practical code examples in multiple languages to help you integrate authentication into your application quickly.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start Examples](#quick-start-examples)
3. [Authentication Flows](#authentication-flows)
4. [Common Operations](#common-operations)
5. [SDK Examples](#sdk-examples)
6. [Testing with Postman](#testing-with-postman)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, you'll need:

1. **API Endpoint**: 
   - Production: `https://api.auth.outlabs.com`
   - Development: `http://localhost:8030`

2. **Credentials**:
   - For testing: Email: `system@outlabs.io`, Password: `Asd123$$$`
   - For production: Your platform credentials

3. **Development Tools**:
   - HTTP client (curl, Postman, or your language's HTTP library)
   - JSON parser for handling responses

## Quick Start Examples

### 1. Simple Login (JavaScript)

```javascript
// Quick login example
async function login(email, password) {
  const response = await fetch('https://api.auth.outlabs.com/v1/auth/login/json', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  
  if (!response.ok) {
    throw new Error('Login failed');
  }
  
  const { access_token, refresh_token } = await response.json();
  console.log('Login successful!');
  
  return { access_token, refresh_token };
}

// Usage
const tokens = await login('user@example.com', 'SecurePassword123!');
```

### 2. Making Authenticated Requests (Python)

```python
import requests

class OutlabsAuthClient:
    def __init__(self, base_url="https://api.auth.outlabs.com"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
    
    def login(self, email, password):
        """Login and store tokens"""
        response = requests.post(
            f"{self.base_url}/v1/auth/login/json",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        
        data = response.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        return data
    
    def get_current_user(self):
        """Get current user information"""
        response = requests.get(
            f"{self.base_url}/v1/auth/me",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = OutlabsAuthClient()
client.login("user@example.com", "SecurePassword123!")
user_info = client.get_current_user()
print(f"Logged in as: {user_info['email']}")
```

### 3. Token Refresh (PHP)

```php
<?php
class OutlabsAuth {
    private $baseUrl;
    private $accessToken;
    private $refreshToken;
    
    public function __construct($baseUrl = "https://api.auth.outlabs.com") {
        $this->baseUrl = $baseUrl;
    }
    
    public function login($email, $password) {
        $response = $this->request('POST', '/v1/auth/login/json', [
            'email' => $email,
            'password' => $password
        ]);
        
        $this->accessToken = $response['access_token'];
        $this->refreshToken = $response['refresh_token'];
        
        return $response;
    }
    
    public function refreshAccessToken() {
        $response = $this->request('POST', '/v1/auth/mobile/refresh', [
            'refresh_token' => $this->refreshToken
        ]);
        
        $this->accessToken = $response['access_token'];
        $this->refreshToken = $response['refresh_token'];
        
        return $response;
    }
    
    private function request($method, $endpoint, $data = null) {
        $ch = curl_init($this->baseUrl . $endpoint);
        
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $method);
        
        $headers = ['Content-Type: application/json'];
        if ($this->accessToken && $method !== 'POST' || !str_contains($endpoint, 'auth')) {
            $headers[] = 'Authorization: Bearer ' . $this->accessToken;
        }
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        
        if ($data) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($httpCode >= 400) {
            throw new Exception("API Error: HTTP $httpCode");
        }
        
        return json_decode($response, true);
    }
}

// Usage
$auth = new OutlabsAuth();
$auth->login("user@example.com", "SecurePassword123!");
$user = $auth->request('GET', '/v1/auth/me');
echo "Logged in as: " . $user['email'];
?>
```

### 4. Permission Checking (C#/.NET)

```csharp
using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

public class OutlabsAuthClient
{
    private readonly HttpClient _httpClient;
    private string _accessToken;
    private string _refreshToken;
    
    public OutlabsAuthClient(string baseUrl = "https://api.auth.outlabs.com")
    {
        _httpClient = new HttpClient { BaseAddress = new Uri(baseUrl) };
    }
    
    public async Task<LoginResponse> LoginAsync(string email, string password)
    {
        var loginData = new { email, password };
        var json = JsonSerializer.Serialize(loginData);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        var response = await _httpClient.PostAsync("/v1/auth/login/json", content);
        response.EnsureSuccessStatusCode();
        
        var responseData = await response.Content.ReadAsStringAsync();
        var loginResponse = JsonSerializer.Deserialize<LoginResponse>(responseData);
        
        _accessToken = loginResponse.AccessToken;
        _refreshToken = loginResponse.RefreshToken;
        
        return loginResponse;
    }
    
    public async Task<bool> CheckPermissionAsync(string permission, string entityId = null)
    {
        _httpClient.DefaultRequestHeaders.Authorization = 
            new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", _accessToken);
        
        var checkData = new 
        { 
            permission = permission,
            entity_id = entityId
        };
        
        var json = JsonSerializer.Serialize(checkData);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        var response = await _httpClient.PostAsync("/v1/permissions/check", content);
        if (!response.IsSuccessStatusCode) return false;
        
        var responseData = await response.Content.ReadAsStringAsync();
        var result = JsonSerializer.Deserialize<PermissionCheckResult>(responseData);
        
        return result.Allowed;
    }
}

// Usage
var client = new OutlabsAuthClient();
await client.LoginAsync("user@example.com", "SecurePassword123!");
bool canCreateUsers = await client.CheckPermissionAsync("user:create");
Console.WriteLine($"Can create users: {canCreateUsers}");
```

## Authentication Flows

### Web Application Flow

```javascript
// 1. Login and let OutlabsAuth set HTTP-only cookies
async function webLogin(email, password) {
  const response = await fetch('/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    credentials: 'include', // Important for cookies
    body: new URLSearchParams({ username: email, password })
  });
  
  const data = await response.json();
  // Access token in response, refresh token in HTTP-only cookie
  return data;
}

// 2. Make authenticated requests
async function getProfile() {
  const response = await fetch('/v1/auth/me', {
    credentials: 'include' // Sends cookies automatically
  });
  
  return response.json();
}

// 3. Refresh token automatically via cookies
async function refreshToken() {
  const response = await fetch('/v1/auth/refresh', {
    method: 'POST',
    credentials: 'include'
  });
  
  return response.json();
}
```

### Mobile Application Flow

```swift
// iOS Swift Example
import Foundation

class OutlabsAuthService {
    static let shared = OutlabsAuthService()
    private let baseURL = "https://api.auth.outlabs.com"
    private var accessToken: String?
    private var refreshToken: String?
    
    func login(email: String, password: String) async throws -> User {
        let url = URL(string: "\(baseURL)/v1/auth/mobile/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["email": email, "password": password]
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        let response = try JSONDecoder().decode(LoginResponse.self, from: data)
        
        // Store tokens securely in Keychain
        self.accessToken = response.accessToken
        self.refreshToken = response.refreshToken
        KeychainHelper.save("access_token", response.accessToken)
        KeychainHelper.save("refresh_token", response.refreshToken)
        
        return response.user
    }
    
    func makeAuthenticatedRequest<T: Decodable>(
        endpoint: String,
        method: String = "GET",
        body: Encodable? = nil
    ) async throws -> T {
        let url = URL(string: "\(baseURL)\(endpoint)")!
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer \(accessToken ?? "")", forHTTPHeaderField: "Authorization")
        
        if let body = body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try JSONEncoder().encode(body)
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // Handle token refresh if needed
        if let httpResponse = response as? HTTPURLResponse,
           httpResponse.statusCode == 401 {
            try await refreshAccessToken()
            return try await makeAuthenticatedRequest(endpoint: endpoint, method: method, body: body)
        }
        
        return try JSONDecoder().decode(T.self, from: data)
    }
}
```

## Common Operations

### 1. User Registration

```javascript
async function registerUser(userData) {
  const response = await fetch('https://api.auth.outlabs.com/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: userData.email,
      password: userData.password,
      first_name: userData.firstName,
      last_name: userData.lastName,
      phone: userData.phone
    })
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Registration failed');
  }
  
  return response.json();
}
```

### 2. List Users with Pagination

```python
def list_users(page=1, limit=20, entity_id=None):
    """List users with optional filtering"""
    params = {
        'page': page,
        'limit': limit
    }
    
    if entity_id:
        params['entity_id'] = entity_id
    
    response = requests.get(
        f"{base_url}/v1/users",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params
    )
    
    return response.json()

# Get all users in pages
all_users = []
page = 1
while True:
    result = list_users(page=page)
    all_users.extend(result['items'])
    
    if page >= result['pages']:
        break
    page += 1
```

### 3. Create Entity Hierarchy

```javascript
async function setupBrokerageHierarchy(brokerageData) {
  // Create brokerage
  const brokerage = await createEntity({
    name: sanitizeName(brokerageData.name),
    display_name: brokerageData.name,
    entity_type: 'brokerage',
    entity_class: 'structural',
    parent_entity_id: platformId
  });
  
  // Create offices
  for (const officeData of brokerageData.offices) {
    const office = await createEntity({
      name: sanitizeName(officeData.name),
      display_name: officeData.name,
      entity_type: 'office',
      entity_class: 'structural',
      parent_entity_id: brokerage.id
    });
    
    // Create teams in each office
    for (const teamData of officeData.teams) {
      await createEntity({
        name: sanitizeName(teamData.name),
        display_name: teamData.name,
        entity_type: 'team',
        entity_class: 'structural',
        parent_entity_id: office.id
      });
    }
  }
  
  return brokerage;
}

function sanitizeName(displayName) {
  return displayName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
}
```

### 4. Batch Permission Check

```php
function checkMultiplePermissions($userId, $permissions) {
    global $auth;
    
    $checks = array_map(function($perm) use ($userId) {
        return [
            'user_id' => $userId,
            'permission' => $perm
        ];
    }, $permissions);
    
    $response = $auth->request('POST', '/v1/permissions/check-batch', [
        'checks' => $checks
    ]);
    
    $results = [];
    foreach ($response['results'] as $i => $result) {
        $results[$permissions[$i]] = $result['allowed'];
    }
    
    return $results;
}

// Usage
$permissions = checkMultiplePermissions($userId, [
    'user:create',
    'user:update',
    'entity:manage',
    'role:assign'
]);

if ($permissions['user:create']) {
    echo "Can create users";
}
```

## SDK Examples

### JavaScript/TypeScript SDK

```typescript
// outlabs-auth-sdk.ts
export class OutlabsAuthSDK {
  private baseUrl: string;
  private accessToken?: string;
  private refreshToken?: string;
  private tokenExpiry?: number;
  
  constructor(config: { baseUrl?: string }) {
    this.baseUrl = config.baseUrl || 'https://api.auth.outlabs.com';
  }
  
  async login(email: string, password: string): Promise<AuthResponse> {
    const response = await this.request('POST', '/v1/auth/login/json', {
      email,
      password
    });
    
    this.setTokens(response);
    return response;
  }
  
  async logout(): Promise<void> {
    if (this.refreshToken) {
      await this.request('POST', '/v1/auth/mobile/logout', {
        refresh_token: this.refreshToken
      });
    }
    
    this.clearTokens();
  }
  
  async getCurrentUser(): Promise<User> {
    return this.authenticatedRequest('GET', '/v1/auth/me');
  }
  
  async checkPermission(
    permission: string, 
    entityId?: string
  ): Promise<boolean> {
    const result = await this.authenticatedRequest(
      'POST', 
      '/v1/permissions/check',
      { permission, entity_id: entityId }
    );
    
    return result.allowed;
  }
  
  private async authenticatedRequest(
    method: string,
    endpoint: string,
    body?: any
  ): Promise<any> {
    // Auto-refresh if token is about to expire
    if (this.tokenExpiry && Date.now() >= this.tokenExpiry - 60000) {
      await this.refreshAccessToken();
    }
    
    try {
      return await this.request(method, endpoint, body, true);
    } catch (error) {
      // Retry once if 401
      if (error.status === 401) {
        await this.refreshAccessToken();
        return await this.request(method, endpoint, body, true);
      }
      throw error;
    }
  }
  
  private async request(
    method: string,
    endpoint: string,
    body?: any,
    authenticated = false
  ): Promise<any> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json'
    };
    
    if (authenticated && this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }
    
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw { status: response.status, ...error };
    }
    
    return response.json();
  }
  
  private setTokens(response: AuthResponse): void {
    this.accessToken = response.access_token;
    this.refreshToken = response.refresh_token;
    this.tokenExpiry = Date.now() + (response.expires_in * 1000);
  }
  
  private clearTokens(): void {
    this.accessToken = undefined;
    this.refreshToken = undefined;
    this.tokenExpiry = undefined;
  }
}

// Usage
const auth = new OutlabsAuthSDK({ baseUrl: 'http://localhost:8030' });
await auth.login('user@example.com', 'password');
const user = await auth.getCurrentUser();
console.log(`Logged in as ${user.email}`);
```

## Testing with Postman

### Import Postman Collection

Create a new Postman collection with these requests:

```json
{
  "info": {
    "name": "OutlabsAuth API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "baseUrl",
      "value": "http://localhost:8030",
      "type": "default"
    },
    {
      "key": "accessToken",
      "value": "",
      "type": "default"
    }
  ],
  "item": [
    {
      "name": "Login",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "const response = pm.response.json();",
              "pm.collectionVariables.set('accessToken', response.access_token);",
              "pm.test('Login successful', () => {",
              "  pm.response.to.have.status(200);",
              "  pm.expect(response).to.have.property('access_token');",
              "});"
            ]
          }
        }
      ],
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n  \"email\": \"system@outlabs.io\",\n  \"password\": \"Asd123$$$\"\n}"
        },
        "url": {
          "raw": "{{baseUrl}}/v1/auth/login/json",
          "host": ["{{baseUrl}}"],
          "path": ["v1", "auth", "login", "json"]
        }
      }
    },
    {
      "name": "Get Current User",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{accessToken}}"
          }
        ],
        "url": {
          "raw": "{{baseUrl}}/v1/auth/me",
          "host": ["{{baseUrl}}"],
          "path": ["v1", "auth", "me"]
        }
      }
    },
    {
      "name": "List Entities",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "Authorization",
            "value": "Bearer {{accessToken}}"
          }
        ],
        "url": {
          "raw": "{{baseUrl}}/v1/entities?page=1&limit=20",
          "host": ["{{baseUrl}}"],
          "path": ["v1", "entities"],
          "query": [
            {"key": "page", "value": "1"},
            {"key": "limit", "value": "20"}
          ]
        }
      }
    }
  ]
}
```

### Environment Variables

Set up Postman environments:

```json
// Development Environment
{
  "name": "OutlabsAuth Dev",
  "values": [
    {
      "key": "baseUrl",
      "value": "http://localhost:8030",
      "enabled": true
    },
    {
      "key": "testEmail",
      "value": "system@outlabs.io",
      "enabled": true
    },
    {
      "key": "testPassword",
      "value": "Asd123$$$",
      "enabled": true
    }
  ]
}

// Production Environment
{
  "name": "OutlabsAuth Prod",
  "values": [
    {
      "key": "baseUrl",
      "value": "https://api.auth.outlabs.com",
      "enabled": true
    },
    {
      "key": "apiKey",
      "value": "your_api_key_here",
      "enabled": true
    }
  ]
}
```

## Troubleshooting

### Common Issues and Solutions

#### 1. 401 Unauthorized

```javascript
// Problem: Token expired
// Solution: Implement automatic token refresh
async function makeRequest(url, options = {}) {
  let response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`
    }
  });
  
  if (response.status === 401) {
    // Try to refresh
    const refreshResponse = await fetch('/v1/auth/mobile/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken })
    });
    
    if (refreshResponse.ok) {
      const tokens = await refreshResponse.json();
      accessToken = tokens.access_token;
      refreshToken = tokens.refresh_token;
      
      // Retry original request
      response = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${accessToken}`
        }
      });
    }
  }
  
  return response;
}
```

#### 2. 403 Forbidden

```python
# Problem: Missing permissions
# Solution: Check and request necessary permissions
def ensure_permission(permission, entity_id=None):
    """Decorator to check permissions before executing"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            has_permission = check_permission(permission, entity_id)
            if not has_permission:
                raise PermissionError(f"Missing permission: {permission}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

@ensure_permission("user:create")
def create_user(user_data):
    # Function will only execute if user has permission
    return api_call("POST", "/v1/users", user_data)
```

#### 3. 429 Rate Limited

```javascript
// Problem: Too many requests
// Solution: Implement exponential backoff
async function rateLimitedRequest(fn, maxRetries = 3) {
  let lastError;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (error.status === 429) {
        const retryAfter = error.headers?.['retry-after'] || Math.pow(2, i);
        console.log(`Rate limited. Waiting ${retryAfter} seconds...`);
        await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
        lastError = error;
      } else {
        throw error;
      }
    }
  }
  
  throw lastError;
}

// Usage
const users = await rateLimitedRequest(() => 
  fetch('/v1/users', { headers: { 'Authorization': `Bearer ${token}` }})
);
```

#### 4. CORS Issues (Browser)

```javascript
// Problem: CORS errors in browser
// Solution: Configure proper CORS headers or use proxy
const isDevelopment = process.env.NODE_ENV === 'development';

const apiUrl = isDevelopment 
  ? '/api' // Proxy through your dev server
  : 'https://api.auth.outlabs.com';

// In your dev server configuration (e.g., webpack.config.js)
module.exports = {
  devServer: {
    proxy: {
      '/api': {
        target: 'http://localhost:8030',
        pathRewrite: { '^/api': '' },
        changeOrigin: true
      }
    }
  }
};
```

## Next Steps

1. **Explore Advanced Features**:
   - Review [External API Integration Guide](./EXTERNAL_API_INTEGRATION_GUIDE.md)
   - Check [Property Hub Integration Guide](./PROPERTY_HUB_INTEGRATION_GUIDE.md) for real estate examples

2. **Set Up Your Platform**:
   - Follow [Platform Setup Guide](./PLATFORM_SETUP_GUIDE.md)
   - Configure entity hierarchy and roles

3. **Implement Security Best Practices**:
   - Use secure token storage
   - Implement proper error handling
   - Set up monitoring and logging

4. **Get Support**:
   - API Documentation: https://api.auth.outlabs.com/docs
   - Support Email: support@outlabs.com