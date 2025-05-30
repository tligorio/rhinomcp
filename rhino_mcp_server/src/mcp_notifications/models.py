"""
Core data structures for MCP notifications
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, Union
import json


class BaseEventType(Enum):
    """
    Base event categories that most CAD/3D tools share
    
    These provide a standardized way to categorize events across different tools,
    while still allowing tool-specific event types.
    """
    
    # Geometry operations
    GEOMETRY = "geometry"
    SELECTION = "selection"
    
    # Organization
    LAYER = "layer"
    GROUP = "group"
    BLOCK = "block"  # Rhino blocks, Blender collections, etc.
    
    # Materials and appearance
    MATERIAL = "material"
    TEXTURE = "texture"
    
    # Views and display
    VIEW = "view"
    DISPLAY = "display"
    
    # Document lifecycle
    DOCUMENT = "document"
    
    # Tool-specific
    CUSTOM = "custom"
    ERROR = "error"


@dataclass
class EventData:
    """Base class for event-specific data"""
    pass


@dataclass
class StandardEvent:
    """
    Standard event structure for MCP notifications
    
    Uses a flexible event_type system that supports both:
    - Standard categories (BaseEventType) 
    - Tool-specific event strings (e.g., "rhino.nurbs_surface_created")
    """
    event_type: Union[BaseEventType, str]  # Flexible: enum or custom string
    action: str  # The specific action: "added", "deleted", "modified", etc.
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None  # Which notifier generated this event
    session_id: Optional[str] = None  # For tracking across sessions
    
    def get_event_category(self) -> str:
        """Get the event category (standardized or custom)"""
        if isinstance(self.event_type, BaseEventType):
            return self.event_type.value
        else:
            # For custom strings like "rhino.nurbs_surface_created", 
            # try to extract the category part
            if "." in self.event_type:
                return self.event_type.split(".")[0]
            return "custom"
    
    def get_full_event_type(self) -> str:
        """Get the full event type as a string"""
        if isinstance(self.event_type, BaseEventType):
            return f"{self.event_type.value}.{self.action}"
        else:
            return self.event_type
    
    def to_log_dict(self) -> Dict[str, Any]:
        """
        Format event for wire logging
        
        Returns a dictionary suitable for JSON serialization in wire logs
        """
        return {
            "event_type": self.get_full_event_type(),
            "category": self.get_event_category(),
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "session_id": self.session_id,
            **self.data
        }
    
    def to_json(self) -> str:
        """Convert event to JSON string for transmission"""
        return json.dumps(self.to_log_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandardEvent":
        """Create StandardEvent from dictionary"""
        event_type_str = data.pop("event_type")
        action = data.pop("action", "")
        
        # Try to match to BaseEventType, otherwise use as custom string
        try:
            category = data.pop("category", "")
            if category:
                event_type = BaseEventType(category)
            else:
                event_type = event_type_str
        except ValueError:
            event_type = event_type_str
        
        timestamp_str = data.pop("timestamp", None)
        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()
        source = data.pop("source", None)
        session_id = data.pop("session_id", None)
        
        return cls(
            event_type=event_type,
            action=action,
            timestamp=timestamp,
            data=data,
            source=source,
            session_id=session_id
        )


# Tool-specific event type collections that can be imported separately
class RhinoEventTypes:
    """Rhino-specific event types"""
    
    # Geometry events
    NURBS_SURFACE_CREATED = "rhino.nurbs_surface_created"
    NURBS_CURVE_CREATED = "rhino.nurbs_curve_created"
    MESH_CREATED = "rhino.mesh_created"
    POLYSURFACE_CREATED = "rhino.polysurface_created"
    
    # Rhino-specific operations
    BOOLEAN_OPERATION = "rhino.boolean_operation"
    FILLET_CREATED = "rhino.fillet_created"
    EXTRUDE_OPERATION = "rhino.extrude_operation"
    LOFT_OPERATION = "rhino.loft_operation"
    
    # Grasshopper events
    GRASSHOPPER_DEFINITION_LOADED = "rhino.grasshopper_definition_loaded"
    GRASSHOPPER_BAKED = "rhino.grasshopper_baked"
    
    # Rhino layers (more specific than generic)
    LAYER_LOCKED = "rhino.layer_locked"
    LAYER_UNLOCKED = "rhino.layer_unlocked"
    
    # Rhino blocks
    BLOCK_DEFINITION_CREATED = "rhino.block_definition_created"
    BLOCK_INSTANCE_INSERTED = "rhino.block_instance_inserted"


class BlenderEventTypes:
    """Blender-specific event types (for future expansion)"""
    
    MODIFIER_ADDED = "blender.modifier_added"
    MODIFIER_APPLIED = "blender.modifier_applied"
    ANIMATION_KEYFRAME_SET = "blender.animation_keyframe_set"
    SHADER_NODE_CREATED = "blender.shader_node_created" 