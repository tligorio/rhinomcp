"""
Transport configuration and management for MCP notifications

Handles different transport methods (STDIO, SSE, HTTP) and provides
a unified interface for starting MCP servers with notification capabilities.
"""

import os
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable
from mcp.server.fastmcp import FastMCP


class TransportType(Enum):
    """Available transport types for MCP communication"""
    STDIO = "stdio"           # Standard input/output (Claude Desktop)
    SSE = "sse"              # Server-Sent Events (Web clients)
    HTTP = "http"            # HTTP with streaming (Web clients)
    STREAMABLE_HTTP = "streamable-http"  # FastMCP streamable HTTP


@dataclass
class TransportConfig:
    """Configuration for a specific transport type"""
    transport_type: TransportType
    host: Optional[str] = None
    port: Optional[int] = None
    additional_params: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_params is None:
            self.additional_params = {}
    
    @classmethod
    def from_environment(cls) -> "TransportConfig":
        """
        Create transport configuration from environment variables
        
        Environment variables:
        - RHINOMCP_TRANSPORT: Transport type (stdio, sse, http, streamable-http)
        - RHINOMCP_HOST: Host for network transports (default: 127.0.0.1)
        - RHINOMCP_PORT: Port for network transports (default: 2001)
        """
        transport_str = os.getenv("RHINOMCP_TRANSPORT", "stdio").lower()
        
        try:
            transport_type = TransportType(transport_str)
        except ValueError:
            logging.warning(f"Unknown transport type '{transport_str}', defaulting to STDIO")
            transport_type = TransportType.STDIO
        
        config = cls(transport_type=transport_type)
        
        # Set network parameters for non-STDIO transports
        if transport_type != TransportType.STDIO:
            config.host = os.getenv("RHINOMCP_HOST", "127.0.0.1")
            config.port = int(os.getenv("RHINOMCP_PORT", "2001"))
        
        return config
    
    def get_startup_kwargs(self) -> Dict[str, Any]:
        """
        Get keyword arguments for FastMCP.run() based on transport type
        """
        if self.transport_type == TransportType.STDIO:
            return {}  # FastMCP defaults to STDIO
        
        kwargs = {
            "transport": self.transport_type.value,
            **self.additional_params
        }
        
        if self.host is not None:
            kwargs["host"] = self.host
        if self.port is not None:
            kwargs["port"] = self.port
            
        return kwargs
    
    def supports_notifications(self) -> bool:
        """
        Check if this transport type supports real-time notifications
        """
        return self.transport_type in [
            TransportType.SSE, 
            TransportType.HTTP, 
            TransportType.STREAMABLE_HTTP
        ]
    
    def __str__(self) -> str:
        if self.transport_type == TransportType.STDIO:
            return "STDIO"
        else:
            return f"{self.transport_type.value.upper()} on {self.host}:{self.port}"


class TransportManager:
    """
    Manages transport configuration and server startup for MCP notifications
    """
    
    def __init__(self, config: Optional[TransportConfig] = None):
        self.config = config or TransportConfig.from_environment()
        self.logger = logging.getLogger("TransportManager")
        self._server: Optional[FastMCP] = None
        self._startup_callbacks: list[Callable[[FastMCP, TransportConfig], None]] = []
    
    def add_startup_callback(self, callback: Callable[[FastMCP, TransportConfig], None]) -> None:
        """
        Add a callback that will be called when the server starts
        
        Args:
            callback: Function that takes (server, config) and sets up additional functionality
        """
        self._startup_callbacks.append(callback)
    
    def remove_startup_callback(self, callback: Callable[[FastMCP, TransportConfig], None]) -> None:
        """Remove a startup callback"""
        if callback in self._startup_callbacks:
            self._startup_callbacks.remove(callback)
    
    def configure_server(self, server: FastMCP) -> None:
        """
        Configure a FastMCP server for the current transport
        
        Args:
            server: The FastMCP server instance to configure
        """
        self._server = server
        
        # Log transport configuration
        self.logger.info(f"Configuring server for transport: {self.config}")
        
        if not self.config.supports_notifications():
            self.logger.warning(
                f"Transport {self.config.transport_type.value} does not support "
                "real-time notifications. Events will only be logged."
            )
        else:
            self.logger.info("Transport supports real-time notifications")
        
        # Call startup callbacks
        for callback in self._startup_callbacks:
            try:
                callback(server, self.config)
            except Exception as e:
                self.logger.error(f"Error in startup callback: {str(e)}")
    
    def run_server(self, server: FastMCP) -> None:
        """
        Run the server with the configured transport
        
        Args:
            server: The FastMCP server instance to run
        """
        self.configure_server(server)
        
        startup_kwargs = self.config.get_startup_kwargs()
        
        self.logger.info(f"Starting MCP server with {self.config}")
        if startup_kwargs:
            self.logger.info(f"Startup parameters: {startup_kwargs}")
        
        try:
            server.run(**startup_kwargs)
        except KeyboardInterrupt:
            self.logger.info("Server stopped by user")
        except Exception as e:
            self.logger.error(f"Server error: {str(e)}")
            raise
    
    @property
    def transport_type(self) -> TransportType:
        """Get the current transport type"""
        return self.config.transport_type
    
    @property
    def supports_notifications(self) -> bool:
        """Check if current transport supports notifications"""
        return self.config.supports_notifications()


def create_transport_manager(
    transport_type: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None
) -> TransportManager:
    """
    Factory function to create a TransportManager
    
    Args:
        transport_type: Override transport type (stdio, sse, http, streamable-http)
        host: Override host for network transports
        port: Override port for network transports
    
    Returns:
        Configured TransportManager instance
    """
    if transport_type is None:
        # Use environment-based configuration
        config = TransportConfig.from_environment()
    else:
        # Create custom configuration
        try:
            transport_enum = TransportType(transport_type.lower())
        except ValueError:
            raise ValueError(f"Unknown transport type: {transport_type}")
        
        config = TransportConfig(
            transport_type=transport_enum,
            host=host,
            port=port
        )
    
    return TransportManager(config)


# Convenience functions for common setups
def create_stdio_manager() -> TransportManager:
    """Create a TransportManager configured for STDIO (Claude Desktop)"""
    config = TransportConfig(transport_type=TransportType.STDIO)
    return TransportManager(config)


def create_sse_manager(host: str = "127.0.0.1", port: int = 2001) -> TransportManager:
    """Create a TransportManager configured for SSE (Web clients)"""
    config = TransportConfig(
        transport_type=TransportType.SSE,
        host=host,
        port=port
    )
    return TransportManager(config)


def create_http_manager(host: str = "127.0.0.1", port: int = 2001) -> TransportManager:
    """Create a TransportManager configured for HTTP (Web clients)"""
    config = TransportConfig(
        transport_type=TransportType.STREAMABLE_HTTP,
        host=host,
        port=port
    )
    return TransportManager(config) 