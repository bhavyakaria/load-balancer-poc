"""
Health Check Module for Load Balancer
"""
import socket
import threading
import time
import logging
from typing import List, Set, Callable

from .config import ServerConfig


class HealthChecker:
    """Health checker for backend servers"""
    
    def __init__(self, servers: List[ServerConfig], check_interval: int = 30):
        self.servers = servers
        self.check_interval = check_interval
        self.healthy_servers: Set[str] = set()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Callback to notify when server health changes
        self.health_change_callback: Callable[[List[ServerConfig]], None] = None
    
    def start(self):
        """Start the health checker"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.thread.start()
        self.logger.info("Health checker started")
    
    def stop(self):
        """Stop the health checker"""
        self.running = False
        if self.thread:
            self.thread.join()
        self.logger.info("Health checker stopped")
    
    def _health_check_loop(self):
        """Main health check loop"""
        while self.running:
            self._check_all_servers()
            time.sleep(self.check_interval)
    
    def _check_all_servers(self):
        """Check health of all servers"""
        current_healthy = set()
        
        for server in self.servers:
            server_key = f"{server.host}:{server.port}"
            
            if self._check_server_health(server):
                current_healthy.add(server_key)
            else:
                self.logger.warning(f"Server {server_key} is unhealthy")
        
        with self.lock:
            # Check if health status changed
            if current_healthy != self.healthy_servers:
                self.healthy_servers = current_healthy
                self.logger.info(f"Healthy servers: {list(self.healthy_servers)}")
                
                # Notify callback if set
                if self.health_change_callback:
                    healthy_server_configs = [
                        server for server in self.servers
                        if f"{server.host}:{server.port}" in self.healthy_servers
                    ]
                    self.health_change_callback(healthy_server_configs)
    
    def _check_server_health(self, server: ServerConfig) -> bool:
        """Check if a single server is healthy"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 second timeout
            result = sock.connect_ex((server.host, server.port))
            sock.close()
            return result == 0
        except Exception as e:
            self.logger.debug(f"Health check failed for {server.host}:{server.port}: {e}")
            return False
    
    def get_healthy_servers(self) -> List[ServerConfig]:
        """Get list of healthy servers"""
        with self.lock:
            return [
                server for server in self.servers
                if f"{server.host}:{server.port}" in self.healthy_servers
            ]
    
    def is_server_healthy(self, server: ServerConfig) -> bool:
        """Check if a specific server is healthy"""
        server_key = f"{server.host}:{server.port}"
        with self.lock:
            return server_key in self.healthy_servers
    
    def update_servers(self, servers: List[ServerConfig]):
        """Update the server list"""
        self.servers = servers
        self.logger.info(f"Updated server list: {[str(s) for s in servers]}")
    
    def set_health_change_callback(self, callback: Callable[[List[ServerConfig]], None]):
        """Set callback for health changes"""
        self.health_change_callback = callback
