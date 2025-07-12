"""
Test Client Package

This package provides test clients for load balancer testing.
"""

# Export main classes for easier importing
from .test_client import TestClient, ClientManager, run_multiple_clients

__version__ = "1.0.0"
__all__ = [
    "TestClient",
    "ClientManager", 
    "run_multiple_clients"
]
