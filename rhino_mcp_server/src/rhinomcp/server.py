# rhino_mcp_server.py
from mcp.server.fastmcp import FastMCP, Context, Image
import socket
import json
import asyncio
import uuid
import logging, os, pathlib, tempfile
from logging import FileHandler, Filter
from datetime import datetime
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- File Handler for Wire Log ---
# Use project-local logs directory instead of system temp
project_root = pathlib.Path(__file__).parent.parent.parent
LOG_DIR = project_root / "logs"
LOG_DIR.mkdir(exist_ok=True)
session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = LOG_DIR / f"wire_{session_stamp}.log"

class WireFilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().startswith(("[Claude → Rhino]", "[Rhino → Claude]", "[Rhino -> Server]"))

# Get the root logger
logger = logging.getLogger()

# Create and configure the file handler
fh = logging.FileHandler(log_path, encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
fh.addFilter(WireFilter())

# Add the handler to the root logger
logger.addHandler(fh)

# Log the location for debugging
logger.info(f"Wire log file: {log_path}")

# Global connection instance
_global_rhino_connection: "RhinoConnection" = None

@dataclass
class RhinoConnection:
    host: str
    port: int
    sock: socket.socket | None = None
    pending_requests: Dict[str, asyncio.Future] = field(default_factory=dict)
    listener_task: asyncio.Task | None = None
    # Command execution context tracking
    active_command_context: Dict[str, Any] = field(default_factory=dict)
    command_timeout: float = 5.0  # seconds to associate events with commands
    
    async def connect(self) -> bool:
        """Connect to the Rhino addon socket server"""
        if self.sock:
            return True
            
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setblocking(False)  # Set to non-blocking for async operations
            
            # Use asyncio to connect
            await asyncio.get_running_loop().sock_connect(self.sock, (self.host, self.port))
            
            # Start the listener task
            self.listener_task = asyncio.create_task(self._listen())
            
            logger.info(f"Connected to Rhino at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Rhino: {str(e)}")
            self.sock = None
            return False
    
    def _is_user_initiated_event(self) -> bool:
        """Check if an event is user-initiated (not triggered by a recent command)"""
        current_time = time.time()
        
        # Check if we have any recent commands
        for request_id, context in self.active_command_context.items():
            if current_time - context['timestamp'] < self.command_timeout:
                return False  # Command-triggered event
        
        return True  # User-initiated event
    
    def _cleanup_old_contexts(self):
        """Remove old command contexts"""
        current_time = time.time()
        expired_contexts = [
            request_id for request_id, context in self.active_command_context.items()
            if current_time - context['timestamp'] > self.command_timeout
        ]
        for request_id in expired_contexts:
            del self.active_command_context[request_id]
    
    async def _listen(self):
        """Listen for incoming messages from Rhino"""
        while self.sock and not self.sock._closed:
            try:
                response_data = await asyncio.get_running_loop().sock_recv(self.sock, 8192)
                if not response_data:
                    logger.warning("Connection to Rhino closed")
                    self.disconnect()
                    break
                
                response = json.loads(response_data.decode('utf-8'))
                request_id = response.get("request_id")
                
                if request_id and request_id in self.pending_requests:
                    logger.info(f"[Rhino → Claude] {json.dumps(response)}")
                    
                    # Remove the command context as it's complete
                    if request_id in self.active_command_context:
                        del self.active_command_context[request_id]
                    
                    future = self.pending_requests.pop(request_id)
                    future.set_result(response.get("result", {}))
                elif response.get("type") == "event":
                    # Clean up old contexts first
                    self._cleanup_old_contexts()
                    
                    # Only log user-initiated events
                    if self._is_user_initiated_event():
                        logger.info(f"[Rhino -> Server] (user-initiated) {json.dumps(response)}")
                else:
                    logger.warning(f"Received unexpected message from Rhino: {response}")
            except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                logger.error(f"Socket connection error: {str(e)}")
                self.disconnect()
                break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from Rhino: {str(e)}")
            except Exception as e:
                logger.error(f"Error in listener: {str(e)}")
                self.disconnect()
                break
    
    def disconnect(self):
        """Disconnect from the Rhino addon"""
        if self.listener_task and not self.listener_task.done():
            self.listener_task.cancel()
        
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from Rhino: {str(e)}")
            finally:
                self.sock = None

    async def send_command(self, command_type: str, params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Send a command to Rhino and return the response"""
        if not self.sock and not await self.connect():
            raise ConnectionError("Not connected to Rhino")
        
        request_id = str(uuid.uuid4())
        command = {
            "type": command_type,
            "params": params or {},
            "request_id": request_id
        }

        # Track command execution context
        self.active_command_context[request_id] = {
            'command_type': command_type,
            'timestamp': time.time()
        }

        # Log the full Claude → Rhino command
        logger.info("[Claude → Rhino] %s", json.dumps(command))
        
        try:
            # Log the command being sent
            logger.info(f"Sending command: {command_type} with params: {params}")

            if self.sock is None:
                raise Exception("Socket is not connected")
            
            # Send the command using async socket operations
            command_bytes = json.dumps(command).encode('utf-8')
            await asyncio.get_running_loop().sock_sendall(self.sock, command_bytes)
            logger.info(f"Command sent, waiting for response...")
            
            # Create a future to wait for the response
            future = asyncio.get_running_loop().create_future()
            self.pending_requests[request_id] = future
            
            # Wait for the response with a timeout
            try:
                return await asyncio.wait_for(future, timeout=15.0)
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for response from Rhino")
                if request_id in self.pending_requests:
                    del self.pending_requests[request_id]
                # Clean up command context on timeout
                if request_id in self.active_command_context:
                    del self.active_command_context[request_id]
                raise Exception("Timeout waiting for Rhino response - try simplifying your request")

        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Socket connection error: {str(e)}")
            # Clean up command context on error
            if request_id in self.active_command_context:
                del self.active_command_context[request_id]
            self.sock = None
            raise Exception(f"Connection to Rhino lost: {str(e)}")
        except Exception as e:
            logger.error(f"Error communicating with Rhino: {str(e)}")
            # Clean up command context on error
            if request_id in self.active_command_context:
                del self.active_command_context[request_id]
            # Don't try to reconnect here - let the get_rhino_connection handle reconnection
            self.sock = None
            raise Exception(f"Communication error with Rhino: {str(e)}")

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    global _global_rhino_connection
    
    connection = RhinoConnection(host="127.0.0.1", port=1999)
    try:
        await connection.connect()
        _global_rhino_connection = connection
        logger.info("RhinoMCP server started up and connected to Rhino.")
        yield
    finally:
        if _global_rhino_connection:
            logger.info("Disconnecting from Rhino on shutdown")
            _global_rhino_connection.disconnect()
            _global_rhino_connection = None
        logger.info("RhinoMCP server shut down")


# Create the MCP server with lifespan support
mcp = FastMCP(
    "RhinoMCP",
    description="Rhino integration through the Model Context Protocol",
    lifespan=server_lifespan
)

# Resource endpoints

def get_rhino_connection(ctx: Context) -> RhinoConnection:
    """Get the persistent Rhino connection from the global state."""
    global _global_rhino_connection
    if _global_rhino_connection is None:
        raise ConnectionError("Rhino connection not initialized")
    return _global_rhino_connection

# Main execution
def main():
    """Run the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()