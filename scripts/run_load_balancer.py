#!/usr/bin/env python3
"""
Load Balancer Management Script
"""
import asyncio
import json
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from load_balancer import LoadBalancer, LoadBalancerConfig


class LoadBalancerManager:
    """Manager for load balancer operations"""
    
    def __init__(self, config_path: str = "config/default.json"):
        self.config_path = config_path
        self.load_balancer = None
    
    def load_config(self):
        """Load configuration from file"""
        if Path(self.config_path).exists():
            return LoadBalancerConfig.from_json(self.config_path)
        else:
            print(f"Config file {self.config_path} not found, using default config")
            return LoadBalancerConfig()
    
    async def start(self):
        """Start the load balancer"""
        config = self.load_config()
        self.load_balancer = LoadBalancer(config)
        
        print(f"Starting load balancer with configuration:")
        print(f"  Listen Address: {config.listen_host}:{config.listen_port}")
        print(f"  Backend Servers: {[str(s) for s in config.backend_servers]}")
        print(f"  Algorithm: {config.algorithm}")
        print(f"  Health Check Interval: {config.health_check_interval}s")
        print(f"  Connection Timeout: {config.connection_timeout}s")
        print(f"  Max Concurrent Connections: {config.max_concurrent_connections}")
        print()
        
        await self.load_balancer.serve_forever()
    
    async def status(self):
        """Show load balancer status"""
        if not self.load_balancer:
            config = self.load_config()
            self.load_balancer = LoadBalancer(config)
        
        self.load_balancer.print_status()
    
    def create_default_config(self):
        """Create default configuration file"""
        from load_balancer.config import DEFAULT_CONFIG
        DEFAULT_CONFIG.to_json(self.config_path)
        print(f"Created default configuration file: {self.config_path}")


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/run_load_balancer.py start [config_file]")
        print("  python scripts/run_load_balancer.py status [config_file]")
        print("  python scripts/run_load_balancer.py create-config [config_file]")
        sys.exit(1)
    
    command = sys.argv[1]
    config_file = sys.argv[2] if len(sys.argv) > 2 else "config/default.json"
    
    manager = LoadBalancerManager(config_file)
    
    if command == "start":
        try:
            await manager.start()
        except KeyboardInterrupt:
            print("\\nShutting down...")
    
    elif command == "status":
        await manager.status()
    
    elif command == "create-config":
        manager.create_default_config()
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
