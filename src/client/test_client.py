"""
Test Client for Load Balancer Testing
"""
import asyncio
import logging
import random
import sys
import time
from datetime import datetime
from typing import List


class TestClient:
    """Test client for load balancer testing"""
    
    def __init__(self, lb_host='localhost', lb_port=8080, client_id=None):
        self.lb_host = lb_host
        self.lb_port = lb_port
        self.client_id = client_id or f"Client-{random.randint(1000, 9999)}"
        self.logger = self._setup_logging()
        
        # Statistics
        self.successful_connections = 0
        self.failed_connections = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.response_times = []
    
    def _setup_logging(self):
        """Setup logging"""
        logger = logging.getLogger(f'test_client_{self.client_id}')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f'%(asctime)s - {self.client_id} - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    async def send_request(self, message: str, timeout: int = 30) -> tuple:
        """Send a single request to the load balancer"""
        start_time = time.time()
        
        try:
            # Connect to load balancer
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.lb_host, self.lb_port),
                timeout=timeout
            )
            
            # Send message
            message_bytes = message.encode('utf-8')
            writer.write(message_bytes)
            await writer.drain()
            
            self.total_bytes_sent += len(message_bytes)
            
            # Read response
            response_data = await asyncio.wait_for(
                reader.read(1024),
                timeout=timeout
            )
            
            self.total_bytes_received += len(response_data)
            response = response_data.decode('utf-8', errors='ignore')
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            end_time = time.time()
            response_time = end_time - start_time
            
            self.successful_connections += 1
            self.response_times.append(response_time)
            
            self.logger.debug(f"Request successful in {response_time:.3f}s: {response[:50]}...")
            
            return True, response, response_time
            
        except Exception as e:
            self.failed_connections += 1
            response_time = time.time() - start_time
            self.logger.error(f"Request failed after {response_time:.3f}s: {e}")
            return False, str(e), response_time
    
    async def send_multiple_requests(self, messages: List[str], concurrent: int = 1, delay: float = 0):
        """Send multiple requests"""
        self.logger.info(f"Sending {len(messages)} requests with {concurrent} concurrent connections")
        
        tasks = []
        semaphore = asyncio.Semaphore(concurrent)
        
        async def send_with_semaphore(message):
            async with semaphore:
                result = await self.send_request(message)
                if delay > 0:
                    await asyncio.sleep(delay)
                return result
        
        # Create tasks for all messages
        for i, message in enumerate(messages):
            task = asyncio.create_task(send_with_semaphore(f"{message} (Request #{i+1})"))
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = 0
        failed = 0
        
        for result in results:
            if isinstance(result, Exception):
                failed += 1
                self.logger.error(f"Task failed: {result}")
            else:
                success, response, response_time = result
                if success:
                    successful += 1
                else:
                    failed += 1
        
        self.logger.info(f"Completed {len(messages)} requests: {successful} successful, {failed} failed")
        
        return results
    
    async def load_test(self, duration: int = 60, requests_per_second: int = 10, concurrent: int = 5):
        """Perform load testing"""
        self.logger.info(f"Starting load test for {duration} seconds at {requests_per_second} RPS with {concurrent} concurrent connections")
        
        end_time = time.time() + duration
        request_count = 0
        
        while time.time() < end_time:
            # Calculate how many requests to send in this batch
            batch_size = min(requests_per_second, concurrent)
            
            # Generate messages
            messages = [f"Load test message {request_count + i}" for i in range(batch_size)]
            
            # Send requests
            await self.send_multiple_requests(messages, concurrent=concurrent)
            
            request_count += batch_size
            
            # Wait to maintain desired rate
            await asyncio.sleep(1.0)
        
        self.logger.info(f"Load test completed. Sent {request_count} requests")
    
    def get_stats(self):
        """Get client statistics"""
        total_requests = self.successful_connections + self.failed_connections
        
        stats = {
            'client_id': self.client_id,
            'total_requests': total_requests,
            'successful_requests': self.successful_connections,
            'failed_requests': self.failed_connections,
            'success_rate': self.successful_connections / total_requests if total_requests > 0 else 0,
            'total_bytes_sent': self.total_bytes_sent,
            'total_bytes_received': self.total_bytes_received,
            'average_response_time': sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            'min_response_time': min(self.response_times) if self.response_times else 0,
            'max_response_time': max(self.response_times) if self.response_times else 0
        }
        
        return stats
    
    def print_stats(self):
        """Print client statistics"""
        stats = self.get_stats()
        
        print("\\n" + "="*50)
        print(f"CLIENT STATISTICS - {stats['client_id']}")
        print("="*50)
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Successful Requests: {stats['successful_requests']}")
        print(f"Failed Requests: {stats['failed_requests']}")
        print(f"Success Rate: {stats['success_rate']:.2%}")
        print(f"Total Bytes Sent: {stats['total_bytes_sent']}")
        print(f"Total Bytes Received: {stats['total_bytes_received']}")
        print(f"Average Response Time: {stats['average_response_time']:.3f}s")
        print(f"Min Response Time: {stats['min_response_time']:.3f}s")
        print(f"Max Response Time: {stats['max_response_time']:.3f}s")
        print("="*50)


class ClientManager:
    """Manager for multiple test clients"""
    
    def __init__(self, client_count: int, lb_host='localhost', lb_port=8080):
        self.clients = []
        self.lb_host = lb_host
        self.lb_port = lb_port
        
        for i in range(client_count):
            client = TestClient(lb_host, lb_port, f"Client-{i+1}")
            self.clients.append(client)
    
    async def run_load_test(self, requests_per_client: int = 10, concurrent: int = 2):
        """Run load test with all clients"""
        tasks = []
        
        for client in self.clients:
            messages = [f"Message {j+1} from {client.client_id}" for j in range(requests_per_client)]
            task = asyncio.create_task(client.send_multiple_requests(messages, concurrent=concurrent))
            tasks.append(task)
        
        # Wait for all clients to complete
        await asyncio.gather(*tasks)
    
    def print_all_stats(self):
        """Print statistics for all clients"""
        for client in self.clients:
            client.print_stats()
        
        # Print overall statistics
        total_requests = sum(client.successful_connections + client.failed_connections for client in self.clients)
        total_successful = sum(client.successful_connections for client in self.clients)
        total_failed = sum(client.failed_connections for client in self.clients)
        
        print("\\n" + "="*50)
        print("OVERALL STATISTICS")
        print("="*50)
        print(f"Total Clients: {len(self.clients)}")
        print(f"Total Requests: {total_requests}")
        print(f"Total Successful: {total_successful}")
        print(f"Total Failed: {total_failed}")
        print(f"Overall Success Rate: {total_successful / total_requests:.2%}" if total_requests > 0 else "N/A")
        print("="*50)


async def run_multiple_clients(client_count: int, lb_host='localhost', lb_port=8080, 
                              requests_per_client: int = 10, concurrent: int = 2):
    """Run multiple test clients"""
    manager = ClientManager(client_count, lb_host, lb_port)
    await manager.run_load_test(requests_per_client, concurrent)
    manager.print_all_stats()


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_client.py single <message> [lb_host] [lb_port]")
        print("  python test_client.py multiple <count> [lb_host] [lb_port] [requests_per_client] [concurrent]")
        print("  python test_client.py load <duration> <rps> [concurrent] [lb_host] [lb_port]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "single":
        if len(sys.argv) < 3:
            print("Usage: python test_client.py single <message> [lb_host] [lb_port]")
            sys.exit(1)
        
        message = sys.argv[2]
        lb_host = sys.argv[3] if len(sys.argv) > 3 else 'localhost'
        lb_port = int(sys.argv[4]) if len(sys.argv) > 4 else 8080
        
        client = TestClient(lb_host, lb_port)
        success, response, response_time = await client.send_request(message)
        
        print(f"Request {'successful' if success else 'failed'}")
        print(f"Response time: {response_time:.3f}s")
        print(f"Response: {response}")
        
    elif command == "multiple":
        if len(sys.argv) < 3:
            print("Usage: python test_client.py multiple <count> [lb_host] [lb_port] [requests_per_client] [concurrent]")
            sys.exit(1)
        
        client_count = int(sys.argv[2])
        lb_host = sys.argv[3] if len(sys.argv) > 3 else 'localhost'
        lb_port = int(sys.argv[4]) if len(sys.argv) > 4 else 8080
        requests_per_client = int(sys.argv[5]) if len(sys.argv) > 5 else 10
        concurrent = int(sys.argv[6]) if len(sys.argv) > 6 else 2
        
        await run_multiple_clients(client_count, lb_host, lb_port, requests_per_client, concurrent)
        
    elif command == "load":
        if len(sys.argv) < 4:
            print("Usage: python test_client.py load <duration> <rps> [concurrent] [lb_host] [lb_port]")
            sys.exit(1)
        
        duration = int(sys.argv[2])
        rps = int(sys.argv[3])
        concurrent = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        lb_host = sys.argv[5] if len(sys.argv) > 5 else 'localhost'
        lb_port = int(sys.argv[6]) if len(sys.argv) > 6 else 8080
        
        client = TestClient(lb_host, lb_port, "LoadTestClient")
        await client.load_test(duration, rps, concurrent)
        client.print_stats()
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
