"""
Notification mixin for FastMCP servers

Provides notification capabilities that can be added to any FastMCP server
through multiple inheritance or composition.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP, Context

from .models import StandardEvent, BaseEventType
from .base_notifier import BaseMCPNotifier
from .transport_manager import TransportManager, TransportConfig


class NotificationMixin:
    """
    Mixin class that adds notification capabilities to FastMCP servers
    
    This mixin can be used with multiple inheritance to extend any FastMCP server:
    
    class MyMCPServer(FastMCP, NotificationMixin):
        def __init__(self):
            super().__init__("MyServer")
            self.init_notifications()
    """
    
    def init_notifications(
        self, 
        transport_manager: Optional[TransportManager] = None,
        logger: Optional[logging.Logger] = None
    ) -> None:
        """
        Initialize notification capabilities
        
        Args:
            transport_manager: Optional transport manager (creates default if None)
            logger: Optional logger (uses server logger if None)
        """
        # Initialize notification attributes
        self._notifiers: Dict[str, BaseMCPNotifier] = {}
        self._notification_active = False
        self._transport_manager = transport_manager or TransportManager()
        
        # Set up logging for notifications
        if logger:
            self._notification_logger = logger
        elif hasattr(self, 'logger'):
            self._notification_logger = self.logger  # Use FastMCP's logger if available
        else:
            self._notification_logger = logging.getLogger(f"Notifications.{getattr(self, 'name', 'Unknown')}")
        
        # Configure transport manager
        self._transport_manager.add_startup_callback(self._on_server_startup)
        
        self._notification_logger.info("Notification system initialized")
    
    def add_notifier(self, notifier: BaseMCPNotifier) -> None:
        """
        Register a notifier with this server
        
        Args:
            notifier: The notifier to register
        """
        if notifier.name in self._notifiers:
            self._notification_logger.warning(f"Notifier {notifier.name} is already registered")
            return
        
        # Add event handler to route events through our broadcasting system
        notifier.add_event_handler(self._handle_notifier_event)
        
        self._notifiers[notifier.name] = notifier
        self._notification_logger.info(f"Registered notifier: {notifier.name}")
        
        # Start the notifier if notifications are active
        if self._notification_active:
            import asyncio
            asyncio.create_task(notifier.start())
    
    def remove_notifier(self, notifier_name: str) -> bool:
        """
        Remove a notifier by name
        
        Args:
            notifier_name: Name of the notifier to remove
            
        Returns:
            True if notifier was removed, False if not found
        """
        if notifier_name not in self._notifiers:
            return False
        
        notifier = self._notifiers.pop(notifier_name)
        
        # Stop the notifier
        if notifier.is_active:
            import asyncio
            asyncio.create_task(notifier.stop())
        
        self._notification_logger.info(f"Removed notifier: {notifier_name}")
        return True
    
    def get_notifier(self, notifier_name: str) -> Optional[BaseMCPNotifier]:
        """Get a notifier by name"""
        return self._notifiers.get(notifier_name)
    
    def list_notifiers(self) -> List[str]:
        """Get list of registered notifier names"""
        return list(self._notifiers.keys())
    
    async def start_notifications(self) -> None:
        """Start all registered notifiers"""
        if self._notification_active:
            self._notification_logger.warning("Notifications are already active")
            return
        
        self._notification_active = True
        self._notification_logger.info("Starting notification system")
        
        # Start all registered notifiers
        for notifier in self._notifiers.values():
            try:
                await notifier.start()
                self._notification_logger.info(f"Started notifier: {notifier.name}")
            except Exception as e:
                self._notification_logger.error(f"Failed to start notifier {notifier.name}: {str(e)}")
    
    async def stop_notifications(self) -> None:
        """Stop all registered notifiers"""
        if not self._notification_active:
            return
        
        self._notification_logger.info("Stopping notification system")
        self._notification_active = False
        
        # Stop all notifiers
        for notifier in self._notifiers.values():
            try:
                await notifier.stop()
                self._notification_logger.info(f"Stopped notifier: {notifier.name}")
            except Exception as e:
                self._notification_logger.error(f"Error stopping notifier {notifier.name}: {str(e)}")
    
    def _handle_notifier_event(self, event: StandardEvent) -> None:
        """
        Handle events from registered notifiers
        
        This method is called whenever a notifier emits an event.
        It logs the event and broadcasts it to connected clients.
        """
        # Log the event using the existing wire log format
        self._log_notification_event(event)
        
        # Broadcast the event to connected clients (if transport supports it)
        self._broadcast_event(event)
    
    def _log_notification_event(self, event: StandardEvent) -> None:
        """
        Log notification events using the existing wire log format
        
        This extends the existing [Claude → Rhino] / [Rhino → Claude] pattern
        with [Rhino → SSE] for notification events.
        """
        # Create the log entry in the same format as existing wire logs
        log_data = event.to_log_dict()
        
        # Use the same JSON formatting as existing wire logs
        log_message = f"[{event.source} → SSE] {json.dumps(log_data)}"
        
        # Log using the notification logger
        self._notification_logger.info(log_message)
    
    def _broadcast_event(self, event: StandardEvent) -> None:
        """
        Broadcast event to connected clients
        
        This uses FastMCP's built-in broadcasting capabilities when available.
        For STDIO transport, events are only logged (no broadcasting).
        """
        if not self._transport_manager.supports_notifications:
            # STDIO transport - events are only logged
            return
        
        # For SSE/HTTP transports, FastMCP handles the broadcasting automatically
        # when we use the server's context or built-in notification methods
        
        # Note: The actual broadcasting implementation will depend on how FastMCP
        # exposes its SSE/HTTP client management. This is a placeholder for now.
        self._notification_logger.debug(f"Broadcasting event: {event.get_full_event_type()}")
    
    def _on_server_startup(self, server: FastMCP, config: TransportConfig) -> None:
        """
        Callback called when the server starts up
        
        This is called by the TransportManager during server startup.
        """
        self._notification_logger.info(f"Server starting with transport: {config}")
        
        if config.supports_notifications():
            self._notification_logger.info("Transport supports real-time notifications")
        else:
            self._notification_logger.info("Transport only supports logging (no real-time notifications)")
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the notification system
        
        Returns:
            Dictionary with notification system statistics
        """
        stats = {
            "active": self._notification_active,
            "transport_type": self._transport_manager.transport_type.value,
            "supports_notifications": self._transport_manager.supports_notifications,
            "notifiers": {}
        }
        
        for name, notifier in self._notifiers.items():
            stats["notifiers"][name] = {
                "active": notifier.is_active,
                "session_id": notifier.session_id
            }
        
        return stats


class NotificationAwareServer(FastMCP, NotificationMixin):
    """
    A ready-to-use FastMCP server with notification capabilities
    
    This is a convenience class that combines FastMCP with NotificationMixin.
    You can use this instead of multiple inheritance if you prefer.
    """
    
    def __init__(
        self, 
        name: str, 
        description: Optional[str] = None,
        transport_manager: Optional[TransportManager] = None,
        **kwargs
    ):
        # Initialize FastMCP
        super().__init__(name, description=description, **kwargs)
        
        # Initialize notifications
        self.init_notifications(transport_manager=transport_manager)
        
        # Set up lifespan management for notifications
        self._original_lifespan = getattr(self, '_lifespan', None)
        self._lifespan = self._notification_lifespan
    
    @asynccontextmanager
    async def _notification_lifespan(self, app):
        """
        Enhanced lifespan manager that includes notification startup/shutdown
        """
        try:
            # Call original lifespan if it exists
            if self._original_lifespan:
                async with self._original_lifespan(app) as context:
                    # Start notifications
                    await self.start_notifications()
                    yield context
            else:
                # Start notifications
                await self.start_notifications()
                yield {}
        finally:
            # Stop notifications
            await self.stop_notifications()


# Convenience function for creating notification-aware servers
def create_notification_server(
    name: str,
    description: Optional[str] = None,
    transport_type: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None
) -> NotificationAwareServer:
    """
    Factory function to create a notification-aware MCP server
    
    Args:
        name: Server name
        description: Server description
        transport_type: Transport type (stdio, sse, http, streamable-http)
        host: Host for network transports
        port: Port for network transports
    
    Returns:
        NotificationAwareServer instance
    """
    from .transport_manager import create_transport_manager
    
    transport_manager = create_transport_manager(
        transport_type=transport_type,
        host=host,
        port=port
    )
    
    return NotificationAwareServer(
        name=name,
        description=description,
        transport_manager=transport_manager
    ) 