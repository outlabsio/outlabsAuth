#!/usr/bin/env python3
"""
🔥 HARDCORE DDoS-LEVEL STRESS TEST 🔥
This script will absolutely DESTROY our system with massive load to test its limits.
We're talking thousands of concurrent requests, database hammering, and memory pressure.
"""

import asyncio
import aiohttp
import time
import json
import random
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil
import threading
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.live import Live
from rich.panel import Panel
from faker import Faker
import uvloop

# Set the event loop policy to use uvloop for maximum performance
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

console = Console()
fake = Faker()

@dataclass
class StressTestConfig:
    """Configuration for our hardcore stress test"""
    base_url: str = "http://localhost:8030"
    
    # DDoS-level configuration
    max_concurrent_users: int = 1000
    requests_per_user: int = 100
    test_duration_seconds: int = 300  # 5 minutes of pure hell
    
    # Attack patterns
    burst_size: int = 50  # Requests in a single burst
    burst_interval: float = 0.1  # Seconds between bursts
    
    # Database stress
    db_connection_pool_size: int = 100
    
    # Memory pressure
    generate_large_payloads: bool = True
    payload_size_kb: int = 10
    
    # Chaos engineering
    random_delays: bool = True
    connection_drops: bool = True
    
@dataclass
class RequestResult:
    """Result of a single request"""
    endpoint: str
    method: str
    status_code: int
    response_time: float
    success: bool
    error: Optional[str] = None
    timestamp: float = 0

class SystemMonitor:
    """Monitor system resources during stress test"""
    
    def __init__(self):
        self.cpu_usage = []
        self.memory_usage = []
        self.disk_io = []
        self.network_io = []
        self.monitoring = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Start system monitoring in background thread"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
            
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage.append(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.memory_usage.append(memory.percent)
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                self.disk_io.append({
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes
                })
            
            # Network I/O
            net_io = psutil.net_io_counters()
            if net_io:
                self.network_io.append({
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv
                })
                
            time.sleep(1)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        return {
            'cpu': {
                'avg': statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
                'max': max(self.cpu_usage) if self.cpu_usage else 0,
                'min': min(self.cpu_usage) if self.cpu_usage else 0
            },
            'memory': {
                'avg': statistics.mean(self.memory_usage) if self.memory_usage else 0,
                'max': max(self.memory_usage) if self.memory_usage else 0,
                'min': min(self.memory_usage) if self.memory_usage else 0
            },
            'samples': len(self.cpu_usage)
        }

class HardcoreStressTester:
    """The main stress testing beast"""
    
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.results: List[RequestResult] = []
        self.admin_token: Optional[str] = None
        self.user_tokens: List[str] = []
        self.test_users: List[Dict[str, Any]] = []
        self.monitor = SystemMonitor()
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def setup_session(self):
        """Setup HTTP session with connection pooling"""
        connector = aiohttp.TCPConnector(
            limit=self.config.max_concurrent_users * 2,
            limit_per_host=self.config.max_concurrent_users,
            ttl_dns_cache=300,
            ttl_dns_cache_per_host=300,
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'HardcoreStressTester/1.0'}
        )
    
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
    
    async def authenticate_admin(self) -> bool:
        """Get admin token for setup"""
        try:
            login_data = {
                "username": "admin@test.com",
                "password": "admin123"
            }
            
            async with self.session.post(
                f"{self.config.base_url}/v1/auth/login",
                data=login_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data.get("access_token")
                    return True
                return False
        except Exception as e:
            console.print(f"[red]Failed to authenticate admin: {e}[/red]")
            return False
    
    async def create_test_users(self, count: int = 100) -> List[Dict[str, Any]]:
        """Create test users for stress testing"""
        users = []
        headers = {"Authorization": f"Bearer {self.admin_token}"}
        
        console.print(f"[yellow]Creating {count} test users...[/yellow]")
        
        # Create users in batches to avoid overwhelming the system during setup
        batch_size = 10
        for i in range(0, count, batch_size):
            batch_users = []
            for j in range(batch_size):
                if i + j >= count:
                    break
                    
                user_data = {
                    "email": fake.email(),
                    "password": "StressTest123!",
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name()
                }
                batch_users.append(user_data)
            
            # Create batch of users
            tasks = []
            for user_data in batch_users:
                task = self.create_single_user(user_data, headers)
                tasks.append(task)
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for user_data, result in zip(batch_users, batch_results):
                if isinstance(result, dict) and result.get('success'):
                    users.append({
                        'email': user_data['email'],
                        'password': user_data['password'],
                        'user_id': result.get('user_id')
                    })
        
        console.print(f"[green]Created {len(users)} test users successfully[/green]")
        return users
    
    async def create_single_user(self, user_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Create a single test user"""
        try:
            async with self.session.post(
                f"{self.config.base_url}/v1/users/",
                json=user_data,
                headers=headers
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    return {'success': True, 'user_id': data.get('_id')}
                else:
                    return {'success': False, 'status': response.status}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def authenticate_users(self, users: List[Dict[str, Any]]) -> List[str]:
        """Authenticate all test users to get tokens"""
        console.print(f"[yellow]Authenticating {len(users)} users...[/yellow]")
        
        tasks = []
        for user in users:
            task = self.authenticate_single_user(user['email'], user['password'])
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        tokens = []
        for result in results:
            if isinstance(result, str):
                tokens.append(result)
        
        console.print(f"[green]Got {len(tokens)} user tokens[/green]")
        return tokens
    
    async def authenticate_single_user(self, email: str, password: str) -> Optional[str]:
        """Authenticate a single user"""
        try:
            login_data = {
                "username": email,
                "password": password
            }
            
            async with self.session.post(
                f"{self.config.base_url}/v1/auth/login",
                data=login_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("access_token")
                return None
        except Exception:
            return None
    
    def generate_large_payload(self) -> Dict[str, Any]:
        """Generate large payload for memory pressure testing"""
        if not self.config.generate_large_payloads:
            return {}
        
        # Generate payload of specified size
        payload_size = self.config.payload_size_kb * 1024
        large_string = 'x' * (payload_size // 2)  # Divide by 2 for safety
        
        return {
            'large_data': large_string,
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'size_kb': self.config.payload_size_kb,
                'random_data': [fake.text() for _ in range(10)]
            }
        }
    
    async def execute_request(self, endpoint: str, method: str = 'GET', 
                            headers: Optional[Dict[str, str]] = None,
                            payload: Optional[Dict[str, Any]] = None) -> RequestResult:
        """Execute a single HTTP request"""
        start_time = time.time()
        
        try:
            # Add random delay for chaos engineering
            if self.config.random_delays:
                await asyncio.sleep(random.uniform(0, 0.1))
            
            # Add large payload for memory pressure
            if payload is None and method in ['POST', 'PUT']:
                payload = self.generate_large_payload()
            
            url = f"{self.config.base_url}{endpoint}"
            
            async with self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=payload if payload else None
            ) as response:
                response_time = time.time() - start_time
                
                return RequestResult(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status,
                    response_time=response_time,
                    success=200 <= response.status < 400,
                    timestamp=start_time
                )
                
        except Exception as e:
            response_time = time.time() - start_time
            return RequestResult(
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time=response_time,
                success=False,
                error=str(e),
                timestamp=start_time
            )
    
    async def ddos_attack_pattern(self, token: str, user_id: int) -> List[RequestResult]:
        """Execute DDoS-style attack pattern for a single user"""
        results = []
        headers = {"Authorization": f"Bearer {token}"}
        
        # Define attack endpoints
        endpoints = [
            ("/v1/auth/me", "GET"),
            ("/v1/users/", "GET"),
            ("/v1/roles/", "GET"),
            ("/v1/permissions/", "GET"),
            ("/v1/groups/", "GET"),
            ("/v1/client_accounts/", "GET"),
        ]
        
        for _ in range(self.config.requests_per_user):
            # Random endpoint selection
            endpoint, method = random.choice(endpoints)
            
            # Execute request
            result = await self.execute_request(endpoint, method, headers)
            results.append(result)
            
            # Burst pattern - send multiple requests rapidly
            if random.random() < 0.3:  # 30% chance of burst
                burst_tasks = []
                for _ in range(self.config.burst_size):
                    burst_endpoint, burst_method = random.choice(endpoints)
                    task = self.execute_request(burst_endpoint, burst_method, headers)
                    burst_tasks.append(task)
                
                burst_results = await asyncio.gather(*burst_tasks, return_exceptions=True)
                for burst_result in burst_results:
                    if isinstance(burst_result, RequestResult):
                        results.append(burst_result)
            
            # Small delay between requests (but not too much - we want to stress!)
            await asyncio.sleep(self.config.burst_interval)
        
        return results
    
    async def run_hardcore_stress_test(self):
        """Run the main hardcore stress test"""
        console.print(Panel.fit(
            "[bold red]🔥 HARDCORE DDoS-LEVEL STRESS TEST INITIATED 🔥[/bold red]\n"
            f"[yellow]Concurrent Users: {self.config.max_concurrent_users}[/yellow]\n"
            f"[yellow]Requests per User: {self.config.requests_per_user}[/yellow]\n"
            f"[yellow]Test Duration: {self.config.test_duration_seconds}s[/yellow]\n"
            f"[red]PREPARE FOR SYSTEM ANNIHILATION![/red]",
            title="🚨 STRESS TEST CONFIGURATION 🚨"
        ))
        
        # Setup
        await self.setup_session()
        
        # Start system monitoring
        self.monitor.start_monitoring()
        
        try:
            # Phase 1: Authentication
            console.print("\n[bold blue]Phase 1: Admin Authentication[/bold blue]")
            if not await self.authenticate_admin():
                console.print("[red]Failed to authenticate admin. Aborting test.[/red]")
                return
            
            # Phase 2: Create test users
            console.print("\n[bold blue]Phase 2: Creating Test Army[/bold blue]")
            self.test_users = await self.create_test_users(min(100, self.config.max_concurrent_users))
            
            # Phase 3: Authenticate users
            console.print("\n[bold blue]Phase 3: Authenticating Test Army[/bold blue]")
            self.user_tokens = await self.authenticate_users(self.test_users)
            
            if not self.user_tokens:
                console.print("[red]No user tokens available. Aborting test.[/red]")
                return
            
            # Phase 4: THE MAIN ASSAULT
            console.print("\n[bold red]Phase 4: LAUNCHING DDoS ASSAULT![/bold red]")
            
            start_time = time.time()
            
            # Create concurrent tasks for maximum destruction
            tasks = []
            for i in range(self.config.max_concurrent_users):
                token = random.choice(self.user_tokens)
                task = self.ddos_attack_pattern(token, i)
                tasks.append(task)
            
            # Execute all tasks concurrently with progress tracking
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                
                assault_task = progress.add_task(
                    f"[red]ASSAULTING SYSTEM WITH {self.config.max_concurrent_users} CONCURRENT USERS",
                    total=self.config.max_concurrent_users
                )
                
                # Execute tasks in batches to avoid overwhelming the system
                batch_size = 50
                all_results = []
                
                for i in range(0, len(tasks), batch_size):
                    batch = tasks[i:i + batch_size]
                    batch_results = await asyncio.gather(*batch, return_exceptions=True)
                    
                    for result in batch_results:
                        if isinstance(result, list):
                            all_results.extend(result)
                        elif isinstance(result, Exception):
                            console.print(f"[red]Task failed: {result}[/red]")
                    
                    progress.update(assault_task, advance=len(batch))
                    
                    # Brief pause between batches
                    await asyncio.sleep(0.1)
            
            end_time = time.time()
            self.results = all_results
            
            # Phase 5: Analysis
            console.print("\n[bold green]Phase 5: Analyzing Destruction[/bold green]")
            await self.analyze_results(end_time - start_time)
            
        finally:
            # Cleanup
            self.monitor.stop_monitoring()
            await self.cleanup_session()
    
    async def analyze_results(self, total_duration: float):
        """Analyze stress test results"""
        if not self.results:
            console.print("[red]No results to analyze![/red]")
            return
        
        # Calculate statistics
        successful_requests = [r for r in self.results if r.success]
        failed_requests = [r for r in self.results if not r.success]
        
        response_times = [r.response_time for r in successful_requests]
        
        stats = {
            'total_requests': len(self.results),
            'successful_requests': len(successful_requests),
            'failed_requests': len(failed_requests),
            'success_rate': (len(successful_requests) / len(self.results)) * 100,
            'total_duration': total_duration,
            'requests_per_second': len(self.results) / total_duration,
            'avg_response_time': statistics.mean(response_times) if response_times else 0,
            'min_response_time': min(response_times) if response_times else 0,
            'max_response_time': max(response_times) if response_times else 0,
            'median_response_time': statistics.median(response_times) if response_times else 0,
            'p95_response_time': statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else 0,
            'p99_response_time': statistics.quantiles(response_times, n=100)[98] if len(response_times) > 100 else 0,
        }
        
        # System stats
        system_stats = self.monitor.get_stats()
        
        # Display results
        self.display_results(stats, system_stats)
        
        # Save detailed results
        await self.save_results(stats, system_stats)
    
    def display_results(self, stats: Dict[str, Any], system_stats: Dict[str, Any]):
        """Display stress test results"""
        
        # Main results table
        table = Table(title="🔥 HARDCORE STRESS TEST RESULTS 🔥")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta")
        table.add_column("Status", style="green")
        
        # Request statistics
        table.add_row("Total Requests", f"{stats['total_requests']:,}", "📊")
        table.add_row("Successful Requests", f"{stats['successful_requests']:,}", "✅")
        table.add_row("Failed Requests", f"{stats['failed_requests']:,}", "❌")
        table.add_row("Success Rate", f"{stats['success_rate']:.2f}%", 
                     "🎯" if stats['success_rate'] > 95 else "⚠️" if stats['success_rate'] > 80 else "💥")
        
        # Performance statistics
        table.add_row("", "", "")
        table.add_row("Total Duration", f"{stats['total_duration']:.2f}s", "⏱️")
        table.add_row("Requests/Second", f"{stats['requests_per_second']:.2f}", "🚀")
        table.add_row("Avg Response Time", f"{stats['avg_response_time']*1000:.2f}ms", "📈")
        table.add_row("Min Response Time", f"{stats['min_response_time']*1000:.2f}ms", "⚡")
        table.add_row("Max Response Time", f"{stats['max_response_time']*1000:.2f}ms", "🐌")
        table.add_row("Median Response Time", f"{stats['median_response_time']*1000:.2f}ms", "📊")
        table.add_row("95th Percentile", f"{stats['p95_response_time']*1000:.2f}ms", "📈")
        table.add_row("99th Percentile", f"{stats['p99_response_time']*1000:.2f}ms", "🔥")
        
        # System statistics
        table.add_row("", "", "")
        table.add_row("Avg CPU Usage", f"{system_stats['cpu']['avg']:.2f}%", 
                     "🔥" if system_stats['cpu']['avg'] > 80 else "⚡")
        table.add_row("Max CPU Usage", f"{system_stats['cpu']['max']:.2f}%", 
                     "💥" if system_stats['cpu']['max'] > 90 else "🔥")
        table.add_row("Avg Memory Usage", f"{system_stats['memory']['avg']:.2f}%", 
                     "🔥" if system_stats['memory']['avg'] > 80 else "⚡")
        table.add_row("Max Memory Usage", f"{system_stats['memory']['max']:.2f}%", 
                     "💥" if system_stats['memory']['max'] > 90 else "🔥")
        
        console.print(table)
        
        # Performance verdict
        if stats['success_rate'] > 95 and stats['avg_response_time'] < 1.0:
            verdict = "[bold green]🏆 SYSTEM SURVIVED THE ASSAULT! ENTERPRISE GRADE! 🏆[/bold green]"
        elif stats['success_rate'] > 80 and stats['avg_response_time'] < 2.0:
            verdict = "[bold yellow]⚠️ SYSTEM HELD UP WELL BUT SHOWED STRESS ⚠️[/bold yellow]"
        else:
            verdict = "[bold red]💥 SYSTEM BUCKLED UNDER PRESSURE! NEEDS OPTIMIZATION! 💥[/bold red]"
        
        console.print(f"\n{verdict}")
    
    async def save_results(self, stats: Dict[str, Any], system_stats: Dict[str, Any]):
        """Save detailed results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stress_test_results_{timestamp}.json"
        
        detailed_results = {
            'config': asdict(self.config),
            'stats': stats,
            'system_stats': system_stats,
            'timestamp': datetime.now().isoformat(),
            'detailed_requests': [asdict(r) for r in self.results[:1000]]  # Limit for file size
        }
        
        with open(filename, 'w') as f:
            json.dump(detailed_results, f, indent=2)
        
        console.print(f"[green]Detailed results saved to: {filename}[/green]")

async def main():
    """Main entry point"""
    console.print("""
    🔥🔥🔥 HARDCORE DDoS-LEVEL STRESS TEST 🔥🔥🔥
    
    This will absolutely PUNISH your system with:
    - Thousands of concurrent requests
    - Database hammering
    - Memory pressure testing
    - Burst attack patterns
    - System resource monitoring
    
    ARE YOU READY TO SEE YOUR SYSTEM SCREAM? 😈
    """)
    
    # Configuration
    config = StressTestConfig(
        max_concurrent_users=500,  # Start with 500 concurrent users
        requests_per_user=50,      # 50 requests per user
        test_duration_seconds=180, # 3 minutes of hell
        burst_size=20,             # 20 requests in a burst
        burst_interval=0.05,       # Very fast bursts
        generate_large_payloads=True,
        payload_size_kb=5,         # 5KB payloads for memory pressure
        random_delays=True,
        connection_drops=True
    )
    
    # Create and run stress tester
    tester = HardcoreStressTester(config)
    await tester.run_hardcore_stress_test()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[red]Stress test interrupted by user[/red]")
    except Exception as e:
        console.print(f"\n[red]Stress test failed: {e}[/red]")
        raise 