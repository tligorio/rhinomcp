#!/usr/bin/env python3
"""
Test script for NotificationMixin functionality
"""

import asyncio
import sys
import os
from typing import AsyncIterator
from unittest.mock import Mock, patch

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp_notifications.mixins import NotificationMixin, NotificationAwareServer, create_notification_server
from mcp_notifications.models import StandardEvent, BaseEventType
from mcp_notifications.base_notifier import BaseMCPNotifier
from mcp_notifications.transport_manager import create_stdio_manager, create_sse_manager


class TestNotifier(BaseMCPNotifier):
    """Test notifier for mixin testing"""
    
    def __init__(self, name: str = "TestNotifier"):
        super().__init__(name)
        self.events_to_emit = []
        self.event_index = 0
    
    def add_test_event(self, event: StandardEvent):
        """Add an event to be emitted during testing"""
        self.events_to_emit.append(event)
    
    async def detect_events(self) -> AsyncIterator[StandardEvent]:
        """Emit test events"""
        while self._is_active and self.event_index < len(self.events_to_emit):
            await asyncio.sleep(0.1)  # Small delay
            if self.event_index < len(self.events_to_emit):
                yield self.events_to_emit[self.event_index]
                self.event_index += 1
    
    async def start_monitoring(self) -> None:
        """Start test monitoring"""
        pass
    
    async def stop_monitoring(self) -> None:
        """Stop test monitoring"""
        pass


class TestServer(NotificationMixin):
    """Test server class that uses NotificationMixin"""
    
    def __init__(self, name: str = "TestServer"):
        self.name = name
        self.logger = Mock()
        self.init_notifications()


def test_mixin_initialization():
    """Test NotificationMixin initialization"""
    print("\n=== Testing Mixin Initialization ===")
    
    server = TestServer()
    
    # Check initialization
    assert hasattr(server, '_notifiers')
    assert hasattr(server, '_notification_active')
    assert hasattr(server, '_transport_manager')
    assert len(server.list_notifiers()) == 0
    
    print("✓ Mixin initialized correctly")


def test_notifier_registration():
    """Test notifier registration and management"""
    print("\n=== Testing Notifier Registration ===")
    
    server = TestServer()
    notifier1 = TestNotifier("Notifier1")
    notifier2 = TestNotifier("Notifier2")
    
    # Test adding notifiers
    server.add_notifier(notifier1)
    server.add_notifier(notifier2)
    
    assert len(server.list_notifiers()) == 2
    assert "Notifier1" in server.list_notifiers()
    assert "Notifier2" in server.list_notifiers()
    
    print("✓ Notifiers registered successfully")
    
    # Test getting notifiers
    retrieved = server.get_notifier("Notifier1")
    assert retrieved is notifier1
    
    print("✓ Notifier retrieval works")
    
    # Test removing notifiers
    removed = server.remove_notifier("Notifier1")
    assert removed
    assert len(server.list_notifiers()) == 1
    assert "Notifier1" not in server.list_notifiers()
    
    # Test removing non-existent notifier
    removed = server.remove_notifier("NonExistent")
    assert not removed
    
    print("✓ Notifier removal works")


async def test_notification_lifecycle():
    """Test notification system lifecycle"""
    print("\n=== Testing Notification Lifecycle ===")
    
    server = TestServer()
    notifier = TestNotifier()
    
    # Add test events
    notifier.add_test_event(StandardEvent(
        event_type=BaseEventType.GEOMETRY,
        action="added",
        data={"object_id": "test_001"}
    ))
    
    server.add_notifier(notifier)
    
    # Test starting notifications
    await server.start_notifications()
    assert server._notification_active
    assert notifier.is_active
    
    print("✓ Notifications started successfully")
    
    # Let it run briefly
    await asyncio.sleep(0.2)
    
    # Test stopping notifications
    await server.stop_notifications()
    assert not server._notification_active
    assert not notifier.is_active
    
    print("✓ Notifications stopped successfully")


async def test_event_handling():
    """Test event handling and logging"""
    print("\n=== Testing Event Handling ===")
    
    server = TestServer()
    notifier = TestNotifier()
    
    # Mock the logger to capture log calls
    captured_logs = []
    
    def mock_log_info(message):
        captured_logs.append(message)
    
    server._notification_logger.info = mock_log_info
    
    # Add test events
    test_event = StandardEvent(
        event_type=BaseEventType.GEOMETRY,
        action="added",
        data={"object_id": "cube_001", "type": "mesh"}
    )
    notifier.add_test_event(test_event)
    
    server.add_notifier(notifier)
    
    # Start and let it emit events
    await server.start_notifications()
    await asyncio.sleep(0.2)  # Let it emit the event
    await server.stop_notifications()
    
    # Check that events were logged
    log_messages = [log for log in captured_logs if "→ SSE" in log]
    assert len(log_messages) > 0, "Should have logged at least one SSE event"
    
    # Check log format
    sse_log = log_messages[0]
    assert "[TestNotifier → SSE]" in sse_log
    assert "geometry.added" in sse_log
    assert "cube_001" in sse_log
    
    print("✓ Event logging works correctly")
    print(f"  Sample log: {sse_log}")


def test_notification_aware_server():
    """Test the NotificationAwareServer class"""
    print("\n=== Testing NotificationAwareServer ===")
    
    # Test with STDIO transport
    server = create_notification_server(
        name="TestServer",
        description="Test server",
        transport_type="stdio"
    )
    
    assert server.name == "TestServer"
    assert hasattr(server, '_notifiers')
    assert not server._transport_manager.supports_notifications
    
    print("✓ STDIO server created successfully")
    
    # Test with SSE transport
    server = create_notification_server(
        name="TestSSEServer",
        transport_type="sse",
        host="localhost",
        port=3000
    )
    
    assert server._transport_manager.supports_notifications
    
    print("✓ SSE server created successfully")


def test_notification_stats():
    """Test notification statistics"""
    print("\n=== Testing Notification Stats ===")
    
    server = TestServer()
    notifier1 = TestNotifier("Stats1")
    notifier2 = TestNotifier("Stats2")
    
    server.add_notifier(notifier1)
    server.add_notifier(notifier2)
    
    stats = server.get_notification_stats()
    
    assert "active" in stats
    assert "transport_type" in stats
    assert "supports_notifications" in stats
    assert "notifiers" in stats
    assert len(stats["notifiers"]) == 2
    assert "Stats1" in stats["notifiers"]
    assert "Stats2" in stats["notifiers"]
    
    print("✓ Notification stats work correctly")
    print(f"  Stats: {stats}")


async def main():
    """Run all tests"""
    print("🧪 Testing Notification Mixin")
    print("=" * 40)
    
    try:
        # Test basic functionality
        test_mixin_initialization()
        test_notifier_registration()
        test_notification_aware_server()
        test_notification_stats()
        
        # Test async functionality
        await test_notification_lifecycle()
        await test_event_handling()
        
        print("\n" + "=" * 40)
        print("🎉 All notification mixin tests passed!")
        
        print("\n📋 Example Usage:")
        print("# Method 1: Multiple inheritance")
        print("class MyServer(FastMCP, NotificationMixin):")
        print("    def __init__(self):")
        print("        super().__init__('MyServer')")
        print("        self.init_notifications()")
        print("")
        print("# Method 2: Use NotificationAwareServer")
        print("server = create_notification_server('MyServer', transport_type='sse')")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 