#!/usr/bin/env python3
"""
Test script for RhinoMCP server integration with notification framework
"""

import asyncio
import sys
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_backward_compatibility():
    """Test that original mcp instance still exists"""
    print("\n=== Testing Backward Compatibility ===")
    
    # Import after path is set
    from rhinomcp.server import mcp
    from mcp.server.fastmcp import FastMCP
    
    # Check that mcp is the original FastMCP instance
    assert isinstance(mcp, FastMCP), "mcp should be a FastMCP instance"
    assert mcp.name == "RhinoMCP", "mcp should have correct name"
    
    print("✓ Original mcp instance available for backward compatibility")


def test_wire_filter():
    """Test that WireFilter includes SSE events"""
    print("\n=== Testing Enhanced WireFilter ===")
    
    # Import after path is set
    from rhinomcp.server import WireFilter
    import logging
    
    filter_instance = WireFilter()
    
    # Create mock log records
    class MockRecord:
        def __init__(self, msg):
            self.msg = msg
    
    # Test existing wire log patterns
    claude_to_rhino = MockRecord("[Claude → Rhino] {\"type\": \"get_objects\"}")
    rhino_to_claude = MockRecord("[Rhino → Claude] {\"status\": \"success\"}")
    
    # Test new SSE pattern
    rhino_to_sse = MockRecord("[Rhino → SSE] {\"event_type\": \"geometry.added\"}")
    
    # Test non-wire messages
    regular_log = MockRecord("Regular log message")
    
    # Verify filtering
    assert filter_instance.filter(claude_to_rhino), "Should accept Claude → Rhino"
    assert filter_instance.filter(rhino_to_claude), "Should accept Rhino → Claude"
    assert filter_instance.filter(rhino_to_sse), "Should accept Rhino → SSE"
    assert not filter_instance.filter(regular_log), "Should reject regular logs"
    
    print("✓ WireFilter correctly handles all wire log types")


async def test_enhanced_server_creation():
    """Test that the enhanced server can be created"""
    print("\n=== Testing Enhanced Server Creation ===")
    
    # Import after path is set
    from rhinomcp.server import create_enhanced_server
    
    server = create_enhanced_server()
    
    # Check server has notification capabilities
    assert hasattr(server, '_notifiers'), "Server should have notifiers"
    assert hasattr(server, '_transport_manager'), "Server should have transport manager"
    
    # Check demo notifier is registered
    notifiers = server.list_notifiers()
    assert "RhinoEventDemo" in notifiers, "Demo notifier should be registered"
    
    print("✓ Enhanced server created successfully")
    print(f"  Registered notifiers: {notifiers}")
    
    return server


async def test_notification_lifecycle():
    """Test notification system lifecycle"""
    print("\n=== Testing Notification Lifecycle ===")
    
    from rhinomcp.server import create_enhanced_server
    
    server = create_enhanced_server()
    
    # Test starting notifications
    await server.start_notifications()
    assert server._notification_active, "Notifications should be active"
    
    # Check that demo notifier is active
    demo_notifier = server.get_notifier("RhinoEventDemo")
    assert demo_notifier is not None, "Demo notifier should exist"
    assert demo_notifier.is_active, "Demo notifier should be active"
    
    print("✓ Notifications started successfully")
    
    # Let it run briefly to emit some events
    await asyncio.sleep(1)
    
    # Test stopping notifications
    await server.stop_notifications()
    assert not server._notification_active, "Notifications should be inactive"
    assert not demo_notifier.is_active, "Demo notifier should be inactive"
    
    print("✓ Notifications stopped successfully")


def test_log_file_creation():
    """Test that wire log file is created with timestamp"""
    print("\n=== Testing Wire Log File Creation ===")
    
    # Import to trigger log file creation
    from rhinomcp.server import log_path, LOG_DIR
    
    assert LOG_DIR.exists(), "Log directory should exist"
    assert log_path.name.startswith("wire_"), "Log file should start with 'wire_'"
    assert log_path.name.endswith(".log"), "Log file should end with '.log'"
    
    print(f"✓ Wire log file: {log_path}")


def test_transport_configuration():
    """Test transport configuration via environment"""
    print("\n=== Testing Transport Configuration ===")
    
    # Test STDIO (default)
    from rhinomcp.server import create_enhanced_server
    
    server = create_enhanced_server()
    transport_type = server._transport_manager.transport_type
    print(f"✓ Default transport: {transport_type.value}")


async def main():
    """Run all integration tests"""
    print("🧪 Testing RhinoMCP Server Integration")
    print("=" * 50)
    
    try:
        # Test basic functionality
        test_backward_compatibility()
        test_wire_filter()
        test_log_file_creation()
        test_transport_configuration()
        
        # Test enhanced server functionality
        await test_enhanced_server_creation()
        await test_notification_lifecycle()
        
        print("\n" + "=" * 50)
        print("🎉 All integration tests passed!")
        
        print("\n📋 How to run the servers:")
        print("# Original server (backward compatibility):")
        print("python -m rhinomcp.server")
        print("")
        print("# Enhanced server with notifications:")
        print("RHINOMCP_ENHANCED=true python -m rhinomcp.server")
        print("")
        print("# Enhanced server with SSE transport:")
        print("RHINOMCP_ENHANCED=true RHINOMCP_TRANSPORT=sse python -m rhinomcp.server")
        print("")
        print("📁 Wire logs will appear in:")
        print(f"   {Path.home() / 'dev' / 'logs' / 'rhinomcp'}")
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 