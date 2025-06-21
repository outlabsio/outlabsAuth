#!/usr/bin/env python3
"""
🚀 LOCUST DDoS STRESS TEST 🚀
Web-based stress testing with distributed capabilities
Run with: locust -f locust_ddos.py --host=http://localhost:8030
"""

import random
import json
from locust import HttpUser, task, between, events
from locust.env import Environment
from faker import Faker

fake = Faker()

class DDosUser(HttpUser):
    """Hardcore DDoS user that will absolutely hammer the system"""
    
    # Wait time between requests (very aggressive)
    wait_time = between(0.1, 0.5)  # 100ms to 500ms between requests
    
    def on_start(self):
        """Called when a user starts - authenticate and prepare for assault"""
        self.admin_token = None
        self.user_token = None
        self.user_data = None
        
        # Try to get admin token first
        self.authenticate_admin()
        
        # Create and authenticate a test user
        if self.admin_token:
            self.create_and_authenticate_user()
    
    def authenticate_admin(self):
        """Authenticate as admin"""
        response = self.client.post("/v1/auth/login", data={
            "username": "admin@test.com",
            "password": "admin123"
        })
        
        if response.status_code == 200:
            self.admin_token = response.json().get("access_token")
        else:
            print(f"Admin login failed in DDosUser: {response.status_code} - {response.text}")
            self.admin_token = None
    
    def create_and_authenticate_user(self):
        """Create and authenticate a test user"""
        # Create user data
        self.user_data = {
            "email": fake.email(),
            "password": "StressTest123!",
            "first_name": fake.first_name(),
            "last_name": fake.last_name()
        }
        
        # Create user
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        response = self.client.post("/v1/users/", 
                                  json=self.user_data, 
                                  headers=headers)
        
        if response.status_code == 201:
            # Authenticate user
            auth_response = self.client.post("/v1/auth/login", data={
                "username": self.user_data["email"],
                "password": self.user_data["password"]
            })
            
            if auth_response.status_code == 200:
                self.user_token = auth_response.json().get("access_token")
    
    @task(10)
    def auth_me_endpoint(self):
        """Hammer the /me endpoint (most common operation)"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            self.client.get("/v1/auth/me", headers=headers, name="auth_me")
    
    @task(8)
    def list_users(self):
        """Try to list users (should fail for regular users)"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            self.client.get("/v1/users/", headers=headers, name="list_users")
    
    @task(8)
    def list_roles(self):
        """Try to list roles"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            self.client.get("/v1/roles/", headers=headers, name="list_roles")
    
    @task(8)
    def list_permissions(self):
        """Try to list permissions"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            self.client.get("/v1/permissions/", headers=headers, name="list_permissions")
    
    @task(6)
    def list_groups(self):
        """Try to list groups"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            self.client.get("/v1/groups/", headers=headers, name="list_groups")
    
    @task(6)
    def list_client_accounts(self):
        """Try to list client accounts"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            self.client.get("/v1/client_accounts/", headers=headers, name="list_client_accounts")
    
    @task(5)
    def refresh_token(self):
        """Refresh authentication token"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            self.client.post("/v1/auth/refresh", headers=headers, name="refresh_token")
    
    @task(3)
    def attempt_user_creation(self):
        """Attempt to create users (should fail for regular users)"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            fake_user = {
                "email": fake.email(),
                "password": "TestPass123!",
                "first_name": fake.first_name(),
                "last_name": fake.last_name()
            }
            self.client.post("/v1/users/", json=fake_user, headers=headers, name="attempt_create_user")
    
    @task(3)
    def attempt_role_creation(self):
        """Attempt to create roles (should fail for regular users)"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            fake_role = {
                "_id": f"fake_role_{random.randint(1000, 9999)}",
                "name": f"Fake Role {random.randint(1000, 9999)}",
                "description": "This should fail",
                "permissions": ["user:read"]
            }
            self.client.post("/v1/roles/", json=fake_role, headers=headers, name="attempt_create_role")
    
    @task(2)
    def burst_attack(self):
        """Burst attack - send multiple rapid requests"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            
            # Send 5 rapid requests
            for i in range(5):
                endpoint = random.choice([
                    "/v1/auth/me",
                    "/v1/users/",
                    "/v1/roles/",
                    "/v1/permissions/"
                ])
                self.client.get(endpoint, headers=headers, name=f"burst_attack_{i}")
    
    @task(1)
    def memory_pressure_attack(self):
        """Send large payloads to create memory pressure"""
        if self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            
            # Create large payload
            large_payload = {
                "large_data": "x" * 10240,  # 10KB of data
                "metadata": {
                    "timestamp": fake.iso8601(),
                    "random_data": [fake.text() for _ in range(20)],
                    "numbers": [random.randint(1, 1000000) for _ in range(100)]
                }
            }
            
            # Try to create user with large payload (will fail but stress the system)
            self.client.post("/v1/users/", json=large_payload, headers=headers, name="memory_pressure")

class AdminDDosUser(HttpUser):
    """Admin user for more privileged operations"""
    
    wait_time = between(0.2, 0.8)
    weight = 1  # Less admin users
    
    def on_start(self):
        """Authenticate as admin"""
        response = self.client.post("/v1/auth/login", data={
            "username": "admin@test.com",
            "password": "admin123"
        })
        
        if response.status_code == 200:
            self.admin_token = response.json().get("access_token")
        else:
            print(f"Admin login failed: {response.status_code} - {response.text}")
            self.admin_token = None
    
    @task(10)
    def admin_list_users(self):
        """Admin listing users"""
        if self.admin_token:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            self.client.get("/v1/users/", headers=headers, name="admin_list_users")
    
    @task(5)
    def admin_create_users(self):
        """Admin creating users"""
        if self.admin_token:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            user_data = {
                "email": fake.email(),
                "password": "AdminTest123!",
                "first_name": fake.first_name(),
                "last_name": fake.last_name()
            }
            self.client.post("/v1/users/", json=user_data, headers=headers, name="admin_create_user")
    
    @task(3)
    def admin_bulk_operations(self):
        """Admin performing bulk operations"""
        if self.admin_token:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            
            # Bulk user creation
            users_data = []
            for _ in range(5):
                users_data.append({
                    "email": fake.email(),
                    "password": "BulkTest123!",
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name()
                })
            
            self.client.post("/v1/users/bulk-create", json=users_data, headers=headers, name="admin_bulk_create")

# Custom event handlers for detailed monitoring
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Log detailed request information"""
    if exception:
        print(f"FAILED: {request_type} {name} - {exception}")
    elif response_time > 2000:  # Log slow requests (>2s)
        print(f"SLOW: {request_type} {name} - {response_time}ms")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("🔥 DDoS STRESS TEST STARTING - PREPARE FOR SYSTEM ANNIHILATION! 🔥")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("💥 DDoS STRESS TEST COMPLETED - ANALYZING DESTRUCTION... 💥")
    
    # Print summary stats
    stats = environment.stats
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Max response time: {stats.total.max_response_time:.2f}ms")
    print(f"Requests per second: {stats.total.current_rps:.2f}")

# Locust configuration for different attack scenarios
class QuickAssault(DDosUser):
    """Quick assault configuration"""
    wait_time = between(0.05, 0.2)  # Very fast
    weight = 3

class SustainedAttack(DDosUser):
    """Sustained attack configuration"""
    wait_time = between(0.3, 1.0)  # Sustained load
    weight = 2

class HeavyBomber(DDosUser):
    """Heavy bomber with large payloads"""
    wait_time = between(0.5, 1.5)
    weight = 1
    
    @task(20)
    def heavy_payload_attack(self):
        """Send extremely large payloads"""
        if hasattr(self, 'user_token') and self.user_token:
            headers = {"Authorization": f"Bearer {self.user_token}"}
            
            # Create massive payload
            massive_payload = {
                "huge_data": "X" * 50000,  # 50KB
                "arrays": [[random.randint(1, 1000) for _ in range(100)] for _ in range(10)],
                "text_data": [fake.text(max_nb_chars=1000) for _ in range(20)]
            }
            
            self.client.post("/v1/users/", json=massive_payload, headers=headers, name="heavy_bomber")

if __name__ == "__main__":
    print("""
    🚀 LOCUST DDoS STRESS TEST 🚀
    
    Run with different configurations:
    
    1. Basic DDoS:
       locust -f locust_ddos.py --host=http://localhost:8030
    
    2. Hardcore assault (1000 users):
       locust -f locust_ddos.py --host=http://localhost:8030 -u 1000 -r 50
    
    3. Sustained attack (5 minutes):
       locust -f locust_ddos.py --host=http://localhost:8030 -u 500 -r 25 -t 300s
    
    4. Distributed attack (multiple machines):
       Master: locust -f locust_ddos.py --host=http://localhost:8030 --master
       Worker: locust -f locust_ddos.py --host=http://localhost:8030 --worker --master-host=<master-ip>
    
    Open http://localhost:8089 for the web UI
    """) 