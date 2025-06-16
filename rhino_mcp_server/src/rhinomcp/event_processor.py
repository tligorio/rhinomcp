from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from enum import Enum, auto
import uuid

logger = logging.getLogger("RhinoMCPServer")

class EventType(Enum):
    """Types of events that can be processed."""
    GEOMETRY_ADDED = auto()
    GEOMETRY_MODIFIED = auto()
    GEOMETRY_DELETED = auto()
    LAYER_ADDED = auto()
    LAYER_MODIFIED = auto()
    LAYER_DELETED = auto()
    DOCUMENT_MODIFIED = auto()
    SELECTION_CHANGED = auto()

@dataclass
class EventValidationResult:
    """Result of event validation."""
    is_valid: bool
    error_message: Optional[str] = None

class ToolEventProcessor:
    """Processes and validates tool events from Rhino."""
    
    def __init__(self):
        self._event_handlers = {
            EventType.GEOMETRY_ADDED: self._handle_geometry_added,
            EventType.GEOMETRY_MODIFIED: self._handle_geometry_modified,
            EventType.GEOMETRY_DELETED: self._handle_geometry_deleted,
            EventType.LAYER_ADDED: self._handle_layer_added,
            EventType.LAYER_MODIFIED: self._handle_layer_modified,
            EventType.LAYER_DELETED: self._handle_layer_deleted,
            EventType.DOCUMENT_MODIFIED: self._handle_document_modified,
            EventType.SELECTION_CHANGED: self._handle_selection_changed
        }
    
    def process_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a tool event.
        
        Args:
            event_type: Type of the event
            event_data: Event data
            
        Returns:
            Dict containing the processing result
        """
        try:
            # Convert string event type to enum
            event_enum = self._get_event_type(event_type)
            
            # Validate the event
            validation = self._validate_event(event_enum, event_data)
            if not validation.is_valid:
                return {
                    "status": "error",
                    "message": validation.error_message
                }
            
            # Process the event
            handler = self._event_handlers.get(event_enum)
            if handler:
                return handler(event_data)
            else:
                return {
                    "status": "error",
                    "message": f"No handler found for event type: {event_type}"
                }
                
        except Exception as e:
            error_msg = f"Error processing event: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "message": error_msg
            }
    
    def _get_event_type(self, event_type: str) -> EventType:
        """Convert string event type to enum."""
        try:
            return EventType[event_type.upper()]
        except KeyError:
            raise ValueError(f"Unknown event type: {event_type}")
    
    def _validate_event(self, event_type: EventType, event_data: Dict[str, Any]) -> EventValidationResult:
        """Validate event data based on event type."""
        required_fields = self._get_required_fields(event_type)
        
        for field in required_fields:
            if field not in event_data:
                return EventValidationResult(
                    is_valid=False,
                    error_message=f"Missing required field: {field}"
                )
        
        return EventValidationResult(is_valid=True)
    
    def _get_required_fields(self, event_type: EventType) -> list[str]:
        """Get required fields for each event type."""
        field_map = {
            EventType.GEOMETRY_ADDED: ["object_id", "geometry_type"],
            EventType.GEOMETRY_MODIFIED: ["object_id", "geometry_type"],
            EventType.GEOMETRY_DELETED: ["object_id"],
            EventType.LAYER_ADDED: ["layer_name"],
            EventType.LAYER_MODIFIED: ["layer_name", "property_name"],
            EventType.LAYER_DELETED: ["layer_name"],
            EventType.DOCUMENT_MODIFIED: ["modification_type"],
            EventType.SELECTION_CHANGED: ["selected_objects"]
        }
        return field_map.get(event_type, [])
    
    # Event handlers
    def _handle_geometry_added(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle geometry added event."""
        logger.info(f"Geometry added: {event_data['object_id']}")
        return {
            "status": "success",
            "message": "Geometry added event processed"
        }
    
    def _handle_geometry_modified(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle geometry modified event."""
        logger.info(f"Geometry modified: {event_data['object_id']}")
        return {
            "status": "success",
            "message": "Geometry modified event processed"
        }
    
    def _handle_geometry_deleted(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle geometry deleted event."""
        logger.info(f"Geometry deleted: {event_data['object_id']}")
        return {
            "status": "success",
            "message": "Geometry deleted event processed"
        }
    
    def _handle_layer_added(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle layer added event."""
        logger.info(f"Layer added: {event_data['layer_name']}")
        return {
            "status": "success",
            "message": "Layer added event processed"
        }
    
    def _handle_layer_modified(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle layer modified event."""
        logger.info(f"Layer modified: {event_data['layer_name']}")
        return {
            "status": "success",
            "message": "Layer modified event processed"
        }
    
    def _handle_layer_deleted(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle layer deleted event."""
        logger.info(f"Layer deleted: {event_data['layer_name']}")
        return {
            "status": "success",
            "message": "Layer deleted event processed"
        }
    
    def _handle_document_modified(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle document modified event."""
        logger.info(f"Document modified: {event_data['modification_type']}")
        return {
            "status": "success",
            "message": "Document modified event processed"
        }
    
    def _handle_selection_changed(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle selection changed event."""
        logger.info(f"Selection changed: {len(event_data['selected_objects'])} objects selected")
        return {
            "status": "success",
            "message": "Selection changed event processed"
        } 