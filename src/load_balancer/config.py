"""
Layer 4 Load Balancer Configuration
"""
import json
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ServerConfig:
    """Configuration for backend servers"""
    host: str
    port: int
    weight: int = 1
    max_connections: int = 100
    
    def __str__(self):
        return f"{self.host}:{self.port}"


@dataclass
class LoadBalancerConfig:
    """Configuration for the load balancer"""
    listen_host: str = "localhost"
    listen_port: int = 8080
    backend_servers: List[ServerConfig] = None
    algorithm: str = "round_robin"  # round_robin, least_connections, weighted_round_robin
    health_check_interval: int = 30
    connection_timeout: int = 30
    max_concurrent_connections: int = 1000
    
    def __post_init__(self):
        if self.backend_servers is None:
            self.backend_servers = []
    
    @classmethod
    def from_json(cls, config_path: str) -> 'LoadBalancerConfig':
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        servers = [ServerConfig(**server) for server in data.get('backend_servers', [])]
        data['backend_servers'] = servers
        
        return cls(**data)
    
    def to_json(self, config_path: str):
        """Save configuration to JSON file"""
        data = {
            'listen_host': self.listen_host,
            'listen_port': self.listen_port,
            'backend_servers': [
                {
                    'host': server.host,
                    'port': server.port,
                    'weight': server.weight,
                    'max_connections': server.max_connections
                }
                for server in self.backend_servers
            ],
            'algorithm': self.algorithm,
            'health_check_interval': self.health_check_interval,
            'connection_timeout': self.connection_timeout,
            'max_concurrent_connections': self.max_concurrent_connections
        }
        
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)


# Default configuration
DEFAULT_CONFIG = LoadBalancerConfig(
    listen_host="localhost",
    listen_port=8080,
    backend_servers=[
        ServerConfig("localhost", 9001),
        ServerConfig("localhost", 9002),
        ServerConfig("localhost", 9003)
    ],
    algorithm="round_robin",
    health_check_interval=30,
    connection_timeout=30,
    max_concurrent_connections=1000
)
