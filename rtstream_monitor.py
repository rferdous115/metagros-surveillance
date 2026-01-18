"""
Real-Time Stream Monitor using VideoDB RTStream

Provides AI-powered monitoring of RTSP streams with customizable
detection scenarios and webhook alerts.
"""

import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable
import videodb
from videodb import SceneExtractionType


# ==================== DETECTION SCENARIOS ====================
class DetectionScenario(Enum):
    """Preset detection scenarios with example prompts."""
    FLASH_FLOOD = "Flash Flood"
    BURGLARY = "Burglary / Break-in"
    FIRE_SMOKE = "Fire / Smoke"
    LOITERING = "Person Loitering"
    VEHICLE_LOITERING = "Vehicle Loitering"
    CROWD_GATHERING = "Crowd Gathering"
    VIOLENCE = "Violence / Assault"
    VEHICLE_THEFT = "Vehicle Theft"
    CUSTOM = "Custom"


SCENARIO_PROMPTS = {
    DetectionScenario.FLASH_FLOOD: 
        "Monitor the area carefully. If moving water is detected across dry land or roads, "
        "identify it as a flash flood and describe the scene. Note water level and flow direction.",
    
    DetectionScenario.BURGLARY:
        "Monitor for suspicious activity. Detect breaking glass, forced entry attempts, "
        "masked individuals, or people trying to access locked doors/windows after hours.",
    
    DetectionScenario.FIRE_SMOKE:
        "Watch for smoke plumes, visible flames, or rapid haze buildup indicating a fire. "
        "Describe the location and intensity of any fire or smoke detected.",
    
    DetectionScenario.LOITERING:
        "Detect individuals remaining in the same area for an extended period without clear purpose. "
        "Note the number of people and duration of loitering behavior.",
    
    DetectionScenario.VEHICLE_LOITERING:
        "Detect parked vehicles remaining stationary in the same location for an extended period. "
        "Note suspicious vehicles that appear to be loitering or surveilling the area.",
    
    DetectionScenario.CROWD_GATHERING:
        "Detect crowd gathering or large groups of people forming. "
        "Alert when multiple people congregate in an area.",
    
    DetectionScenario.VIOLENCE:
        "Monitor for physical altercations, fights, or aggressive behavior between individuals. "
        "Describe the nature of the violence and number of people involved.",
    
    DetectionScenario.VEHICLE_THEFT:
        "Watch for suspicious activity around parked vehicles. Detect break-ins, hotwiring attempts, "
        "or individuals checking multiple car doors.",
    
    DetectionScenario.CUSTOM:
        "Describe what is happening in this scene in detail."
}

SCENARIO_EVENTS = {
    DetectionScenario.FLASH_FLOOD: ("Detect sudden flash floods or water surges.", "flash_flood"),
    DetectionScenario.BURGLARY: ("Detect breaking and entering or forced entry.", "burglary_detected"),
    DetectionScenario.FIRE_SMOKE: ("Detect fire or heavy smoke.", "fire_detected"),
    DetectionScenario.LOITERING: ("Detect prolonged person loitering behavior.", "loitering_detected"),
    DetectionScenario.VEHICLE_LOITERING: ("Detect parked vehicle loitering.", "vehicle_loitering"),
    DetectionScenario.CROWD_GATHERING: ("Detect crowd gathering or large groups.", "crowd_detected"),
    DetectionScenario.VIOLENCE: ("Detect physical violence or fighting.", "violence_detected"),
    DetectionScenario.VEHICLE_THEFT: ("Detect vehicle break-in or theft attempt.", "vehicle_theft"),
    DetectionScenario.CUSTOM: ("Detect notable events.", "custom_event"),
}


# ==================== DATA CLASSES ====================
@dataclass
class StreamConfig:
    """Configuration for a monitored stream."""
    name: str
    rtsp_url: str
    scenario: DetectionScenario
    custom_prompt: Optional[str] = None
    webhook_url: Optional[str] = None
    sample_interval: int = 10  # seconds
    frame_count: int = 6


@dataclass
class DetectedEvent:
    """Represents a detected event from the stream."""
    label: str
    confidence: float
    explanation: str
    start_time: str
    end_time: str
    stream_url: Optional[str] = None


# ==================== RTSTREAM MONITOR ====================
class RTStreamMonitor:
    """Wrapper for VideoDB RTStream real-time monitoring."""
    
    SAMPLE_STREAM = "rtsp://samples.rts.videodb.io:8554/floods"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the monitor with VideoDB credentials."""
        self.api_key = api_key or os.environ.get("VIDEO_DB_API_KEY")
        if not self.api_key:
            raise ValueError("VideoDB API key required")
        
        os.environ["VIDEO_DB_API_KEY"] = self.api_key
        self.conn = videodb.connect()
        self.coll = self.conn.get_collection()
        
        self.active_streams = {}  # stream_id -> rtstream object
        self.active_indexes = {}  # index_id -> scene_index object
        self.event_ids = {}       # label -> event_id
    
    def connect_stream(self, config: StreamConfig) -> str:
        """Connect to an RTSP stream and return stream ID."""
        rtstream = self.coll.connect_rtstream(
            name=config.name,
            url=config.rtsp_url
        )
        stream_id = rtstream.id
        self.active_streams[stream_id] = rtstream
        return stream_id
    
    def get_stream(self, stream_id: str):
        """Get an existing stream by ID."""
        if stream_id in self.active_streams:
            return self.active_streams[stream_id]
        rtstream = self.coll.get_rtstream(stream_id)
        self.active_streams[stream_id] = rtstream
        return rtstream
    
    def start_monitoring(self, stream_id: str, config: StreamConfig, 
                         on_status: Optional[Callable] = None) -> str:
        """Start AI monitoring on a stream. Returns index ID."""
        rtstream = self.get_stream(stream_id)
        
        # Get prompt
        if config.custom_prompt:
            prompt = config.custom_prompt
        else:
            prompt = SCENARIO_PROMPTS.get(config.scenario, SCENARIO_PROMPTS[DetectionScenario.CUSTOM])
        
        if on_status:
            on_status(f"Creating scene index for {config.scenario.value}...")
        
        # Create scene index
        scene_index = rtstream.index_scenes(
            extraction_type=SceneExtractionType.time_based,
            extraction_config={
                "time": config.sample_interval,
                "frame_count": config.frame_count,
            },
            prompt=prompt,
            name=f"{config.scenario.value}_Index",
            model_name="twelvelabs-pegasus-1.2"
        )
        
        index_id = scene_index.rtstream_index_id
        self.active_indexes[index_id] = scene_index
        
        if on_status:
            on_status(f"Monitoring started. Index ID: {index_id}")
        
        return index_id
    
    def create_event(self, scenario: DetectionScenario, custom_prompt: Optional[str] = None) -> str:
        """Create an event for detection. Returns event ID."""
        if scenario in self.event_ids:
            return self.event_ids[scenario]
        
        event_prompt, label = SCENARIO_EVENTS.get(
            scenario, 
            (custom_prompt or "Detect notable events.", "custom_event")
        )
        
        event_id = self.conn.create_event(
            event_prompt=event_prompt,
            label=label
        )
        self.event_ids[scenario] = event_id
        return event_id
    
    def create_alert(self, index_id: str, event_id: str, webhook_url: str) -> str:
        """Create an alert to send to webhook when event is detected."""
        scene_index = self.active_indexes.get(index_id)
        if not scene_index:
            raise ValueError(f"Index {index_id} not found")
        
        alert_id = scene_index.create_alert(
            event_id,
            callback_url=webhook_url
        )
        return alert_id
    
    def get_recent_scenes(self, index_id: str, page_size: int = 5) -> list:
        """Get recently indexed scenes."""
        scene_index = self.active_indexes.get(index_id)
        if not scene_index:
            return []
        
        scenes = scene_index.get_scenes(page_size=page_size)
        return scenes.get("scenes", []) if scenes else []
    
    def stop_monitoring(self, index_id: str):
        """Stop monitoring (pause scene indexing)."""
        if index_id in self.active_indexes:
            self.active_indexes[index_id].stop()
    
    def stop_stream(self, stream_id: str):
        """Stop a stream entirely."""
        if stream_id in self.active_streams:
            self.active_streams[stream_id].stop()
    
    def list_streams(self) -> list:
        """List all connected streams."""
        streams = []
        for rtstream in self.coll.list_rtstreams():
            streams.append({
                "id": rtstream.id,
                "name": rtstream.name,
                "status": rtstream.status,
                "created_at": rtstream.created_at
            })
        return streams


def get_scenario_prompt(scenario: DetectionScenario) -> str:
    """Get the default prompt for a scenario."""
    return SCENARIO_PROMPTS.get(scenario, SCENARIO_PROMPTS[DetectionScenario.CUSTOM])
