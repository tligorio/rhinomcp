import pytest
import json
import logging
from datetime import datetime
from pathlib import Path
import tempfile
import os

from rhinomcp.server import WireFilter, log_tool_event

@pytest.fixture
def temp_log_file():
    """Create a temporary log file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        return f.name

@pytest.fixture
def test_logger(temp_log_file):
    """Set up a test logger with our WireFilter."""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)
    
    # Create a file handler
    fh = logging.FileHandler(temp_log_file, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
    fh.addFilter(WireFilter())
    fh.setLevel(logging.INFO)
    
    logger.addHandler(fh)
    return logger

def test_wire_filter():
    """Test that WireFilter correctly filters log messages."""
    filter = WireFilter()
    
    # Test valid messages
    assert filter.filter(logging.LogRecord("test", logging.INFO, "", 0, "[Claude → Rhino] test", (), None))
    assert filter.filter(logging.LogRecord("test", logging.INFO, "", 0, "[Rhino → Claude] test", (), None))
    assert filter.filter(logging.LogRecord("test", logging.INFO, "", 0, "[Rhino → Server] test", (), None))
    assert filter.filter(logging.LogRecord("test", logging.INFO, "", 0, "[Server → Rhino] test", (), None))
    
    # Test invalid messages
    assert not filter.filter(logging.LogRecord("test", logging.INFO, "", 0, "Invalid message", (), None))

def test_log_tool_event(test_logger, temp_log_file):
    """Test that tool events are logged correctly."""
    # Test Rhino to Server event
    event_data = {
        "object_id": "test123",
        "layer": "Default",
        "geometry_type": "curve"
    }
    
    log_tool_event("geometry_added", event_data, logger=test_logger)
    
    # Read the log file
    with open(temp_log_file, 'r') as f:
        log_content = f.read()
    
    # Verify log content
    assert "[Rhino → Server]" in log_content
    assert "geometry_added" in log_content
    assert "test123" in log_content
    
    # Verify JSON structure
    log_line = log_content.strip()
    event_json = json.loads(log_line.split("] ")[1])
    assert event_json["event_type"] == "geometry_added"
    assert event_json["data"] == event_data
    assert "timestamp" in event_json

def test_log_tool_event_direction(test_logger, temp_log_file):
    """Test that tool events respect the direction parameter."""
    event_data = {"status": "success"}
    
    # Test Server to Rhino direction
    log_tool_event("event_acknowledged", event_data, "Server → Rhino", logger=test_logger)
    
    with open(temp_log_file, 'r') as f:
        log_content = f.read()
    
    assert "[Server → Rhino]" in log_content
    assert "event_acknowledged" in log_content

def test_log_tool_event_timestamp(test_logger, temp_log_file):
    """Test that tool events include valid timestamps."""
    event_data = {"test": "data"}
    log_tool_event("test_event", event_data, logger=test_logger)
    
    with open(temp_log_file, 'r') as f:
        log_content = f.read()
    
    event_json = json.loads(log_content.strip().split("] ")[1])
    timestamp = datetime.fromisoformat(event_json["timestamp"])
    assert isinstance(timestamp, datetime)
    # Verify timestamp is recent (within last minute)
    assert (datetime.now() - timestamp).total_seconds() < 60 