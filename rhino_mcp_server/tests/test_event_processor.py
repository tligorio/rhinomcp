import pytest
from rhinomcp.event_processor import ToolEventProcessor, EventType, EventValidationResult

@pytest.fixture
def event_processor():
    """Create a ToolEventProcessor instance for testing."""
    return ToolEventProcessor()

def test_process_geometry_added_event(event_processor):
    """Test processing a geometry added event."""
    event_data = {
        "object_id": "test123",
        "geometry_type": "curve"
    }
    
    result = event_processor.process_event("geometry_added", event_data)
    assert result["status"] == "success"
    assert "Geometry added event processed" in result["message"]

def test_process_geometry_modified_event(event_processor):
    """Test processing a geometry modified event."""
    event_data = {
        "object_id": "test123",
        "geometry_type": "curve"
    }
    
    result = event_processor.process_event("geometry_modified", event_data)
    assert result["status"] == "success"
    assert "Geometry modified event processed" in result["message"]

def test_process_layer_added_event(event_processor):
    """Test processing a layer added event."""
    event_data = {
        "layer_name": "TestLayer"
    }
    
    result = event_processor.process_event("layer_added", event_data)
    assert result["status"] == "success"
    assert "Layer added event processed" in result["message"]

def test_process_invalid_event_type(event_processor):
    """Test processing an invalid event type."""
    event_data = {"test": "data"}
    
    result = event_processor.process_event("invalid_event", event_data)
    assert result["status"] == "error"
    assert "Unknown event type" in result["message"]

def test_process_event_missing_required_fields(event_processor):
    """Test processing an event with missing required fields."""
    event_data = {
        "object_id": "test123"
        # Missing geometry_type
    }
    
    result = event_processor.process_event("geometry_added", event_data)
    assert result["status"] == "error"
    assert "Missing required field" in result["message"]

def test_get_event_type(event_processor):
    """Test converting string event type to enum."""
    event_type = event_processor._get_event_type("geometry_added")
    assert event_type == EventType.GEOMETRY_ADDED

def test_validate_event(event_processor):
    """Test event validation."""
    event_data = {
        "object_id": "test123",
        "geometry_type": "curve"
    }
    
    validation = event_processor._validate_event(EventType.GEOMETRY_ADDED, event_data)
    assert validation.is_valid
    assert validation.error_message is None

def test_validate_event_missing_fields(event_processor):
    """Test event validation with missing fields."""
    event_data = {
        "object_id": "test123"
        # Missing geometry_type
    }
    
    validation = event_processor._validate_event(EventType.GEOMETRY_ADDED, event_data)
    assert not validation.is_valid
    assert "Missing required field" in validation.error_message 