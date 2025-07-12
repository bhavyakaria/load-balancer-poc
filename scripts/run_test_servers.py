#!/usr/bin/env python3
"""
Test Server Runner Script
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from server import TestServer
from server.test_server import run_multiple_servers


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_test_servers.py <port> [host]")
        print("   or: python scripts/run_test_servers.py multiple <port1> <port2> <port3> [host]")
        sys.exit(1)
    
    if sys.argv[1] == "multiple":
        if len(sys.argv) < 5:
            print("Usage: python scripts/run_test_servers.py multiple <port1> <port2> <port3> [host]")
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
