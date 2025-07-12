"""
Layer 4 Load Balancer Implementation
"""
import asyncio
import logging
import signal
import sys
import uuid
from typing import Dict, Optional, Tuple

from .config import LoadBalancerConfig, DEFAULT_CONFIG
from .algorithms import get_algorithm, LeastConnectionsAlgorithm
from .health_check import HealthChecker
from .monitoring import MetricsCollector


class LoadBalancer:
    """Layer 4 Load Balancer using asyncio"""
    
    def __init__(self, config: LoadBalancerConfig = None):
        self.config = config or DEFAULT_CONFIG
        self.logger = self._setup_logging()
        
        # Components
        self.algorithm = get_algorithm(self.config.algorithm, self.config.backend_servers)
        self.health_checker = HealthChecker(self.config.backend_servers, self.config.health_check_interval)
        self.metrics = MetricsCollector()
        
        # Server state
        self.server = None
        self.running = False
        self.connections: Dict[str, Tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}
        
        # Setup health check callback
        self.health_checker.set_health_change_callback(self._on_health_change)
        
        self.logger.info(f"Load Balancer initialized with {len(self.config.backend_servers)} servers")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logger = logging.getLogger('load_balancer')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _on_health_change(self, healthy_servers):
        """Callback when server health changes"""
        self.algorithm.update_servers(healthy_servers)
        self.logger.info(f"Updated algorithm with {len(healthy_servers)} healthy servers")
    
    async def start(self):
        """Start the load balancer"""
        if self.running:
            return
        
        self.running = True
        
        # Start health checker
        self.health_checker.start()
        
        # Start server
        self.server = await asyncio.start_server(
            self._handle_client,
            self.config.listen_host,
            self.config.listen_port
        )
        
        self.logger.info(
            f"Load Balancer started on {self.config.listen_host}:{self.config.listen_port}"
        )
        
        # Setup signal handlers (Windows compatible)
        try:
            loop = asyncio.get_running_loop()
            if hasattr(loop, 'add_signal_handler'):
                for sig in [signal.SIGINT, signal.SIGTERM]:
                    loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
        except NotImplementedError:
            # Signal handlers not supported on Windows
            pass
    
    async def stop(self):
        """Stop the load balancer"""
        if not self.running:
            return
        
        self.logger.info("Stopping load balancer...")
        self.running = False
        
        # Stop accepting new connections
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Close existing connections
        for conn_id, (reader, writer) in self.connections.items():
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                self.logger.error(f"Error closing connection {conn_id}: {e}")
        
        # Stop health checker
        self.health_checker.stop()
        
        self.logger.info("Load balancer stopped")
    
    async def _handle_client(self, client_reader, client_writer):
        """Handle incoming client connection"""
        connection_id = str(uuid.uuid4())
        client_addr = client_writer.get_extra_info('peername')
        
        self.logger.info(f"New connection {connection_id} from {client_addr}")
        
        # Check connection limit
        if len(self.connections) >= self.config.max_concurrent_connections:
            self.logger.warning(f"Connection limit reached, rejecting {connection_id}")
            client_writer.close()
            await client_writer.wait_closed()
            return
        
        # Select backend server
        backend_server = self.algorithm.select_server()
        if not backend_server:
            self.logger.error(f"No backend servers available for {connection_id}")
            client_writer.close()
            await client_writer.wait_closed()
            return
        
        # Check if server is healthy
        if not self.health_checker.is_server_healthy(backend_server):
            self.logger.warning(f"Selected server {backend_server} is unhealthy")
            client_writer.close()
            await client_writer.wait_closed()
            return
        
        # Record connection start
        metrics = self.metrics.record_connection_start(
            connection_id, 
            f"{backend_server.host}:{backend_server.port}"
        )
        
        # Track connection count for least connections algorithm
        if isinstance(self.algorithm, LeastConnectionsAlgorithm):
            self.algorithm.increment_connection(backend_server)
        
        try:
            # Connect to backend server
            backend_reader, backend_writer = await asyncio.wait_for(
                asyncio.open_connection(backend_server.host, backend_server.port),
                timeout=self.config.connection_timeout
            )
            
            self.connections[connection_id] = (client_reader, client_writer)
            
            self.logger.info(f"Connected {connection_id} to {backend_server}")
            
            # Start bidirectional data forwarding
            await self._forward_data(
                connection_id, 
                client_reader, client_writer,
                backend_reader, backend_writer,
                metrics
            )
            
        except asyncio.TimeoutError:
            error_msg = f"Connection timeout to {backend_server}"
            self.logger.error(error_msg)
            self.metrics.record_connection_end(connection_id, metrics, error_msg)
            
        except Exception as e:
            error_msg = f"Error connecting to {backend_server}: {e}"
            self.logger.error(error_msg)
            self.metrics.record_connection_end(connection_id, metrics, error_msg)
            
        finally:
            # Clean up connections
            self.connections.pop(connection_id, None)
            
            # Update connection count for least connections algorithm
            if isinstance(self.algorithm, LeastConnectionsAlgorithm):
                self.algorithm.decrement_connection(backend_server)
            
            # Close client connection
            try:
                client_writer.close()
                await client_writer.wait_closed()
            except Exception as e:
                self.logger.error(f"Error closing client connection {connection_id}: {e}")
    
    async def _forward_data(self, connection_id, client_reader, client_writer, 
                           backend_reader, backend_writer, metrics):
        """Forward data between client and backend server"""
        try:
            # Create forwarding tasks
            client_to_backend = asyncio.create_task(
                self._forward_stream(
                    client_reader, backend_writer, 
                    connection_id, "client->backend", metrics, True
                )
            )
            
            backend_to_client = asyncio.create_task(
                self._forward_stream(
                    backend_reader, client_writer, 
                    connection_id, "backend->client", metrics, False
                )
            )
            
            # Wait for either direction to complete
            done, pending = await asyncio.wait(
                [client_to_backend, backend_to_client],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check for errors
            for task in done:
                try:
                    await task
                except Exception as e:
                    self.logger.error(f"Error in data forwarding for {connection_id}: {e}")
                    raise
            
            # Record successful completion
            self.metrics.record_connection_end(connection_id, metrics)
            
        except Exception as e:
            self.logger.error(f"Error in data forwarding for {connection_id}: {e}")
            self.metrics.record_connection_end(connection_id, metrics, str(e))
            raise
        finally:
            # Close backend connection
            try:
                backend_writer.close()
                await backend_writer.wait_closed()
            except Exception as e:
                self.logger.error(f"Error closing backend connection {connection_id}: {e}")
    
    async def _forward_stream(self, reader, writer, connection_id, direction, metrics, is_client_to_backend):
        """Forward data from reader to writer"""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                
                writer.write(data)
                await writer.drain()
                
                # Record metrics
                if is_client_to_backend:
                    self.metrics.record_data_transfer(metrics, len(data), 0)
                else:
                    self.metrics.record_data_transfer(metrics, 0, len(data))
                
                self.logger.debug(f"Forwarded {len(data)} bytes {direction} for {connection_id}")
                
        except asyncio.CancelledError:
            self.logger.debug(f"Stream forwarding cancelled for {connection_id} ({direction})")
            raise
        except Exception as e:
            self.logger.error(f"Error forwarding stream for {connection_id} ({direction}): {e}")
            raise
    
    async def serve_forever(self):
        """Serve forever"""
        await self.start()
        
        try:
            await self.server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
    
    def get_status(self) -> Dict:
        """Get current load balancer status"""
        return {
            'running': self.running,
            'active_connections': len(self.connections),
            'backend_servers': [str(server) for server in self.config.backend_servers],
            'healthy_servers': [str(server) for server in self.health_checker.get_healthy_servers()],
            'algorithm': self.config.algorithm,
            'metrics': self.metrics.get_overall_stats()
        }
    
    def print_status(self):
        """Print current status"""
        status = self.get_status()
        
        print("\\n" + "="*50)
        print("LOAD BALANCER STATUS")
        print("="*50)
        print(f"Running: {status['running']}")
        print(f"Active Connections: {status['active_connections']}")
        print(f"Algorithm: {status['algorithm']}")
        print(f"Backend Servers: {', '.join(status['backend_servers'])}")
        print(f"Healthy Servers: {', '.join(status['healthy_servers'])}")
        print("="*50)
        
        # Print detailed metrics
        self.metrics.print_stats()


async def main():
    """Main function"""
    # Create load balancer with default config
    lb = LoadBalancer()
    
    try:
        await lb.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down...")
        await lb.stop()


if __name__ == "__main__":
    asyncio.run(main())
