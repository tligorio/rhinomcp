import pytest
from datetime import datetime
from rhinomcp.server import ToolEvent, tool_event_command, Context

def test_tool_event_creation():
    """Test creating a ToolEvent instance."""
    event_data = {
        "event_type": "geometry_added",
        "data": {"object_id": "test123"},
        "timestamp": datetime.now().isoformat()
    }
    
    event = ToolEvent.from_dict(event_data)
    assert event.event_type == "geometry_added"
    assert event.data == {"object_id": "test123"}
    assert isinstance(event.timestamp, datetime)

def test_tool_event_to_dict():
    """Test converting a ToolEvent to dictionary."""
    event = ToolEvent(
        event_type="geometry_added",
        data={"object_id": "test123"}
    )
    
    event_dict = event.to_dict()
    assert event_dict["event_type"] == "geometry_added"
    assert event_dict["data"] == {"object_id": "test123"}
    assert "timestamp" in event_dict

def test_handle_tool_event_success(test_logger):
    """Test successful tool event handling."""
    event_data = {
        "event_type": "geometry_added",
        "data": {
            "object_id": "test123",
            "geometry_type": "curve"
        },
        "timestamp": datetime.now().isoformat()
    }
    
    response = tool_event_command(Context(), event_data)
    assert response["status"] == "success"
    assert "Geometry added event processed" in response["message"]

def test_handle_tool_event_invalid_data(test_logger):
    """Test handling invalid event data."""
    # Missing required field
    event_data = {
        "data": {"object_id": "test123"},
        "timestamp": datetime.now().isoformat()
    }
    
    response = tool_event_command(Context(), event_data)
    assert response["status"] == "error"
    assert "Invalid event data" in response["message"]

def test_handle_tool_event_invalid_timestamp(test_logger):
    """Test handling invalid timestamp format."""
    event_data = {
        "event_type": "geometry_added",
        "data": {"object_id": "test123"},
        "timestamp": "invalid-timestamp"
    }
    
    response = tool_event_command(Context(), event_data)
    assert response["status"] == "error"
    assert "Error processing tool event" in response["message"] 