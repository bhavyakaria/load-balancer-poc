#!/usr/bin/env python3
"""
Test Client Runner Script
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from client import TestClient, run_multiple_clients


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/run_test_client.py single <message> [lb_host] [lb_port]")
        print("  python scripts/run_test_client.py multiple <count> [lb_host] [lb_port] [requests_per_client] [concurrent]")
        print("  python scripts/run_test_client.py load <duration> <rps> [concurrent] [lb_host] [lb_port]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "single":
        if len(sys.argv) < 3:
            print("Usage: python scripts/run_test_client.py single <message> [lb_host] [lb_port]")
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
            print("Usage: python scripts/run_test_client.py multiple <count> [lb_host] [lb_port] [requests_per_client] [concurrent]")
            sys.exit(1)
        
        client_count = int(sys.argv[2])
        lb_host = sys.argv[3] if len(sys.argv) > 3 else 'localhost'
        lb_port = int(sys.argv[4]) if len(sys.argv) > 4 else 8080
        requests_per_client = int(sys.argv[5]) if len(sys.argv) > 5 else 10
        concurrent = int(sys.argv[6]) if len(sys.argv) > 6 else 2
        
        await run_multiple_clients(client_count, lb_host, lb_port, requests_per_client, concurrent)
        
    elif command == "load":
        if len(sys.argv) < 4:
            print("Usage: python scripts/run_test_client.py load <duration> <rps> [concurrent] [lb_host] [lb_port]")
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
