#!/usr/bin/env python3
"""
🔥 CONTAINER RESOURCE MONITOR 🔥
Real-time monitoring of Docker container resources during stress testing
"""

import docker
import time
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn
from rich.layout import Layout
from rich.text import Text
import threading
import signal
import sys

console = Console()
client = docker.from_env()

class ContainerMonitor:
    def __init__(self, container_names=['outlabs_auth_api', 'outlabs_auth_mongo']):
        self.container_names = container_names
        self.containers = {}
        self.monitoring = False
        self.stats_data = {}
        self.monitor_thread = None
        
        # Initialize containers
        for name in container_names:
            try:
                container = client.containers.get(name)
                self.containers[name] = container
                self.stats_data[name] = {
                    'cpu_percent': 0,
                    'memory_usage': 0,
                    'memory_limit': 0,
                    'memory_percent': 0,
                    'network_rx': 0,
                    'network_tx': 0,
                    'block_read': 0,
                    'block_write': 0,
                    'pids': 0
                }
            except docker.errors.NotFound:
                console.print(f"[red]Container {name} not found![/red]")
    
    def get_container_stats(self, container_name):
        """Get real-time stats for a container"""
        if container_name not in self.containers:
            return None
            
        container = self.containers[container_name]
        
        try:
            # Get stats (non-blocking)
            stats = container.stats(stream=False)
            
            # Calculate CPU percentage
            cpu_percent = self.calculate_cpu_percent(stats)
            
            # Memory stats
            memory_usage = stats['memory_stats']['usage']
            memory_limit = stats['memory_stats']['limit']
            memory_percent = (memory_usage / memory_limit) * 100
            
            # Network stats
            network_stats = stats.get('networks', {})
            network_rx = sum(net['rx_bytes'] for net in network_stats.values())
            network_tx = sum(net['tx_bytes'] for net in network_stats.values())
            
            # Block I/O stats
            block_stats = stats.get('blkio_stats', {}).get('io_service_bytes_recursive', [])
            block_read = sum(stat['value'] for stat in block_stats if stat['op'] == 'Read')
            block_write = sum(stat['value'] for stat in block_stats if stat['op'] == 'Write')
            
            # Process count
            pids = stats.get('pids_stats', {}).get('current', 0)
            
            return {
                'cpu_percent': cpu_percent,
                'memory_usage': memory_usage,
                'memory_limit': memory_limit,
                'memory_percent': memory_percent,
                'network_rx': network_rx,
                'network_tx': network_tx,
                'block_read': block_read,
                'block_write': block_write,
                'pids': pids,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            console.print(f"[red]Error getting stats for {container_name}: {e}[/red]")
            return None
    
    def calculate_cpu_percent(self, stats):
        """Calculate CPU percentage from Docker stats"""
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']
            
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * \
                             len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100
                return round(cpu_percent, 2)
        except (KeyError, ZeroDivisionError):
            pass
        return 0
    
    def format_bytes(self, bytes_value):
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f}{unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f}TB"
    
    def create_dashboard(self):
        """Create the monitoring dashboard"""
        layout = Layout()
        
        # Create main sections
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="stats", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Split stats into containers
        layout["stats"].split_row(
            Layout(name="api_stats"),
            Layout(name="mongo_stats")
        )
        
        # Header
        header_text = Text("🔥 CONTAINER RESOURCE MONITOR - STRESS TEST MODE 🔥", 
                          style="bold red", justify="center")
        layout["header"].update(Panel(header_text, style="red"))
        
        # Footer
        footer_text = Text("Press Ctrl+C to stop monitoring", 
                          style="yellow", justify="center")
        layout["footer"].update(Panel(footer_text, style="yellow"))
        
        # Container stats
        for i, container_name in enumerate(self.container_names):
            if container_name in self.stats_data:
                stats = self.stats_data[container_name]
                
                # Create stats table
                table = Table(title=f"📊 {container_name.upper()}", show_header=True)
                table.add_column("Metric", style="cyan", width=20)
                table.add_column("Value", style="green", width=15)
                table.add_column("Status", style="yellow", width=10)
                
                # CPU
                cpu_status = "🔥" if stats['cpu_percent'] > 80 else "⚡" if stats['cpu_percent'] > 50 else "✅"
                table.add_row("CPU Usage", f"{stats['cpu_percent']:.1f}%", cpu_status)
                
                # Memory
                memory_status = "🔥" if stats['memory_percent'] > 80 else "⚡" if stats['memory_percent'] > 50 else "✅"
                memory_used = self.format_bytes(stats['memory_usage'])
                memory_limit = self.format_bytes(stats['memory_limit'])
                table.add_row("Memory Usage", f"{memory_used}/{memory_limit}", memory_status)
                table.add_row("Memory %", f"{stats['memory_percent']:.1f}%", memory_status)
                
                # Network
                network_rx = self.format_bytes(stats['network_rx'])
                network_tx = self.format_bytes(stats['network_tx'])
                table.add_row("Network RX", network_rx, "📥")
                table.add_row("Network TX", network_tx, "📤")
                
                # Disk I/O
                disk_read = self.format_bytes(stats['block_read'])
                disk_write = self.format_bytes(stats['block_write'])
                table.add_row("Disk Read", disk_read, "📖")
                table.add_row("Disk Write", disk_write, "📝")
                
                # Processes
                pids_status = "🔥" if stats['pids'] > 200 else "⚡" if stats['pids'] > 100 else "✅"
                table.add_row("Processes", str(stats['pids']), pids_status)
                
                # Update layout
                if container_name == 'outlabs_auth_api':
                    layout["api_stats"].update(Panel(table, style="blue"))
                elif container_name == 'outlabs_auth_mongo':
                    layout["mongo_stats"].update(Panel(table, style="green"))
        
        return layout
    
    def monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            for container_name in self.container_names:
                stats = self.get_container_stats(container_name)
                if stats:
                    self.stats_data[container_name] = stats
            
            time.sleep(1)  # Update every second
    
    def start_monitoring(self):
        """Start monitoring in background thread"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
    
    def run_dashboard(self):
        """Run the live dashboard"""
        console.print(Panel.fit(
            "[bold red]🔥 STARTING CONTAINER MONITORING 🔥[/bold red]\n"
            "[yellow]Monitoring containers during stress test[/yellow]\n"
            "[cyan]Press Ctrl+C to stop[/cyan]",
            title="📊 RESOURCE MONITOR"
        ))
        
        self.start_monitoring()
        
        try:
            with Live(self.create_dashboard(), refresh_per_second=2, console=console) as live:
                while self.monitoring:
                    live.update(self.create_dashboard())
                    time.sleep(0.5)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping monitoring...[/yellow]")
        finally:
            self.stop_monitoring()

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    console.print("\n[red]Monitoring interrupted by user[/red]")
    sys.exit(0)

def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    
    console.print("""
    🔥🔥🔥 CONTAINER RESOURCE MONITOR 🔥🔥🔥
    
    This will monitor your Docker containers in real-time
    during stress testing to see where they CHOKE!
    
    Monitoring containers:
    - outlabs_auth_api (API Server)
    - outlabs_auth_mongo (MongoDB)
    
    Resource limits:
    - API: 8GB RAM, 4 CPU cores
    - MongoDB: 4GB RAM, 2 CPU cores
    
    Watch for:
    🔥 Red indicators = HIGH usage (>80%)
    ⚡ Yellow indicators = MEDIUM usage (>50%)
    ✅ Green indicators = LOW usage (<50%)
    """)
    
    monitor = ContainerMonitor()
    
    if not monitor.containers:
        console.print("[red]No containers found! Make sure Docker containers are running.[/red]")
        console.print("[yellow]Run: docker-compose up -d[/yellow]")
        return
    
    monitor.run_dashboard()

if __name__ == "__main__":
    main() 