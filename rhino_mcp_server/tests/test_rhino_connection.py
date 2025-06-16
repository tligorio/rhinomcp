import pytest
from datetime import datetime, timedelta
import socket
from unittest.mock import Mock, patch
from rhinomcp.server import RhinoConnection

@pytest.fixture
def mock_socket():
    """Create a mock socket for testing."""
    with patch('socket.socket') as mock:
        yield mock

@pytest.fixture
def connection(mock_socket):
    """Create a RhinoConnection instance for testing."""
    return RhinoConnection(host="127.0.0.1", port=1999)

def test_connection_success(connection, mock_socket):
    """Test successful connection."""
    assert connection.connect()
    assert connection._is_connected
    assert connection._reconnect_attempts == 0
    mock_socket.return_value.connect.assert_called_once_with(("127.0.0.1", 1999))

def test_connection_failure(connection, mock_socket):
    """Test connection failure."""
    mock_socket.return_value.connect.side_effect = socket.error("Connection refused")
    assert not connection.connect()
    assert not connection._is_connected
    assert connection._reconnect_attempts == 1

def test_disconnect(connection, mock_socket):
    """Test disconnecting."""
    connection.connect()
    connection.disconnect()
    assert not connection._is_connected
    assert connection.sock is None
    assert connection._reconnect_attempts == 0
    mock_socket.return_value.close.assert_called_once()

def test_send_command_success(connection, mock_socket):
    """Test successful command sending."""
    # Mock successful response
    mock_socket.return_value.recv.return_value = b'{"status": "success", "result": {"message": "ok"}}'
    
    connection.connect()
    response = connection.send_command("test_command", {"param": "value"})
    
    assert response == {"message": "ok"}
    mock_socket.return_value.sendall.assert_called_once()

def test_send_command_connection_error(connection, mock_socket):
    """Test command sending with connection error."""
    mock_socket.return_value.sendall.side_effect = socket.error("Connection lost")
    
    connection.connect()
    with pytest.raises(Exception) as exc_info:
        connection.send_command("test_command", {"param": "value"})
    
    assert "Communication error with Rhino" in str(exc_info.value)
    assert connection._reconnect_attempts == 1

def test_send_tool_event(connection, mock_socket):
    """Test sending a tool event."""
    # Mock successful response
    mock_socket.return_value.recv.return_value = b'{"status": "success", "result": {"message": "event received"}}'
    
    connection.connect()
    response = connection.send_tool_event("geometry_added", {"object_id": "test123"})
    
    assert response == {"message": "event received"}
    mock_socket.return_value.sendall.assert_called_once()

def test_heartbeat(connection, mock_socket):
    """Test connection heartbeat."""
    # Mock successful response for both initial connect and heartbeat
    mock_socket.return_value.recv.side_effect = [
        b'{"status": "success", "result": {}}',  # Initial connect response
        b'{"status": "success", "result": {}}'   # Heartbeat response
    ]
    
    connection.connect()
    initial_heartbeat = connection._last_heartbeat
    
    # Simulate time passing
    connection._last_heartbeat = datetime.now() - timedelta(seconds=31)
    
    assert connection.check_connection()
    assert connection._last_heartbeat > initial_heartbeat

def test_heartbeat_failure(connection, mock_socket):
    """Test heartbeat failure."""
    # Mock successful initial connect
    mock_socket.return_value.recv.return_value = b'{"status": "success", "result": {}}'
    
    # Connect successfully first
    assert connection.connect()
    assert connection._is_connected
    
    # Set up the socket to fail on sendall during heartbeat
    mock_socket.return_value.sendall.side_effect = socket.error("Connection lost")
    
    # Force a heartbeat check
    connection._last_heartbeat = datetime.now() - timedelta(seconds=31)
    
    # Check connection should fail
    assert not connection.check_connection()
    assert not connection._is_connected
    assert connection.sock is None
    assert connection._reconnect_attempts == 1

def test_max_reconnect_attempts(connection, mock_socket):
    """Test maximum reconnection attempts."""
    mock_socket.return_value.connect.side_effect = socket.error("Connection refused")
    
    # Try to connect multiple times
    for _ in range(4):
        connection.connect()
    
    assert connection._reconnect_attempts == 3
    assert not connection._is_connected 