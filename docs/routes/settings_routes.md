# Settings Management Routes Documentation

## Overview

The Settings Management Routes provide endpoints for system-level configuration management, including email settings for notifications and other system-wide parameters. These endpoints are designed for super administrators to configure platform-wide settings.

**Base URL**: `/v1/settings`

## Authentication

All settings routes require authentication via Bearer token. Additionally, endpoints require system-level administrative privileges.

```bash
Authorization: Bearer <access_token>
```

## Permission Requirements

Settings routes are restricted to users with:

- `system:manage_settings` permission
- Valid authentication token
- Appropriate system-level scope

---

## Endpoints

### 1. Get Email Settings

Retrieve the current system-level email configuration settings.

**Endpoint**: `GET /v1/settings/email`

**Permissions Required**:

- `system:manage_settings`

**Parameters**: None

**Response**:

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_username": "notifications@company.com",
  "smtp_password": "********",
  "smtp_use_tls": true,
  "smtp_use_ssl": false,
  "from_email": "notifications@company.com",
  "from_name": "OutlabsAuth System",
  "admin_notification_email": "admin@company.com",
  "enabled": true
}
```

**Response Fields**:

- `smtp_host`: SMTP server hostname
- `smtp_port`: SMTP server port (typically 587 for TLS, 465 for SSL, 25 for unencrypted)
- `smtp_username`: Username for SMTP authentication
- `smtp_password`: Password for SMTP authentication (masked in response)
- `smtp_use_tls`: Whether to use TLS encryption
- `smtp_use_ssl`: Whether to use SSL encryption
- `from_email`: Default sender email address
- `from_name`: Default sender display name
- `admin_notification_email`: Email address for admin notifications
- `enabled`: Whether email functionality is enabled

**Status Codes**:

- `200 OK`: Settings retrieved successfully
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: User lacks `system:manage_settings` permission
- `404 Not Found`: No email settings configured
- `500 Internal Server Error`: Server error during retrieval

**Example Request**:

```bash
curl -X GET "http://localhost:8030/v1/settings/email" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json"
```

---

### 2. Update Email Settings

Update the system-level email configuration settings.

**Endpoint**: `PUT /v1/settings/email`

**Permissions Required**:

- `system:manage_settings`

**Request Body**:

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_username": "notifications@company.com",
  "smtp_password": "secure-password",
  "smtp_use_tls": true,
  "smtp_use_ssl": false,
  "from_email": "notifications@company.com",
  "from_name": "OutlabsAuth System",
  "admin_notification_email": "admin@company.com",
  "enabled": true
}
```

**Request Fields**:

All fields from the GET response can be updated. The password field will be encrypted before storage.

**Response**:

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_username": "notifications@company.com",
  "smtp_password": "********",
  "smtp_use_tls": true,
  "smtp_use_ssl": false,
  "from_email": "notifications@company.com",
  "from_name": "OutlabsAuth System",
  "admin_notification_email": "admin@company.com",
  "enabled": true
}
```

**Status Codes**:

- `200 OK`: Settings updated successfully
- `400 Bad Request`: Invalid settings data
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: User lacks `system:manage_settings` permission
- `422 Unprocessable Entity`: Validation error in settings data
- `500 Internal Server Error`: Server error during update

**Example Request**:

```bash
curl -X PUT "http://localhost:8030/v1/settings/email" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "notifications@company.com",
    "smtp_password": "secure-password",
    "smtp_use_tls": true,
    "smtp_use_ssl": false,
    "from_email": "notifications@company.com",
    "from_name": "OutlabsAuth System",
    "admin_notification_email": "admin@company.com",
    "enabled": true
  }'
```

---

### 3. Test Email Settings

Send a test email using the current email configuration to verify settings are working correctly.

**Endpoint**: `POST /v1/settings/email/test`

**Permissions Required**:

- `system:manage_settings`

**Request Body**:

```json
{
  "to_email": "test@example.com"
}
```

**Request Fields**:

- `to_email`: Email address to send the test email to

**Response**:

```json
{
  "success": true,
  "message": "Test email sent successfully to test@example.com"
}
```

**Response Fields**:

- `success`: Whether the test email was sent successfully
- `message`: Descriptive message about the test result

**Status Codes**:

- `200 OK`: Test email sent successfully
- `400 Bad Request`: Invalid email address or missing settings
- `401 Unauthorized`: Invalid or missing authentication token
- `403 Forbidden`: User lacks `system:manage_settings` permission
- `422 Unprocessable Entity`: Email settings not configured or invalid
- `500 Internal Server Error`: Server error during email sending

**Example Request**:

```bash
curl -X POST "http://localhost:8030/v1/settings/email/test" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "admin@company.com"
  }'
```

**Example Error Response**:

```json
{
  "success": false,
  "message": "Failed to send test email: SMTP authentication failed"
}
```

---

## Email Configuration Guide

### Common SMTP Configurations

#### Gmail / Google Workspace

```json
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_use_tls": true,
  "smtp_use_ssl": false,
  "smtp_username": "your-email@gmail.com",
  "smtp_password": "app-specific-password"
}
```

**Note**: Gmail requires an app-specific password for SMTP authentication. Enable 2-factor authentication and generate an app password.

#### Microsoft 365 / Outlook

```json
{
  "smtp_host": "smtp.office365.com",
  "smtp_port": 587,
  "smtp_use_tls": true,
  "smtp_use_ssl": false,
  "smtp_username": "your-email@company.com",
  "smtp_password": "your-password"
}
```

#### SendGrid

```json
{
  "smtp_host": "smtp.sendgrid.net",
  "smtp_port": 587,
  "smtp_use_tls": true,
  "smtp_use_ssl": false,
  "smtp_username": "apikey",
  "smtp_password": "your-sendgrid-api-key"
}
```

#### Amazon SES

```json
{
  "smtp_host": "email-smtp.us-east-1.amazonaws.com",
  "smtp_port": 587,
  "smtp_use_tls": true,
  "smtp_use_ssl": false,
  "smtp_username": "your-ses-smtp-username",
  "smtp_password": "your-ses-smtp-password"
}
```

### Security Considerations

1. **Password Storage**: SMTP passwords are encrypted before storage in the database
2. **TLS/SSL**: Always use TLS or SSL encryption when available
3. **Authentication**: Use strong passwords or API keys for SMTP authentication
4. **Sender Verification**: Ensure from_email is verified with your email provider
5. **Rate Limiting**: Be aware of your email provider's sending limits

---

## Error Handling

### Common Error Scenarios

**SMTP Authentication Failed**:

```json
{
  "detail": "Failed to authenticate with SMTP server. Please check your username and password."
}
```

**SMTP Connection Failed**:

```json
{
  "detail": "Failed to connect to SMTP server. Please check your host and port settings."
}
```

**Invalid Email Configuration**:

```json
{
  "detail": "Email settings are not properly configured. Please update settings first."
}
```

**Permission Denied**:

```json
{
  "detail": "You do not have permission to manage system settings."
}
```

---

## Integration Examples

### Python Client Example

```python
import requests

class EmailSettingsClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_email_settings(self):
        """Retrieve current email settings"""
        response = requests.get(
            f"{self.base_url}/v1/settings/email",
            headers=self.headers
        )
        return response.json() if response.status_code == 200 else None
    
    def update_email_settings(self, settings):
        """Update email settings"""
        response = requests.put(
            f"{self.base_url}/v1/settings/email",
            headers=self.headers,
            json=settings
        )
        return response.json() if response.status_code == 200 else None
    
    def test_email_settings(self, to_email):
        """Send test email"""
        response = requests.post(
            f"{self.base_url}/v1/settings/email/test",
            headers=self.headers,
            json={"to_email": to_email}
        )
        return response.json()

# Usage
client = EmailSettingsClient("http://localhost:8030", admin_token)

# Get current settings
settings = client.get_email_settings()
print(f"Current SMTP Host: {settings['smtp_host']}")

# Update settings
new_settings = {
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "notifications@company.com",
    "smtp_password": "secure-password",
    "smtp_use_tls": True,
    "smtp_use_ssl": False,
    "from_email": "notifications@company.com",
    "from_name": "My Company",
    "admin_notification_email": "admin@company.com",
    "enabled": True
}
updated = client.update_email_settings(new_settings)

# Test configuration
test_result = client.test_email_settings("admin@company.com")
print(f"Test Result: {test_result['message']}")
```

### JavaScript/TypeScript Client Example

```typescript
interface EmailSettings {
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  from_email: string;
  from_name: string;
  admin_notification_email: string;
  enabled: boolean;
}

class EmailSettingsClient {
  constructor(
    private baseUrl: string,
    private accessToken: string
  ) {}

  async getEmailSettings(): Promise<EmailSettings | null> {
    const response = await fetch(`${this.baseUrl}/v1/settings/email`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      }
    });

    if (response.ok) {
      return await response.json();
    }
    return null;
  }

  async updateEmailSettings(settings: EmailSettings): Promise<EmailSettings | null> {
    const response = await fetch(`${this.baseUrl}/v1/settings/email`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(settings)
    });

    if (response.ok) {
      return await response.json();
    }
    return null;
  }

  async testEmailSettings(toEmail: string): Promise<{success: boolean, message: string}> {
    const response = await fetch(`${this.baseUrl}/v1/settings/email/test`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ to_email: toEmail })
    });

    return await response.json();
  }
}

// Usage
const client = new EmailSettingsClient('http://localhost:8030', adminToken);

// Get current settings
const settings = await client.getEmailSettings();
console.log(`Current SMTP Host: ${settings?.smtp_host}`);

// Test configuration
const testResult = await client.testEmailSettings('admin@company.com');
console.log(`Test Result: ${testResult.message}`);
```

---

## Best Practices

### Configuration Management

1. **Test Before Production**: Always test email settings before enabling in production
2. **Secure Storage**: Ensure database encryption for sensitive SMTP credentials
3. **Regular Testing**: Periodically test email configuration to ensure continued functionality
4. **Monitoring**: Monitor email sending success rates and failures
5. **Fallback Strategy**: Have a backup SMTP provider configured

### Email Sending Best Practices

1. **Rate Limiting**: Implement rate limiting to prevent email abuse
2. **Queue Management**: Use background jobs for bulk email sending
3. **Retry Logic**: Implement retry logic for failed email sends
4. **Bounce Handling**: Monitor and handle email bounces appropriately
5. **Unsubscribe Options**: Include unsubscribe links in notification emails

### Security Best Practices

1. **API Keys**: Use API keys instead of passwords when available
2. **IP Whitelisting**: Configure SMTP provider IP restrictions
3. **SPF/DKIM/DMARC**: Configure email authentication records
4. **Audit Logging**: Log all settings changes for security compliance
5. **Access Control**: Limit settings access to super administrators only

---

## Related Documentation

- [Auth Routes](auth_routes.md) - For authentication and permissions
- [Platform Routes](platform_routes.md) - For platform-level operations
- [User Routes](user_routes.md) - For user notification preferences
- [Permissions Documentation](../permissions.md) - For understanding system:manage_settings permission