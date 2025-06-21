#!/usr/bin/env python3
"""
Script to clean up duplicate users by email and ensure database integrity.
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict

# Add the project root to the Python path to allow importing from 'api'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- Configuration ---
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DATABASE", "outlabsAuth")

async def cleanup_duplicate_users(db):
    """
    Removes duplicate users, keeping only the earliest created one for each email.
    """
    print("--- Starting duplicate user cleanup ---")
    
    # Find all users
    users = await db.users.find().to_list(length=None)
    print(f"Found {len(users)} total users")
    
    # Group users by email
    users_by_email = defaultdict(list)
    for user in users:
        users_by_email[user['email']].append(user)
    
    # Find duplicates
    duplicate_emails = {email: user_list for email, user_list in users_by_email.items() if len(user_list) > 1}
    
    if not duplicate_emails:
        print("No duplicate users found!")
        return
        
    print(f"Found {len(duplicate_emails)} emails with duplicates:")
    
    for email, duplicate_users in duplicate_emails.items():
        print(f"\nEmail: {email} has {len(duplicate_users)} duplicates")
        
        # Sort by created_at to keep the earliest one
        duplicate_users.sort(key=lambda x: x.get('created_at', x.get('_id')))
        keep_user = duplicate_users[0]
        remove_users = duplicate_users[1:]
        
        print(f"  Keeping user: {keep_user['_id']} (created: {keep_user.get('created_at', 'unknown')})")
        
        # Remove the duplicate users
        for user in remove_users:
            print(f"  Removing user: {user['_id']} (created: {user.get('created_at', 'unknown')})")
            await db.users.delete_one({"_id": user["_id"]})
    
    print(f"\nCleanup complete! Removed {sum(len(users) - 1 for users in duplicate_emails.values())} duplicate users")

async def ensure_email_index(db):
    """
    Creates unique index on email field to prevent future duplicates.
    """
    print("--- Ensuring unique email index ---")
    
    try:
        # Drop existing email index if it exists (in case it's not unique)
        try:
            await db.users.drop_index("email_1")
            print("Dropped existing non-unique email index")
        except Exception:
            pass  # Index doesn't exist, that's fine
        
        # Create unique index
        await db.users.create_index("email", unique=True)
        print("Created unique index on email field")
        
        # Verify the index
        indexes = await db.users.list_indexes().to_list(length=None)
        email_index = next((idx for idx in indexes if 'email' in idx.get('key', {})), None)
        if email_index and email_index.get('unique'):
            print("✓ Unique email index verified")
        else:
            print("⚠ Warning: Unique email index not found")
            
    except Exception as e:
        print(f"Error creating unique index: {e}")

async def main():
    """
    Main cleanup function.
    """
    print(f"Connecting to MongoDB: {MONGO_URL}")
    print(f"Database: {DB_NAME}")
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Test connection
        await client.admin.command('ismaster')
        print("Connected to MongoDB successfully")
        
        # Clean up duplicates first
        await cleanup_duplicate_users(db)
        
        # Then ensure unique constraint
        await ensure_email_index(db)
        
        print("\n--- Cleanup complete! ---")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(main()) 