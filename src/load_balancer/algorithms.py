"""
Load Balancing Algorithms
"""
import random
import threading
from abc import ABC, abstractmethod
from typing import List, Optional
from collections import defaultdict

from .config import ServerConfig


class LoadBalancingAlgorithm(ABC):
    """Abstract base class for load balancing algorithms"""
    
    def __init__(self, servers: List[ServerConfig]):
        self.servers = servers
        self.lock = threading.Lock()
    
    @abstractmethod
    def select_server(self) -> Optional[ServerConfig]:
        """Select a server based on the algorithm"""
        pass
    
    def update_servers(self, servers: List[ServerConfig]):
        """Update the server list"""
        with self.lock:
            self.servers = servers


class RoundRobinAlgorithm(LoadBalancingAlgorithm):
    """Round Robin load balancing algorithm"""
    
    def __init__(self, servers: List[ServerConfig]):
        super().__init__(servers)
        self.current_index = 0
    
    def select_server(self) -> Optional[ServerConfig]:
        """Select next server in round-robin fashion"""
        with self.lock:
            if not self.servers:
                return None
            
            server = self.servers[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.servers)
            return server


class WeightedRoundRobinAlgorithm(LoadBalancingAlgorithm):
    """Weighted Round Robin load balancing algorithm"""
    
    def __init__(self, servers: List[ServerConfig]):
        super().__init__(servers)
        self.weighted_servers = []
        self.current_index = 0
        self._build_weighted_list()
    
    def _build_weighted_list(self):
        """Build weighted server list based on server weights"""
        self.weighted_servers = []
        for server in self.servers:
            self.weighted_servers.extend([server] * server.weight)
    
    def select_server(self) -> Optional[ServerConfig]:
        """Select next server in weighted round-robin fashion"""
        with self.lock:
            if not self.weighted_servers:
                return None
            
            server = self.weighted_servers[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.weighted_servers)
            return server
    
    def update_servers(self, servers: List[ServerConfig]):
        """Update servers and rebuild weighted list"""
        with self.lock:
            self.servers = servers
            self._build_weighted_list()


class LeastConnectionsAlgorithm(LoadBalancingAlgorithm):
    """Least Connections load balancing algorithm"""
    
    def __init__(self, servers: List[ServerConfig]):
        super().__init__(servers)
        self.connection_count = defaultdict(int)
    
    def select_server(self) -> Optional[ServerConfig]:
        """Select server with least connections"""
        with self.lock:
            if not self.servers:
                return None
            
            # Find server with minimum connections
            min_connections = float('inf')
            selected_server = None
            
            for server in self.servers:
                server_key = f"{server.host}:{server.port}"
                connections = self.connection_count[server_key]
                
                if connections < min_connections:
                    min_connections = connections
                    selected_server = server
            
            return selected_server
    
    def increment_connection(self, server: ServerConfig):
        """Increment connection count for a server"""
        with self.lock:
            server_key = f"{server.host}:{server.port}"
            self.connection_count[server_key] += 1
    
    def decrement_connection(self, server: ServerConfig):
        """Decrement connection count for a server"""
        with self.lock:
            server_key = f"{server.host}:{server.port}"
            self.connection_count[server_key] = max(0, self.connection_count[server_key] - 1)


class RandomAlgorithm(LoadBalancingAlgorithm):
    """Random load balancing algorithm"""
    
    def select_server(self) -> Optional[ServerConfig]:
        """Select a random server"""
        with self.lock:
            if not self.servers:
                return None
            return random.choice(self.servers)


def get_algorithm(algorithm_name: str, servers: List[ServerConfig]) -> LoadBalancingAlgorithm:
    """Factory function to get load balancing algorithm"""
    algorithms = {
        "round_robin": RoundRobinAlgorithm,
        "weighted_round_robin": WeightedRoundRobinAlgorithm,
        "least_connections": LeastConnectionsAlgorithm,
        "random": RandomAlgorithm
    }
    
    if algorithm_name not in algorithms:
        raise ValueError(f"Unknown algorithm: {algorithm_name}")
    
    return algorithms[algorithm_name](servers)
