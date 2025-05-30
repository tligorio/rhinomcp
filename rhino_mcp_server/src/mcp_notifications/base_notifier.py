"""
Abstract base class for MCP notifiers
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Callable, Dict, Any, Optional, List
import asyncio
import logging
from datetime import datetime

from .models import StandardEvent, BaseEventType


class BaseMCPNotifier(ABC):
    """
    Abstract base class for MCP server notifiers
    
    This class defines the interface that all server-specific notifiers
    must implement. It provides the foundation for event detection,
    transformation, and broadcasting.
    """
    
    def __init__(self, name: str, session_id: Optional[str] = None):
        self.name = name
        self.session_id = session_id or f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.logger = logging.getLogger(f"MCPNotifier.{name}")
        self._event_handlers: List[Callable[[StandardEvent], None]] = []
        self._is_active = False
        self._background_task: Optional[asyncio.Task] = None
    
    @abstractmethod
    async def detect_events(self) -> AsyncIterator[StandardEvent]:
        """
        Detect and yield events from the underlying system
        
        This method should be implemented by each specific notifier
        to monitor their respective system (Rhino, Blender, etc.) for changes
        and yield StandardEvent objects when changes occur.
        
        Yields:
            StandardEvent: Events detected from the system
        """
        pass
    
    @abstractmethod
    async def start_monitoring(self) -> None:
        """
        Start monitoring for events
        
        This method should set up any necessary connections or listeners
        to begin detecting events from the underlying system.
        """
        pass
    
    @abstractmethod
    async def stop_monitoring(self) -> None:
        """
        Stop monitoring for events
        
        This method should clean up any connections or listeners
        and stop event detection.
        """
        pass
    
    def add_event_handler(self, handler: Callable[[StandardEvent], None]) -> None:
        """
        Add an event handler that will be called for each detected event
        
        Args:
            handler: Function that takes a StandardEvent and processes it
        """
        self._event_handlers.append(handler)
    
    def remove_event_handler(self, handler: Callable[[StandardEvent], None]) -> None:
        """Remove an event handler"""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)
    
    async def emit_event(self, event: StandardEvent) -> None:
        """
        Emit an event to all registered handlers
        
        Args:
            event: The StandardEvent to emit
        """
        # Ensure the event has the correct source and session_id
        event.source = self.name
        event.session_id = self.session_id
        
        # Call all registered event handlers
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                self.logger.error(f"Error in event handler: {str(e)}")
    
    async def start(self) -> None:
        """
        Start the notifier and begin event monitoring
        """
        if self._is_active:
            self.logger.warning(f"Notifier {self.name} is already active")
            return
        
        self.logger.info(f"Starting notifier: {self.name}")
        self._is_active = True
        
        try:
            await self.start_monitoring()
            # Start the background event detection task
            self._background_task = asyncio.create_task(self._event_loop())
        except Exception as e:
            self._is_active = False
            self.logger.error(f"Failed to start notifier {self.name}: {str(e)}")
            raise
    
    async def stop(self) -> None:
        """
        Stop the notifier and clean up resources
        """
        if not self._is_active:
            return
        
        self.logger.info(f"Stopping notifier: {self.name}")
        self._is_active = False
        
        # Cancel the background task
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None
        
        # Stop monitoring
        try:
            await self.stop_monitoring()
        except Exception as e:
            self.logger.error(f"Error stopping monitoring for {self.name}: {str(e)}")
    
    async def _event_loop(self) -> None:
        """
        Internal event loop that runs in the background
        """
        try:
            async for event in self.detect_events():
                if not self._is_active:
                    break
                await self.emit_event(event)
        except asyncio.CancelledError:
            self.logger.info(f"Event loop cancelled for notifier: {self.name}")
        except Exception as e:
            self.logger.error(f"Error in event loop for {self.name}: {str(e)}")
            self._is_active = False
    
    @property
    def is_active(self) -> bool:
        """Check if the notifier is currently active"""
        return self._is_active
    
    def create_standard_event(self, category: BaseEventType, action: str, data: Dict[str, Any] = None) -> StandardEvent:
        """
        Helper method to create a standard categorized event
        
        Args:
            category: Standard event category (BaseEventType)
            action: Specific action (e.g., "added", "deleted", "modified")
            data: Event-specific data
            
        Returns:
            StandardEvent with standard categorization
        """
        return StandardEvent(
            event_type=category,
            action=action,
            data=data or {},
            source=self.name,
            session_id=self.session_id
        )
    
    def create_custom_event(self, event_type: str, data: Dict[str, Any] = None) -> StandardEvent:
        """
        Helper method to create a tool-specific custom event
        
        Args:
            event_type: Full custom event type (e.g., "rhino.nurbs_surface_created")
            data: Event-specific data
            
        Returns:
            StandardEvent with custom event type
        """
        return StandardEvent(
            event_type=event_type,
            action="",  # Action is embedded in the event_type for custom events
            data=data or {},
            source=self.name,
            session_id=self.session_id
        ) 