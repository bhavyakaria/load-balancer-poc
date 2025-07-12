"""
Monitoring and Metrics Module for Load Balancer
"""
import time
import threading
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ConnectionMetrics:
    """Metrics for a single connection"""
    start_time: float
    end_time: Optional[float] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    backend_server: Optional[str] = None
    error: Optional[str] = None


class MetricsCollector:
    """Collects and manages load balancer metrics"""
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Connection metrics
        self.total_connections = 0
        self.active_connections = 0
        self.failed_connections = 0
        self.connection_history = deque(maxlen=max_history)
        
        # Server metrics
        self.server_connections = defaultdict(int)
        self.server_active_connections = defaultdict(int)
        self.server_failed_connections = defaultdict(int)
        self.server_bytes_sent = defaultdict(int)
        self.server_bytes_received = defaultdict(int)
        
        # Performance metrics
        self.response_times = deque(maxlen=max_history)
        self.start_time = time.time()
        
        # Error tracking
        self.errors = defaultdict(int)
    
    def record_connection_start(self, connection_id: str, backend_server: str = None) -> ConnectionMetrics:
        """Record the start of a new connection"""
        with self.lock:
            self.total_connections += 1
            self.active_connections += 1
            
            if backend_server:
                self.server_connections[backend_server] += 1
                self.server_active_connections[backend_server] += 1
            
            metrics = ConnectionMetrics(
                start_time=time.time(),
                backend_server=backend_server
            )
            
            self.connection_history.append(metrics)
            self.logger.debug(f"Connection {connection_id} started to {backend_server}")
            
            return metrics
    
    def record_connection_end(self, connection_id: str, metrics: ConnectionMetrics, error: str = None):
        """Record the end of a connection"""
        with self.lock:
            self.active_connections -= 1
            metrics.end_time = time.time()
            
            if error:
                self.failed_connections += 1
                self.errors[error] += 1
                metrics.error = error
                
                if metrics.backend_server:
                    self.server_failed_connections[metrics.backend_server] += 1
                
                self.logger.warning(f"Connection {connection_id} failed: {error}")
            else:
                # Record response time
                response_time = metrics.end_time - metrics.start_time
                self.response_times.append(response_time)
                
                self.logger.debug(f"Connection {connection_id} completed in {response_time:.3f}s")
            
            if metrics.backend_server:
                self.server_active_connections[metrics.backend_server] -= 1
                self.server_bytes_sent[metrics.backend_server] += metrics.bytes_sent
                self.server_bytes_received[metrics.backend_server] += metrics.bytes_received
    
    def record_data_transfer(self, metrics: ConnectionMetrics, bytes_sent: int, bytes_received: int):
        """Record data transfer for a connection"""
        with self.lock:
            metrics.bytes_sent += bytes_sent
            metrics.bytes_received += bytes_received
    
    def get_overall_stats(self) -> Dict:
        """Get overall load balancer statistics"""
        with self.lock:
            uptime = time.time() - self.start_time
            
            # Calculate average response time
            avg_response_time = 0
            if self.response_times:
                avg_response_time = sum(self.response_times) / len(self.response_times)
            
            # Calculate request rate
            request_rate = self.total_connections / uptime if uptime > 0 else 0
            
            return {
                'uptime_seconds': uptime,
                'total_connections': self.total_connections,
                'active_connections': self.active_connections,
                'failed_connections': self.failed_connections,
                'success_rate': (self.total_connections - self.failed_connections) / self.total_connections if self.total_connections > 0 else 0,
                'average_response_time': avg_response_time,
                'request_rate': request_rate,
                'errors': dict(self.errors)
            }
    
    def get_server_stats(self) -> Dict:
        """Get per-server statistics"""
        with self.lock:
            stats = {}
            
            all_servers = set(self.server_connections.keys()) | set(self.server_active_connections.keys())
            
            for server in all_servers:
                total_conns = self.server_connections[server]
                active_conns = self.server_active_connections[server]
                failed_conns = self.server_failed_connections[server]
                
                stats[server] = {
                    'total_connections': total_conns,
                    'active_connections': active_conns,
                    'failed_connections': failed_conns,
                    'success_rate': (total_conns - failed_conns) / total_conns if total_conns > 0 else 0,
                    'bytes_sent': self.server_bytes_sent[server],
                    'bytes_received': self.server_bytes_received[server]
                }
            
            return stats
    
    def get_recent_response_times(self, count: int = 100) -> List[float]:
        """Get recent response times"""
        with self.lock:
            return list(self.response_times)[-count:]
    
    def reset_metrics(self):
        """Reset all metrics"""
        with self.lock:
            self.total_connections = 0
            self.active_connections = 0
            self.failed_connections = 0
            self.connection_history.clear()
            self.server_connections.clear()
            self.server_active_connections.clear()
            self.server_failed_connections.clear()
            self.server_bytes_sent.clear()
            self.server_bytes_received.clear()
            self.response_times.clear()
            self.errors.clear()
            self.start_time = time.time()
            
            self.logger.info("Metrics reset")
    
    def print_stats(self):
        """Print current statistics"""
        overall = self.get_overall_stats()
        server_stats = self.get_server_stats()
        
        print("\\n" + "="*50)
        print("LOAD BALANCER STATISTICS")
        print("="*50)
        
        print(f"Uptime: {overall['uptime_seconds']:.1f} seconds")
        print(f"Total Connections: {overall['total_connections']}")
        print(f"Active Connections: {overall['active_connections']}")
        print(f"Failed Connections: {overall['failed_connections']}")
        print(f"Success Rate: {overall['success_rate']:.2%}")
        print(f"Average Response Time: {overall['average_response_time']:.3f} seconds")
        print(f"Request Rate: {overall['request_rate']:.2f} requests/second")
        
        if overall['errors']:
            print("\\nErrors:")
            for error, count in overall['errors'].items():
                print(f"  {error}: {count}")
        
        print("\\nServer Statistics:")
        for server, stats in server_stats.items():
            print(f"  {server}:")
            print(f"    Total: {stats['total_connections']}, Active: {stats['active_connections']}")
            print(f"    Failed: {stats['failed_connections']}, Success Rate: {stats['success_rate']:.2%}")
            print(f"    Bytes Sent: {stats['bytes_sent']}, Bytes Received: {stats['bytes_received']}")
        
        print("="*50)
