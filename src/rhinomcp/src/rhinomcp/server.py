# rhino_mcp_server.py
from mcp.server.fastmcp import FastMCP, Context, Image
import socket
import json
import asyncio
import logging
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List
import os
from pathlib import Path
import base64
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RhinoMCPServer")

@dataclass
class RhinoConnection:
    host: str
    port: int
    sock: socket.socket = None  # Changed from 'socket' to 'sock' to avoid naming conflict
    
    def connect(self) -> bool:
        """Connect to the Rhino addon socket server"""
        if self.sock:
            return True
            
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Rhino at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Rhino: {str(e)}")
            self.sock = None
            return False
    
    def disconnect(self):
        """Disconnect from the Rhino addon"""
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logger.error(f"Error disconnecting from Rhino: {str(e)}")
            finally:
                self.sock = None

    def receive_full_response(self, sock, buffer_size=8192):
        """Receive the complete response, potentially in multiple chunks"""
        chunks = []
        # Use a consistent timeout value that matches the addon's timeout
        sock.settimeout(15.0)  # Match the addon's timeout
        
        try:
            while True:
                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        # If we get an empty chunk, the connection might be closed
                        if not chunks:  # If we haven't received anything yet, this is an error
                            raise Exception("Connection closed before receiving any data")
                        break
                    
                    chunks.append(chunk)
                    
                    # Check if we've received a complete JSON object
                    try:
                        data = b''.join(chunks)
                        json.loads(data.decode('utf-8'))
                        # If we get here, it parsed successfully
                        logger.info(f"Received complete response ({len(data)} bytes)")
                        return data
                    except json.JSONDecodeError:
                        # Incomplete JSON, continue receiving
                        continue
                except socket.timeout:
                    # If we hit a timeout during receiving, break the loop and try to use what we have
                    logger.warning("Socket timeout during chunked receive")
                    break
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error(f"Socket connection error during receive: {str(e)}")
                    raise  # Re-raise to be handled by the caller
        except socket.timeout:
            logger.warning("Socket timeout during chunked receive")
        except Exception as e:
            logger.error(f"Error during receive: {str(e)}")
            raise
            
        # If we get here, we either timed out or broke out of the loop
        # Try to use what we have
        if chunks:
            data = b''.join(chunks)
            logger.info(f"Returning data after receive completion ({len(data)} bytes)")
            try:
                # Try to parse what we have
                json.loads(data.decode('utf-8'))
                return data
            except json.JSONDecodeError:
                # If we can't parse it, it's incomplete
                raise Exception("Incomplete JSON response received")
        else:
            raise Exception("No data received")

    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a command to Rhino and return the response"""
        if not self.sock and not self.connect():
            raise ConnectionError("Not connected to Rhino")
        
        command = {
            "type": command_type,
            "params": params or {}
        }
        
        try:
            # Log the command being sent
            logger.info(f"Sending command: {command_type} with params: {params}")
            
            # Send the command
            self.sock.sendall(json.dumps(command).encode('utf-8'))
            logger.info(f"Command sent, waiting for response...")
            
            # Set a timeout for receiving - use the same timeout as in receive_full_response
            self.sock.settimeout(15.0)  # Match the addon's timeout
            
            # Receive the response using the improved receive_full_response method
            response_data = self.receive_full_response(self.sock)
            logger.info(f"Received {len(response_data)} bytes of data")
            
            response = json.loads(response_data.decode('utf-8'))
            logger.info(f"Response parsed, status: {response.get('status', 'unknown')}")
            
            if response.get("status") == "error":
                logger.error(f"Rhino error: {response.get('message')}")
                raise Exception(response.get("message", "Unknown error from Rhino"))
            
            return response.get("result", {})
        except socket.timeout:
            logger.error("Socket timeout while waiting for response from Rhino")
            # Don't try to reconnect here - let the get_rhino_connection handle reconnection
            # Just invalidate the current socket so it will be recreated next time
            self.sock = None
            raise Exception("Timeout waiting for Rhino response - try simplifying your request")
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
            logger.error(f"Socket connection error: {str(e)}")
            self.sock = None
            raise Exception(f"Connection to Rhino lost: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Rhino: {str(e)}")
            # Try to log what was received
            if 'response_data' in locals() and response_data:
                logger.error(f"Raw response (first 200 bytes): {response_data[:200]}")
            raise Exception(f"Invalid response from Rhino: {str(e)}")
        except Exception as e:
            logger.error(f"Error communicating with Rhino: {str(e)}")
            # Don't try to reconnect here - let the get_rhino_connection handle reconnection
            self.sock = None
            raise Exception(f"Communication error with Rhino: {str(e)}")

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

# Resource endpoints

# Global connection for resources (since resources can't access context)
_rhino_connection = None
_polyhaven_enabled = False  # Add this global variable

def get_rhino_connection():
    """Get or create a persistent Rhino connection"""
    global _rhino_connection, _polyhaven_enabled  # Add _polyhaven_enabled to globals
    
    # If we have an existing connection, check if it's still valid
    if _rhino_connection is not None:
        try:
            # First check if PolyHaven is enabled by sending a ping command
            result = _rhino_connection.send_command("get_polyhaven_status")
            # Store the PolyHaven status globally
            _polyhaven_enabled = result.get("enabled", False)
            return _rhino_connection
        except Exception as e:
            # Connection is dead, close it and create a new one
            logger.warning(f"Existing connection is no longer valid: {str(e)}")
            try:
                _rhino_connection.disconnect()
            except:
                pass
            _rhino_connection = None
    
    # Create a new connection if needed
    if _rhino_connection is None:
        _rhino_connection = RhinoConnection(host="127.0.0.1", port=1999)
        if not _rhino_connection.connect():
            logger.error("Failed to connect to Rhino")
            _rhino_connection = None
            raise Exception("Could not connect to Rhino. Make sure the Rhino addon is running.")
        logger.info("Created new persistent connection to Rhino")
    
    return _rhino_connection


@mcp.tool()
def get_scene_info(ctx: Context) -> str:
    """Get detailed information about the current Rhino scene"""
    try:
        rhino = get_rhino_connection()
        result = rhino.send_command("get_scene_info")
        
        # Just return the JSON representation of what Rhino sent us
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting scene info from Rhino: {str(e)}")
        return f"Error getting scene info: {str(e)}"

@mcp.tool()
def get_object_info(ctx: Context, object_name: str) -> str:
    """
    Get detailed information about a specific object in the Rhino scene.
    
    Parameters:
    - object_name: The name of the object to get information about
    """
    try:
        rhino = get_rhino_connection()
        result = rhino.send_command("get_object_info", {"name": object_name})
        
        # Just return the JSON representation of what Rhino sent us
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error getting object info from Rhino: {str(e)}")
        return f"Error getting object info: {str(e)}"



@mcp.tool()
def create_object(
    ctx: Context,
    type: str = "CUBE",
    name: str = None,
    location: List[float] = None,
    rotation: List[float] = None,
    scale: List[float] = None,
    # Torus-specific parameters
    align: str = "WORLD",
    major_segments: int = 48,
    minor_segments: int = 12,
    mode: str = "MAJOR_MINOR",
    major_radius: float = 1.0,
    minor_radius: float = 0.25,
    abso_major_rad: float = 1.25,
    abso_minor_rad: float = 0.75,
    generate_uvs: bool = True
) -> str:
    """
    Create a new object in the Rhino scene.
    
    Parameters:
    - type: Object type (CUBE, SPHERE, CYLINDER, PLANE, CONE, TORUS, EMPTY, CAMERA, LIGHT)
    - name: Optional name for the object
    - location: Optional [x, y, z] location coordinates
    - rotation: Optional [x, y, z] rotation in radians
    - scale: Optional [x, y, z] scale factors (not used for TORUS)
    
    Torus-specific parameters (only used when type == "TORUS"):
    - align: How to align the torus ('WORLD', 'VIEW', or 'CURSOR')
    - major_segments: Number of segments for the main ring
    - minor_segments: Number of segments for the cross-section
    - mode: Dimension mode ('MAJOR_MINOR' or 'EXT_INT')
    - major_radius: Radius from the origin to the center of the cross sections
    - minor_radius: Radius of the torus' cross section
    - abso_major_rad: Total exterior radius of the torus
    - abso_minor_rad: Total interior radius of the torus
    - generate_uvs: Whether to generate a default UV map
    
    Returns:
    A message indicating the created object name.
    """
    try:
        # Get the global connection
        rhino = get_rhino_connection()
        
        # Set default values for missing parameters
        loc = location or [0, 0, 0]
        rot = rotation or [0, 0, 0]
        sc = scale or [1, 1, 1]
        
        params = {
            "type": type,
            "location": loc,
            "rotation": rot,
        }
        
        if name:
            params["name"] = name

        if type == "TORUS":
            # For torus, the scale is not used.
            params.update({
                "align": align,
                "major_segments": major_segments,
                "minor_segments": minor_segments,
                "mode": mode,
                "major_radius": major_radius,
                "minor_radius": minor_radius,
                "abso_major_rad": abso_major_rad,
                "abso_minor_rad": abso_minor_rad,
                "generate_uvs": generate_uvs
            })
            result = rhino.send_command("create_object", params)
            return f"Created {type} object: {result['name']}"
        else:
            # For non-torus objects, include scale
            params["scale"] = sc
            result = rhino.send_command("create_object", params)
            return f"Created {type} object: {result['name']}"
    except Exception as e:
        logger.error(f"Error creating object: {str(e)}")
        return f"Error creating object: {str(e)}"

@mcp.tool()
def modify_object(
    ctx: Context,
    name: str,
    location: List[float] = None,
    rotation: List[float] = None,
    scale: List[float] = None,
    visible: bool = None
) -> str:
    """
    Modify an existing object in the Rhino scene.
    
    Parameters:
    - name: Name of the object to modify
    - location: Optional [x, y, z] location coordinates
    - rotation: Optional [x, y, z] rotation in radians
    - scale: Optional [x, y, z] scale factors
    - visible: Optional boolean to set visibility
    """
    try:
        # Get the global connection
        rhino = get_rhino_connection()
        
        params = {"name": name}
        
        if location is not None:
            params["location"] = location
        if rotation is not None:
            params["rotation"] = rotation
        if scale is not None:
            params["scale"] = scale
        if visible is not None:
            params["visible"] = visible
            
        result = rhino.send_command("modify_object", params)
        return f"Modified object: {result['name']}"
    except Exception as e:
        logger.error(f"Error modifying object: {str(e)}")
        return f"Error modifying object: {str(e)}"

@mcp.tool()
def delete_object(ctx: Context, name: str) -> str:
    """
    Delete an object from the Rhino scene.
    
    Parameters:
    - name: Name of the object to delete
    """
    try:
        # Get the global connection
        rhino = get_rhino_connection()
        
        result = rhino.send_command("delete_object", {"name": name})
        return f"Deleted object: {name}"
    except Exception as e:
        logger.error(f"Error deleting object: {str(e)}")
        return f"Error deleting object: {str(e)}"

@mcp.prompt()
def asset_creation_strategy() -> str:
    """Defines the preferred strategy for creating assets in Rhino"""
    return """When creating 3D content in Rhino, always start by checking if integrations are available:

    0. Before anything, always check the scene from get_scene_info()
    1. Use the method create_object() for basic primitives (CUBE, SPHERE, etc.)
    2. When including an object into scene, ALWAYS make sure that the name of the object is meanful.
    3. After giving the tool location/scale/rotation information (via create_object() and modify_object()),
       double check the related object's location, scale, rotation, and world_bounding_box using get_object_info(),
       so that the object is in the desired location.
    """

# Main execution

def main():
    """Run the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()