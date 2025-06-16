# rhino_mcp_server.py
from mcp.server.fastmcp import FastMCP, Context, Image
import socket
import json
import asyncio
import logging, os, pathlib
from logging import FileHandler, Filter
from datetime import datetime
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List
import uuid
import time

from .event_processor import ToolEventProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Setup logging for Claude <--> Rhino  JSON payloads
LOG_DIR = pathlib.Path.home() / "dev" / "logs" / "rhinomcp" 
LOG_DIR.mkdir(exist_ok=True)
session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = LOG_DIR / f"wire_{session_stamp}.log"

class WireFilter(Filter):
    """Allow only log records whose message starts with our wire tags."""
    def filter(self, record):
        return record.msg.startswith("[Claude → Rhino]") \
            or record.msg.startswith("[Rhino → Claude]") \
            or record.msg.startswith("[Rhino → Server]") \
            or record.msg.startswith("[Server → Rhino]")

def log_tool_event(event_type: str, event_data: Dict[str, Any], direction: str = "Rhino → Server", logger: logging.Logger = None):
    """Log a tool-initiated event with standardized format.
    
    Args:
        event_type: Type of the tool event (e.g., 'geometry_added')
        event_data: Dictionary containing event details
        direction: Direction of the event flow ('Rhino → Server' or 'Server → Rhino')
        logger: Logger instance to use (defaults to the global logger)
    """
    if logger is None:
        logger = logging.getLogger("RhinoMCPServer")
        
    event = {
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": event_data
    }
    logger.info(f"[{direction}] {json.dumps(event)}")

fh = FileHandler(log_path, encoding="utf‑8")
fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
fh.addFilter(WireFilter())           # ✱ filter before attach
fh.setLevel(logging.INFO)            # same threshold as default

logger = logging.getLogger("RhinoMCPServer")
logger.addHandler(fh)


@dataclass
class RhinoConnection:
    host: str
    port: int
    sock: socket.socket | None = None
    _is_connected: bool = False
    _last_heartbeat: datetime = field(default_factory=datetime.now)
    _reconnect_attempts: int = 0
    MAX_RECONNECT_ATTEMPTS: int = 3
    HEARTBEAT_INTERVAL: int = 30  # seconds
    
    def connect(self) -> bool:
        """Connect to the Rhino addon socket server with improved error handling."""
        if self.sock and self._is_connected:
            return True
            
        # Don't try to reconnect if we've hit the max attempts
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error("Max reconnection attempts reached")
            return False
            
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self._is_connected = True
            self._reconnect_attempts = 0  # Reset counter on successful connection
            self._last_heartbeat = datetime.now()
            logger.info(f"Connected to Rhino at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Rhino: {str(e)}")
            self._reconnect_attempts += 1  # Increment counter on failure
            self._is_connected = False
            self.sock = None
            
            if self._reconnect_attempts <= self.MAX_RECONNECT_ATTEMPTS:
                logger.info(f"Attempting to reconnect (attempt {self._reconnect_attempts}/{self.MAX_RECONNECT_ATTEMPTS})")
                time.sleep(1)  # Wait before reconnecting
                # Don't recursively call connect, just return False
                return False
            else:
                logger.error("Max reconnection attempts reached")
                return False
    
    def disconnect(self):
        """Disconnect from the Rhino addon with proper cleanup."""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from Rhino: {str(e)}")
            finally:
                self.sock = None
                self._is_connected = False
                self._reconnect_attempts = 0
    
    def _handle_connection_error(self):
        """Handle connection errors and attempt reconnection if possible."""
        self._is_connected = False
        self.sock = None
        return self.connect()  # This will handle the reconnection attempts
    
    def check_connection(self) -> bool:
        """Check if the connection is still alive and handle reconnection if needed."""
        if not self._is_connected:
            return self.connect()
            
        # Check if we need to send a heartbeat
        if (datetime.now() - self._last_heartbeat).total_seconds() > self.HEARTBEAT_INTERVAL:
            try:
                # Only send ping if we have a valid socket
                if self.sock is not None:
                    try:
                        self.sock.sendall(json.dumps({"type": "ping", "params": {}}).encode('utf-8'))
                        self._last_heartbeat = datetime.now()
                        return True
                    except (socket.error, ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                        logger.error(f"Heartbeat failed: {str(e)}")
                        self._is_connected = False
                        self.sock = None
                        self._reconnect_attempts += 1  # Increment counter on heartbeat failure
                        return False
                else:
                    # If no socket, try to reconnect
                    return self.connect()
            except Exception as e:
                logger.error(f"Heartbeat failed: {str(e)}")
                self._is_connected = False
                self.sock = None
                self._reconnect_attempts += 1  # Increment counter on heartbeat failure
                return False
                
        return True

    def receive_full_response(self, sock, buffer_size=8192):
        """Receive the complete response with improved error handling."""
        chunks = []
        sock.settimeout(15.0)
        
        try:
            while True:
                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        if not chunks:
                            raise Exception("Connection closed before receiving any data")
                        break
                    
                    chunks.append(chunk)
                    
                    try:
                        data = b''.join(chunks)
                        json.loads(data.decode('utf-8'))
                        logger.info(f"Received complete response ({len(data)} bytes)")
                        return data
                    except json.JSONDecodeError:
                        continue
                except socket.timeout:
                    logger.warning("Socket timeout during chunked receive")
                    break
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error(f"Socket connection error during receive: {str(e)}")
                    raise
        except Exception as e:
            logger.error(f"Error during receive: {str(e)}")
            raise
            
        if chunks:
            data = b''.join(chunks)
            logger.info(f"Returning data after receive completion ({len(data)} bytes)")
            try:
                json.loads(data.decode('utf-8'))
                return data
            except json.JSONDecodeError:
                raise Exception("Incomplete JSON response received")
        else:
            raise Exception("No data received")

    def send_command(self, command_type: str, params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Send a command to Rhino with improved error handling and reconnection logic."""
        if not self._is_connected or self.sock is None:
            if not self.connect():
                raise ConnectionError("Not connected to Rhino")
        
        command = {
            "type": command_type,
            "params": params or {}
        }

        logger.info("[Claude → Rhino] %s", json.dumps(command))
        
        try:
            logger.info(f"Sending command: {command_type} with params: {params}")
            
            self.sock.sendall(json.dumps(command).encode('utf-8'))
            logger.info(f"Command sent, waiting for response...")
            
            self.sock.settimeout(15.0)
            response_data = self.receive_full_response(self.sock)
            logger.info(f"Received {len(response_data)} bytes of data")
            
            response = json.loads(response_data.decode('utf-8'))
            logger.info("[Rhino → Claude] %s", json.dumps(response))
            logger.info(f"Response parsed, status: {response.get('status', 'unknown')}")
            
            if response.get("status") == "error":
                logger.error(f"Rhino error: {response.get('message')}")
                raise Exception(response.get("message", "Unknown error from Rhino"))
            
            return response.get("result", {})
        except socket.timeout:
            logger.error("Socket timeout while waiting for response from Rhino")
            self._is_connected = False
            self.sock = None
            self._reconnect_attempts += 1  # Increment counter on timeout
            raise Exception("Timeout waiting for Rhino response - try simplifying your request")
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Socket connection error: {str(e)}")
            self._is_connected = False
            self.sock = None
            self._reconnect_attempts += 1  # Increment counter on connection error
            raise Exception(f"Communication error with Rhino: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Rhino: {str(e)}")
            if 'response_data' in locals() and response_data:
                logger.error(f"Raw response (first 200 bytes): {response_data[:200]}")
            raise Exception(f"Invalid response from Rhino: {str(e)}")
        except Exception as e:
            logger.error(f"Error communicating with Rhino: {str(e)}")
            self._is_connected = False
            self.sock = None
            self._reconnect_attempts += 1  # Increment counter on general error
            raise Exception(f"Communication error with Rhino: {str(e)}")

    def send_tool_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a tool-initiated event to Rhino."""
        return self.send_command("tool_event", {
            "event_type": event_type,
            "data": event_data
        })

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    # We don't need to create a connection here since we're using the global connection
    # for resources and tools
    
    try:
        # Just log that we're starting up
        logger.info("RhinoMCP server starting up")
        
        # Try to connect to Rhino on startup to verify it's available
        try:
            # This will initialize the global connection if needed
            rhino = get_rhino_connection()
            logger.info("Successfully connected to Rhino on startup")
        except Exception as e:
            logger.warning(f"Could not connect to Rhino on startup: {str(e)}")
            logger.warning("Make sure the Rhino addon is running before using Rhino resources or tools")
        
        # Return an empty context - we're using the global connection
        yield {}
    finally:
        # Clean up the global connection on shutdown
        global _rhino_connection
        if _rhino_connection:
            logger.info("Disconnecting from Rhino on shutdown")
            _rhino_connection.disconnect()
            _rhino_connection = None
        logger.info("RhinoMCP server shut down")

# Create the MCP server with lifespan support
mcp = FastMCP(
    "RhinoMCP",
    description="Rhino integration through the Model Context Protocol",
    lifespan=server_lifespan
)

# Create event processor instance
event_processor = ToolEventProcessor()

# Resource endpoints

# Global connection for resources (since resources can't access context)
_rhino_connection = None

def get_rhino_connection():
    """Get or create a persistent Rhino connection"""
    global _rhino_connection
    
    # Create a new connection if needed
    if _rhino_connection is None:
        _rhino_connection = RhinoConnection(host="127.0.0.1", port=1999)
        if not _rhino_connection.connect():
            logger.error("Failed to connect to Rhino")
            _rhino_connection = None
            raise Exception("Could not connect to Rhino. Make sure the Rhino addon is running.")
        logger.info("Created new persistent connection to Rhino")
    
    return _rhino_connection

@dataclass
class ToolEvent:
    """Represents a tool-initiated event from Rhino."""
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the event to a dictionary format."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolEvent':
        """Create a ToolEvent from a dictionary."""
        return cls(
            event_type=data["event_type"],
            data=data["data"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )

@mcp.tool()
def tool_event_command(context: Context, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tool-initiated events from Rhino.
    
    Args:
        context: The MCP context
        event_data: The event data from Rhino
        
    Returns:
        Dict containing the response to send back to Rhino
    """
    try:
        # Create a ToolEvent instance
        event = ToolEvent.from_dict(event_data)
        
        # Log the event
        log_tool_event(
            event.event_type,
            event.data,
            "Rhino → Server"
        )
        
        # Process the event using the event processor
        result = event_processor.process_event(event.event_type, event.data)
        
        # Log the response
        log_tool_event(
            "event_acknowledged",
            result,
            "Server → Rhino"
        )
        
        return result
        
    except KeyError as e:
        error_msg = f"Invalid event data: missing required field {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }
    except Exception as e:
        error_msg = f"Error processing tool event: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }

# Main execution
def main():
    """Run the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()