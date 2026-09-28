"""
Data models for V2X Network based on SAE J2735 and ETSI standards.
Includes BSM, CAM, VRU, RSU, SPaT, MAP, EVA, and LDM structures.
"""

from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field
import time


class VehicleType(str, Enum):
    PASSENGER_CAR = "passenger_car"
    TRUCK = "truck"
    BUS = "bus"
    MOTORCYCLE = "motorcycle"
    EMERGENCY_AMBULANCE = "emergency_ambulance"
    EMERGENCY_FIRE = "emergency_fire"
    EMERGENCY_POLICE = "emergency_police"


class VRUType(str, Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    SCOOTER = "scooter"
    WHEELCHAIR = "wheelchair"


class SignalPhase(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"
    PREEMPTION_GREEN = "PREEMPTION_GREEN"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# --- SAE J2735 BSM (Basic Safety Message) / ETSI CAM ---
class BSMMessage(BaseModel):
    msg_id: str
    vehicle_id: str
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR
    timestamp: float = Field(default_factory=time.time)
    latitude: float
    longitude: float
    x: float  # local coordinate (meters relative to intersection center)
    y: float
    speed: float  # m/s
    heading: float  # degrees (0 = North, 90 = East, 180 = South, 270 = West)
    acceleration: float = 0.0  # m/s^2
    yaw_rate: float = 0.0  # deg/s
    length: float = 4.5
    width: float = 2.0
    lane_id: int = 1
    target_route: Optional[List[str]] = None
    priority_level: int = 0  # 0: normal, 1-3: emergency
    siren_active: bool = False
    signature: str = ""  # PKI digital signature
    cert_id: str = ""  # Pseudonym cert ID


# --- VRU Telemetry (Vulnerable Road User) ---
class VRUMessage(BaseModel):
    msg_id: str
    vru_id: str
    vru_type: VRUType = VRUType.PEDESTRIAN
    timestamp: float = Field(default_factory=time.time)
    latitude: float
    longitude: float
    x: float
    y: float
    speed: float = 1.2  # m/s
    heading: float = 0.0
    crossing_crosswalk: bool = False
    crosswalk_id: Optional[str] = None
    confidence_radius: float = 0.5  # meters
    signature: str = ""
    cert_id: str = ""


# --- RSU Radar/LiDAR/Camera Detection ---
class RSUDetection(BaseModel):
    rsu_id: str
    timestamp: float = Field(default_factory=time.time)
    detected_objects: List[Dict[str, Any]] = Field(default_factory=list)
    radar_tracks_count: int = 0
    camera_detections_count: int = 0


# --- SAE J2735 SPaT (Signal Phase and Timing) ---
class PhaseState(BaseModel):
    phase_id: int
    approach_direction: str  # "NORTH", "SOUTH", "EAST", "WEST"
    current_state: SignalPhase
    time_remaining_seconds: float
    min_green: float = 10.0
    max_green: float = 45.0
    yellow_duration: float = 3.5
    is_preempted: bool = False


class SPaTMessage(BaseModel):
    intersection_id: str
    timestamp: float = Field(default_factory=time.time)
    phases: Dict[int, PhaseState]
    active_phase_ids: List[int]
    preemption_active: bool = False
    emergency_vehicle_id: Optional[str] = None


# --- SAE J2735 EVA (Emergency Vehicle Alert) ---
class EVAMessage(BaseModel):
    msg_id: str
    vehicle_id: str
    vehicle_type: VehicleType
    priority_level: int = 1  # 1: highest
    origin: str
    destination: str
    route_intersections: List[str]  # e.g., ["INT_01", "INT_02", "INT_03"]
    current_intersection: str
    eta_seconds: float
    speed_mps: float
    siren_active: bool = True
    corridor_cleared: bool = False
    signature: str = ""


# --- Safety Alert Broadcast ---
class SafetyAlert(BaseModel):
    alert_id: str
    timestamp: float = Field(default_factory=time.time)
    alert_type: str  # "FCW" (Forward Collision), "BSW" (Blind Spot), "VRU_ALERT", "RED_LIGHT_RUNNER", "EMERGENCY_CORRIDOR"
    severity: AlertSeverity
    primary_entity_id: str
    target_entity_id: str
    ttc_seconds: Optional[float] = None
    message: str
    recommended_action: str  # e.g., "HARD_BRAKE", "HOLD_CROSSING", "YIELD_TO_AMBULANCE"


# --- Fused Track & Local Dynamic Map (LDM) ---
class FusedTrack(BaseModel):
    track_id: str
    entity_type: str  # "vehicle", "vru", "rsu_unconnected"
    sub_type: str
    x: float
    y: float
    vx: float
    vy: float
    speed: float
    heading: float
    confidence: float
    last_update: float
    history: List[Tuple[float, float]] = Field(default_factory=list)
    length: float = 4.5
    width: float = 2.0
    is_emergency: bool = False
    priority_level: int = 0
    route: Optional[List[str]] = None


class LocalDynamicMap(BaseModel):
    intersection_id: str
    timestamp: float = Field(default_factory=time.time)
    tracks: Dict[str, FusedTrack] = Field(default_factory=dict)
    active_alerts: List[SafetyAlert] = Field(default_factory=list)
    spat: Optional[SPaTMessage] = None
    queue_lengths: Dict[str, int] = Field(default_factory=dict)  # direction -> count
    total_vehicles: int = 0
    total_vrus: int = 0
    edge_inference_latency_ms: float = 0.0
