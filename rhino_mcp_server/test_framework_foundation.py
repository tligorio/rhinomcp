#!/usr/bin/env python3
"""
Test script for the MCP Notifications Framework foundation

This script tests the basic functionality we've built so far:
- Event creation and serialization
- Base notifier functionality
- Event handling
"""

import asyncio
import sys
import os
from typing import AsyncIterator
from datetime import datetime

# Add the src directory to Python path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp_notifications.models import StandardEvent, BaseEventType, RhinoEventTypes
from mcp_notifications.base_notifier import BaseMCPNotifier


class TestNotifier(BaseMCPNotifier):
    """A simple test implementation of BaseMCPNotifier for testing"""
    
    def __init__(self):
        super().__init__("TestNotifier")
        self.test_events = [
            # Standard categorized events
            self.create_standard_event(BaseEventType.GEOMETRY, "added", {
                "object_id": "cube_001",
                "object_type": "mesh",
                "vertices": 8,
                "faces": 6
            }),
            self.create_standard_event(BaseEventType.LAYER, "renamed", {
                "old_name": "Layer01",
                "new_name": "Walls",
                "layer_id": "layer_123"
            }),
            # Custom Rhino-specific events
            self.create_custom_event(RhinoEventTypes.NURBS_SURFACE_CREATED, {
                "object_id": "surface_001",
                "degree_u": 3,
                "degree_v": 3,
                "control_points": 16
            }),
            self.create_custom_event(RhinoEventTypes.BOOLEAN_OPERATION, {
                "operation": "union",
                "input_objects": ["obj_001", "obj_002"],
                "result_object": "obj_003"
            })
        ]
        self.event_index = 0
    
    async def detect_events(self) -> AsyncIterator[StandardEvent]:
        """Simulate detecting events by yielding our test events"""
        while self._is_active and self.event_index < len(self.test_events):
            await asyncio.sleep(1)  # Simulate time between events
            if self.event_index < len(self.test_events):
                yield self.test_events[self.event_index]
                self.event_index += 1
    
    async def start_monitoring(self) -> None:
        """Simulate starting monitoring"""
        print(f"✓ {self.name}: Started monitoring")
    
    async def stop_monitoring(self) -> None:
        """Simulate stopping monitoring"""
        print(f"✓ {self.name}: Stopped monitoring")


def test_event_creation():
    """Test creating and serializing events"""
    print("\n=== Testing Event Creation ===")
    
    # Test standard event
    event1 = StandardEvent(
        event_type=BaseEventType.GEOMETRY,
        action="added",
        data={"object_id": "test_001", "type": "cube"}
    )
    
    print(f"✓ Standard event created: {event1.get_full_event_type()}")
    print(f"  Category: {event1.get_event_category()}")
    print(f"  JSON: {event1.to_json()}")
    
    # Test custom event
    event2 = StandardEvent(
        event_type=RhinoEventTypes.NURBS_SURFACE_CREATED,
        action="",  # Custom events have action embedded
        data={"object_id": "surface_001", "degree": 3}
    )
    
    print(f"✓ Custom event created: {event2.get_full_event_type()}")
    print(f"  Category: {event2.get_event_category()}")
    print(f"  JSON: {event2.to_json()}")
    
    # Test event roundtrip (serialize -> deserialize)
    event1_dict = event1.to_log_dict()
    event1_reconstructed = StandardEvent.from_dict(event1_dict.copy())
    
    print(f"✓ Event roundtrip successful: {event1_reconstructed.get_full_event_type()}")


async def test_notifier_lifecycle():
    """Test the notifier start/stop lifecycle"""
    print("\n=== Testing Notifier Lifecycle ===")
    
    notifier = TestNotifier()
    
    # Test initial state
    assert not notifier.is_active, "Notifier should not be active initially"
    print("✓ Notifier created in inactive state")
    
    # Test starting
    await notifier.start()
    assert notifier.is_active, "Notifier should be active after start"
    print("✓ Notifier started successfully")
    
    # Let it run for a moment
    await asyncio.sleep(0.5)
    
    # Test stopping
    await notifier.stop()
    assert not notifier.is_active, "Notifier should be inactive after stop"
    print("✓ Notifier stopped successfully")


async def test_event_handling():
    """Test event emission and handling"""
    print("\n=== Testing Event Handling ===")
    
    notifier = TestNotifier()
    received_events = []
    
    # Add an event handler
    def event_handler(event: StandardEvent):
        received_events.append(event)
        print(f"  📡 Received: {event.get_full_event_type()} from {event.source}")
    
    notifier.add_event_handler(event_handler)
    
    # Start the notifier and let it emit some events
    await notifier.start()
    
    # Wait for events to be emitted
    await asyncio.sleep(3)  # Should receive at least 2-3 events
    
    await notifier.stop()
    
    # Verify we received events
    assert len(received_events) > 0, "Should have received at least one event"
    print(f"✓ Received {len(received_events)} events through handler")
    
    # Verify event metadata is set correctly
    for event in received_events:
        assert event.source == "TestNotifier", f"Event source should be TestNotifier, got {event.source}"
        assert event.session_id is not None, "Event should have session_id"
    
    print("✓ All events have correct metadata")


async def test_concurrent_notifiers():
    """Test multiple notifiers running concurrently"""
    print("\n=== Testing Concurrent Notifiers ===")
    
    notifier1 = TestNotifier()
    notifier1.name = "TestNotifier1"
    
    notifier2 = TestNotifier() 
    notifier2.name = "TestNotifier2"
    
    all_events = []
    
    def event_collector(event: StandardEvent):
        all_events.append(event)
        print(f"  📡 {event.source}: {event.get_full_event_type()}")
    
    notifier1.add_event_handler(event_collector)
    notifier2.add_event_handler(event_collector)
    
    # Start both notifiers
    await notifier1.start()
    await notifier2.start()
    
    # Let them run
    await asyncio.sleep(2)
    
    # Stop both
    await notifier1.stop()
    await notifier2.stop()
    
    # Verify we got events from both
    sources = {event.source for event in all_events}
    assert "TestNotifier1" in sources, "Should have events from TestNotifier1"
    assert "TestNotifier2" in sources, "Should have events from TestNotifier2"
    
    print(f"✓ Received events from {len(sources)} different notifiers")


async def main():
    """Run all tests"""
    print("🧪 Testing MCP Notifications Framework Foundation")
    print("=" * 50)
    
    try:
        # Test basic functionality
        test_event_creation()
        
        # Test async notifier functionality
        await test_notifier_lifecycle()
        await test_event_handling()
        await test_concurrent_notifiers()
        
        print("\n" + "=" * 50)
        print("🎉 All tests passed! Foundation is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 