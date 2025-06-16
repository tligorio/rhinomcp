import pytest
import socket
import json
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from rhinomcp.server import RhinoConnection, ToolEvent, log_tool_event
from rhinomcp.event_processor import ToolEventProcessor

def handle_client(client_socket, event_processor):
    """Handle client connection in a separate thread."""
    try:
        while True:
            # Receive data
            data = client_socket.recv(1024)
            if not data:
                break
                
            # Parse the command
            command = json.loads(data.decode('utf-8'))
            
            # Process the command
            if command.get("type") == "ping":
                # Handle heartbeat
                response = {"status": "success", "message": "pong"}
            elif command.get("type") == "tool_event":
                # Handle tool event
                params = command.get("params", {})
                result = event_processor.process_event(
                    params.get("event_type"),
                    params.get("data", {})
                )
                response = result  # Return the event processor's response directly
            else:
                response = {
                    "status": "error",
                    "message": f"Unknown command type: {command.get('type')}"
                }
            
            # Send response
            client_socket.sendall(json.dumps(response).encode('utf-8'))
    except Exception as e:
        print(f"Error handling client: {e}")
    finally:
        client_socket.close()

@pytest.fixture
def mock_rhino_server():
    """Create a mock Rhino server socket."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 0))  # Use random port
    server.listen(1)
    yield server
    server.close()

@pytest.fixture
def rhino_connection(mock_rhino_server):
    """Create a RhinoConnection instance connected to the mock server."""
    host, port = mock_rhino_server.getsockname()
    connection = RhinoConnection(host=host, port=port)
    return connection

@pytest.fixture
def event_processor():
    """Create an event processor instance."""
    return ToolEventProcessor()

def test_end_to_end_event_flow(rhino_connection, mock_rhino_server, event_processor):
    """Test the complete flow of an event from Rhino to server and back."""
    # Start server thread
    server_thread = threading.Thread(
        target=lambda: handle_client(mock_rhino_server.accept()[0], event_processor)
    )
    server_thread.daemon = True
    server_thread.start()
    
    # Start the connection
    assert rhino_connection.connect()
    
    # Send a geometry_added event
    event_data = {
        "object_id": "test123",
        "geometry_type": "curve"
    }
    
    # Send the event
    response = rhino_connection.send_tool_event("geometry_added", event_data)
    assert response["status"] == "success"
    assert "Geometry added event processed" in response["message"]

def test_real_heartbeat_behavior(rhino_connection, mock_rhino_server, event_processor):
    """Test the heartbeat mechanism with real socket communication."""
    # Start server thread
    server_thread = threading.Thread(
        target=lambda: handle_client(mock_rhino_server.accept()[0], event_processor)
    )
    server_thread.daemon = True
    server_thread.start()
    
    # Start the connection
    assert rhino_connection.connect()
    
    # Force a heartbeat check
    rhino_connection._last_heartbeat = datetime.now() - timedelta(seconds=31)
    
    # Verify heartbeat is sent and connection is maintained
    assert rhino_connection.check_connection()
    assert rhino_connection._is_connected

def test_connection_recovery(rhino_connection, mock_rhino_server, event_processor):
    """Test how the system recovers from connection drops."""
    # Start server thread
    server_thread = threading.Thread(
        target=lambda: handle_client(mock_rhino_server.accept()[0], event_processor)
    )
    server_thread.daemon = True
    server_thread.start()
    
    # Start the connection
    assert rhino_connection.connect()
    
    # Simulate connection drop by closing the server
    mock_rhino_server.close()
    
    # Force a heartbeat check
    rhino_connection._last_heartbeat = datetime.now() - timedelta(seconds=31)
    
    # Verify connection is marked as disconnected
    assert not rhino_connection.check_connection()
    assert not rhino_connection._is_connected
    assert rhino_connection.sock is None

def test_multiple_events(rhino_connection, mock_rhino_server, event_processor):
    """Test handling multiple events in sequence."""
    # Start server thread
    server_thread = threading.Thread(
        target=lambda: handle_client(mock_rhino_server.accept()[0], event_processor)
    )
    server_thread.daemon = True
    server_thread.start()
    
    # Start the connection
    assert rhino_connection.connect()
    
    # Send multiple events
    events = [
        {
            "event_type": "geometry_added",
            "data": {"object_id": "test1", "geometry_type": "curve"}
        },
        {
            "event_type": "layer_added",
            "data": {"layer_name": "Test Layer"}
        }
    ]
    
    for event in events:
        # Send event
        response = rhino_connection.send_tool_event(
            event["event_type"],
            event["data"]
        )
        
        # Verify response
        assert response["status"] == "success"
        assert f"{event['event_type']} event processed" in response["message"] 