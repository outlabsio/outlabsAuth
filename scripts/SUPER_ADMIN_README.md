# Super Admin Seeding Scripts

This directory contains scripts to create the super admin user (Andrew) for the Outlabs authentication system.

## Scripts Available

### 1. `seed_super_admin.py` - Full Featured Script
Complete script that creates all necessary infrastructure along with the super admin user.

**Features:**
- Creates all essential permissions
- Creates platform_admin role
- Creates Outlabs system client account
- Creates/updates Andrew's super admin user
- Handles existing data gracefully
- Auto-generates secure passwords

**Usage:**
```bash
cd outlabsAuth
python scripts/seed_super_admin.py
```

### 2. `seed_andrew_only.py` - Minimal Script
Lightweight script focused only on creating the super admin user with minimal dependencies.

**Features:**
- Direct database operations
- Minimal dependencies
- Production-safe
- Environment variable support
- Auto-generates secure passwords

**Usage:**
```bash
cd outlabsAuth
python scripts/seed_andrew_only.py
```

## Super Admin Details

- **Email:** `system@outlabs.io`
- **Name:** Andrew System
- **Role:** Platform Administrator (all permissions)
- **Client Account:** Outlabs System

## Environment Variables

Both scripts support these environment variables:

```bash
# Required
DATABASE_URL=mongodb://localhost:27017        # MongoDB connection string
MONGO_DATABASE=outlabsAuth                    # Database name

# Optional
SUPER_ADMIN_PASSWORD=your_secure_password     # Set custom password (seed_andrew_only.py only)
```

## Running the Scripts

### Development Environment
```bash
# Using default local MongoDB
cd outlabsAuth
python scripts/seed_andrew_only.py
```

### Production Environment
```bash
# Set environment variables first
export DATABASE_URL="mongodb://your-production-server:27017"
export MONGO_DATABASE="outlabsAuth"
export SUPER_ADMIN_PASSWORD="your_very_secure_password"

# Run the script
cd outlabsAuth
python scripts/seed_andrew_only.py
```

### Docker Environment
```bash
# Run from within the container
docker exec -it outlabs-auth python scripts/seed_andrew_only.py

# Or with environment variables
docker exec -e SUPER_ADMIN_PASSWORD="secure123" -it outlabs-auth python scripts/seed_andrew_only.py
```

## Security Notes

1. **Password Generation:** If no password is provided via environment variable, scripts generate cryptographically secure 20-character passwords.

2. **Password Display:** Generated passwords are displayed once during script execution. Save them immediately.

3. **Production Safety:** Scripts check for existing users and update them safely rather than creating duplicates.

4. **Database Safety:** Scripts use transactions where possible and handle errors gracefully.

## Script Output

Successful execution will show:
```
🎉 SEEDING COMPLETED SUCCESSFULLY! 🎉
==================================================
📧 Email: system@outlabs.io
👤 Name: Andrew System
🆔 User ID: 507f1f77bcf86cd799439011
🏢 Client Account: Outlabs System
🔑 Password (auto-generated):
   Xy9#mK2$pL4@vN8&qR3!
==================================================
⚠️  IMPORTANT: Save this password securely!
⚠️  It will not be displayed again.
✅ Andrew can now login to the system
```

## Testing the Super Admin Account

After running the script, test the account:

```bash
# Using curl
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=system@outlabs.io&password=YOUR_GENERATED_PASSWORD"

# Should return:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

## Troubleshooting

### Common Issues

1. **Connection Error**
   ```
   Error: [Errno 111] Connection refused
   ```
   - Ensure MongoDB is running
   - Check DATABASE_URL is correct

2. **Database Not Found**
   ```
   Database 'outlabsAuth' not found
   ```
   - The script will create the database automatically
   - Ensure you have write permissions

3. **Import Errors**
   ```
   ModuleNotFoundError: No module named 'api'
   ```
   - Run the script from the project root directory: `cd outlabsAuth`
   - Ensure all dependencies are installed: `pip install -r requirements.txt`

4. **Permission Denied**
   ```
   PermissionError: [Errno 13] Permission denied
   ```
   - Check file permissions
   - Run with appropriate user permissions

### Verification

To verify the super admin was created correctly:

1. **Check user exists:**
   ```python
   from api.models.user_model import UserModel
   user = await UserModel.find_one(UserModel.email == "system@outlabs.io")
   print(f"User: {user.first_name} {user.last_name}")
   print(f"Roles: {user.roles}")
   print(f"Is Main Client: {user.is_main_client}")
   ```

2. **Check permissions:**
   ```bash
   # Login and get user profile
   curl -X GET http://localhost:8000/v1/auth/me \
     -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
   ```

## Script Maintenance

When adding new permissions to the system:

1. Update the permissions list in both scripts
2. Re-run the scripts to update the platform_admin role
3. Existing super admin users will automatically get new permissions

## Security Best Practices

1. **Change Default Password:** Always change the generated password after first login in production
2. **Use Environment Variables:** Never hardcode passwords in scripts
3. **Secure Storage:** Store passwords in secure credential management systems
4. **Regular Rotation:** Rotate super admin passwords regularly
5. **Audit Logging:** Monitor super admin account usage

## Integration with CI/CD

For automated deployments:

```yaml
# Example GitHub Actions step
- name: Seed Super Admin
  run: |
    export DATABASE_URL="${{ secrets.DATABASE_URL }}"
    export MONGO_DATABASE="outlabsAuth"
    export SUPER_ADMIN_PASSWORD="${{ secrets.SUPER_ADMIN_PASSWORD }}"
    python scripts/seed_andrew_only.py
```
