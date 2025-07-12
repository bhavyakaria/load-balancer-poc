"""
Simple TCP Test Server for Load Balancer Testing
"""
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime


class TestServer:
    """Simple TCP server for testing the load balancer"""
    
    def __init__(self, host='localhost', port=9001, server_id=None):
        self.host = host
        self.port = port
        self.server_id = server_id or f"Server-{port}"
        self.server = None
        self.running = False
        self.connections = 0
        self.total_connections = 0
        self.logger = self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging"""
        logger = logging.getLogger(f'test_server_{self.port}')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f'%(asctime)s - {self.server_id} - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def start(self):
        """Start the server"""
        if self.running:
            return
        
        self.running = True
        
        try:
            self.server = await asyncio.start_server(
                self._handle_client,
                self.host,
                self.port
            )
            
            self.logger.info(f"Test server started on {self.host}:{self.port}")
            
            # Setup signal handlers (Windows compatible)
            try:
                loop = asyncio.get_running_loop()
                if hasattr(loop, 'add_signal_handler'):
                    for sig in [signal.SIGINT, signal.SIGTERM]:
                        loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                # Signal handlers not supported on Windows
                pass
            
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            raise
    
    async def stop(self):
        """Stop the server"""
        if not self.running:
            return
        
        self.logger.info("Stopping server...")
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        self.logger.info(f"Server stopped. Total connections handled: {self.total_connections}")
    
    async def _handle_client(self, reader, writer):
        """Handle client connection"""
        client_addr = writer.get_extra_info('peername')
        self.connections += 1
        self.total_connections += 1
        
        self.logger.info(f"New connection from {client_addr} (Active: {self.connections})")
        
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                # Echo back the data with server information
                response = f"[{self.server_id}] Echo: {data.decode('utf-8', errors='ignore')}"
                writer.write(response.encode('utf-8'))
                await writer.drain()
                
                self.logger.debug(f"Echoed {len(data)} bytes to {client_addr}")
                
        except asyncio.CancelledError:
            self.logger.debug(f"Connection from {client_addr} cancelled")
        except Exception as e:
            self.logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            self.connections -= 1
            self.logger.info(f"Connection from {client_addr} closed (Active: {self.connections})")
            
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                self.logger.error(f"Error closing connection: {e}")
    
    async def serve_forever(self):
        """Serve forever"""
        await self.start()
        
        try:
            await self.server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
    
    def get_stats(self):
        """Get server statistics"""
        return {
            'server_id': self.server_id,
            'host': self.host,
            'port': self.port,
            'running': self.running,
            'active_connections': self.connections,
            'total_connections': self.total_connections
        }


class ServerManager:
    """Manager for multiple test servers"""
    
    def __init__(self, servers_config):
        self.servers = []
        self.servers_config = servers_config
        
        for config in servers_config:
            server = TestServer(
                host=config.get('host', 'localhost'),
                port=config['port'],
                server_id=config.get('server_id', f"Server-{config['port']}")
            )
            self.servers.append(server)
    
    async def start_all(self):
        """Start all servers"""
        tasks = []
        for server in self.servers:
            task = asyncio.create_task(server.start())
            tasks.append(task)
        
        await asyncio.gather(*tasks)
    
    async def stop_all(self):
        """Stop all servers"""
        tasks = []
        for server in self.servers:
            task = asyncio.create_task(server.stop())
            tasks.append(task)
        
        await asyncio.gather(*tasks)
    
    async def serve_forever(self):
        """Serve forever with all servers"""
        await self.start_all()
        
        # Create tasks for all servers
        tasks = []
        for server in self.servers:
            task = asyncio.create_task(server.serve_forever())
            tasks.append(task)
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\\nShutting down servers...")
            await self.stop_all()
    
    def get_all_stats(self):
        """Get statistics for all servers"""
        return [server.get_stats() for server in self.servers]


async def run_multiple_servers(ports, host='localhost'):
    """Run multiple test servers"""
    servers_config = [
        {'host': host, 'port': port, 'server_id': f"Server-{port}"}
        for port in ports
    ]
    
    manager = ServerManager(servers_config)
    await manager.serve_forever()


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python test_server.py <port> [host]")
        print("   or: python test_server.py multiple <port1> <port2> <port3> [host]")
        sys.exit(1)
    
    if sys.argv[1] == "multiple":
        if len(sys.argv) < 5:
            print("Usage: python test_server.py multiple <port1> <port2> <port3> [host]")
            sys.exit(1)
        
        ports = [int(p) for p in sys.argv[2:5]]
        host = sys.argv[5] if len(sys.argv) > 5 else 'localhost'
        
        print(f"Starting multiple test servers on ports {ports}")
        await run_multiple_servers(ports, host)
    else:
        port = int(sys.argv[1])
        host = sys.argv[2] if len(sys.argv) > 2 else 'localhost'
        
        server = TestServer(host, port)
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
