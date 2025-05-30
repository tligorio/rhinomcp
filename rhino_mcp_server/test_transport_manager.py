#!/usr/bin/env python3
"""
Test script for TransportManager functionality
"""

import os
import sys
from unittest.mock import patch

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp_notifications.transport_manager import (
    TransportManager, TransportConfig, TransportType,
    create_transport_manager, create_stdio_manager, create_sse_manager
)


def test_transport_config():
    """Test TransportConfig creation and methods"""
    print("\n=== Testing TransportConfig ===")
    
    # Test STDIO config
    stdio_config = TransportConfig(transport_type=TransportType.STDIO)
    assert not stdio_config.supports_notifications()
    assert stdio_config.get_startup_kwargs() == {}
    print("✓ STDIO config created correctly")
    
    # Test SSE config
    sse_config = TransportConfig(
        transport_type=TransportType.SSE,
        host="localhost",
        port=3000
    )
    assert sse_config.supports_notifications()
    kwargs = sse_config.get_startup_kwargs()
    assert kwargs["transport"] == "sse"
    assert kwargs["host"] == "localhost"
    assert kwargs["port"] == 3000
    print("✓ SSE config created correctly")
    
    print(f"  STDIO: {stdio_config}")
    print(f"  SSE: {sse_config}")


def test_environment_config():
    """Test configuration from environment variables"""
    print("\n=== Testing Environment Configuration ===")
    
    # Test default (no env vars)
    config = TransportConfig.from_environment()
    assert config.transport_type == TransportType.STDIO
    print("✓ Default config is STDIO")
    
    # Test with environment variables
    with patch.dict(os.environ, {
        'RHINOMCP_TRANSPORT': 'sse',
        'RHINOMCP_HOST': '0.0.0.0',
        'RHINOMCP_PORT': '8080'
    }):
        config = TransportConfig.from_environment()
        assert config.transport_type == TransportType.SSE
        assert config.host == '0.0.0.0'
        assert config.port == 8080
        print("✓ Environment variables parsed correctly")
    
    # Test invalid transport type
    with patch.dict(os.environ, {'RHINOMCP_TRANSPORT': 'invalid'}):
        config = TransportConfig.from_environment()
        assert config.transport_type == TransportType.STDIO  # Should default
        print("✓ Invalid transport type defaults to STDIO")


def test_transport_manager():
    """Test TransportManager functionality"""
    print("\n=== Testing TransportManager ===")
    
    # Test with STDIO
    manager = create_stdio_manager()
    assert manager.transport_type == TransportType.STDIO
    assert not manager.supports_notifications
    print("✓ STDIO manager created")
    
    # Test with SSE
    manager = create_sse_manager(host="localhost", port=4000)
    assert manager.transport_type == TransportType.SSE
    assert manager.supports_notifications
    print("✓ SSE manager created")
    
    # Test startup callbacks
    callback_called = False
    
    def test_callback(server, config):
        nonlocal callback_called
        callback_called = True
        assert config.transport_type == TransportType.SSE
    
    manager.add_startup_callback(test_callback)
    
    # Create a mock server and configure it
    class MockServer:
        pass
    
    mock_server = MockServer()
    manager.configure_server(mock_server)
    
    assert callback_called, "Startup callback should have been called"
    print("✓ Startup callbacks work correctly")


def test_factory_functions():
    """Test factory functions"""
    print("\n=== Testing Factory Functions ===")
    
    # Test environment-based factory
    manager = create_transport_manager()
    assert isinstance(manager, TransportManager)
    print("✓ Environment-based factory works")
    
    # Test custom factory
    manager = create_transport_manager(
        transport_type="sse",
        host="example.com",
        port=9000
    )
    assert manager.transport_type == TransportType.SSE
    assert manager.config.host == "example.com"
    assert manager.config.port == 9000
    print("✓ Custom factory works")
    
    # Test invalid transport type
    try:
        create_transport_manager(transport_type="invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✓ Invalid transport type raises ValueError")


def main():
    """Run all tests"""
    print("🧪 Testing Transport Manager")
    print("=" * 40)
    
    try:
        test_transport_config()
        test_environment_config()
        test_transport_manager()
        test_factory_functions()
        
        print("\n" + "=" * 40)
        print("🎉 All transport manager tests passed!")
        
        # Show example usage
        print("\n📋 Example Usage:")
        print("# STDIO (Claude Desktop):")
        print("RHINOMCP_TRANSPORT=stdio python server.py")
        print("\n# SSE (Web clients):")
        print("RHINOMCP_TRANSPORT=sse RHINOMCP_PORT=2001 python server.py")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 