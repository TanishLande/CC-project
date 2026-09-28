"""
Local Dynamic Map (LDM) Engine based on ETSI EN 302 895 standard.
Maintains 4 layers:
  Layer 1: Static road geometry & lane topology
  Layer 2: Static infrastructure (Signal heads, crosswalks)
  Layer 3: Transient state (Signal phases, weather)
  Layer 4: Highly dynamic objects (Vehicles, VRUs, sensor fused tracks)
"""

import time
import math
from typing import Dict, List, Optional, Tuple, Any
from backend.models import (
    BSMMessage, VRUMessage, RSUDetection, FusedTrack,
    LocalDynamicMap, SPaTMessage
)
from backend.fusion.kalman import KalmanTrack


class LocalDynamicMapEngine:
    def __init__(self, intersection_id: str = "INT_01", intersection_center: Tuple[float, float] = (0.0, 0.0)):
        self.intersection_id = intersection_id
        self.center_x, self.center_y = intersection_center
        
        # Kalman filter trackers: track_id -> KalmanTrack
        self.trackers: Dict[str, KalmanTrack] = {}
        # Fused tracks dictionary: track_id -> FusedTrack
        self.fused_tracks: Dict[str, FusedTrack] = {}
        
        # SPaT state
        self.current_spat: Optional[SPaTMessage] = None
        
        # Static Layer 1 & 2 definitions (Intersection geometry)
        # Approaches: NORTH, SOUTH, EAST, WEST
        self.approach_lanes = {
            "NORTH": {"entry_x": 0.0, "entry_y": 100.0, "dir_x": 0.0, "dir_y": -1.0},
            "SOUTH": {"entry_x": 0.0, "entry_y": -100.0, "dir_x": 0.0, "dir_y": 1.0},
            "EAST": {"entry_x": 100.0, "entry_y": 0.0, "dir_x": -1.0, "dir_y": 0.0},
            "WEST": {"entry_x": -100.0, "entry_y": 0.0, "dir_x": 1.0, "dir_y": 0.0},
        }
        
        # Crosswalk definitions
        self.crosswalks = {
            "CW_NORTH": {"x1": -20.0, "y1": 25.0, "x2": 20.0, "y2": 25.0, "active": False},
            "CW_SOUTH": {"x1": -20.0, "y1": -25.0, "x2": 20.0, "y2": -25.0, "active": False},
            "CW_EAST": {"x1": 25.0, "y1": -20.0, "x2": 25.0, "y2": 20.0, "active": False},
            "CW_WEST": {"x1": -25.0, "y1": -20.0, "x2": -25.0, "y2": 20.0, "active": False},
        }

        self.last_cleanup_time = time.time()

    def update_vehicle(self, bsm: BSMMessage) -> FusedTrack:
        now = time.time()
        track_id = bsm.vehicle_id

        if track_id not in self.trackers:
            vx = bsm.speed * math.sin(math.radians(bsm.heading))
            vy = bsm.speed * math.cos(math.radians(bsm.heading))
            self.trackers[track_id] = KalmanTrack(track_id, bsm.x, bsm.y, vx, vy)
        else:
            dt = now - self.trackers[track_id].last_timestamp
            self.trackers[track_id].predict(dt)
            self.trackers[track_id].update(bsm.x, bsm.y)

        x, y, vx, vy, speed, heading = self.trackers[track_id].get_state()
        
        history = self.fused_tracks[track_id].history if track_id in self.fused_tracks else []
        history.append((round(x, 2), round(y, 2)))
        if len(history) > 20:
            history.pop(0)

        is_emergency = "emergency" in bsm.vehicle_type.value.lower()
        fused = FusedTrack(
            track_id=track_id,
            entity_type="vehicle",
            sub_type=bsm.vehicle_type.value,
            x=round(x, 2),
            y=round(y, 2),
            vx=round(vx, 2),
            vy=round(vy, 2),
            speed=round(speed, 2),
            heading=round(heading, 1),
            confidence=0.98,
            last_update=now,
            history=history,
            length=bsm.length,
            width=bsm.width,
            is_emergency=is_emergency,
            priority_level=bsm.priority_level if is_emergency else 0,
            route=bsm.target_route
        )
        self.fused_tracks[track_id] = fused
        return fused

    def update_vru(self, vru: VRUMessage) -> FusedTrack:
        now = time.time()
        track_id = vru.vru_id

        if track_id not in self.trackers:
            vx = vru.speed * math.sin(math.radians(vru.heading))
            vy = vru.speed * math.cos(math.radians(vru.heading))
            self.trackers[track_id] = KalmanTrack(track_id, vru.x, vru.y, vx, vy)
        else:
            dt = now - self.trackers[track_id].last_timestamp
            self.trackers[track_id].predict(dt)
            self.trackers[track_id].update(vru.x, vru.y)

        x, y, vx, vy, speed, heading = self.trackers[track_id].get_state()

        history = self.fused_tracks[track_id].history if track_id in self.fused_tracks else []
        history.append((round(x, 2), round(y, 2)))
        if len(history) > 20:
            history.pop(0)

        fused = FusedTrack(
            track_id=track_id,
            entity_type="vru",
            sub_type=vru.vru_type.value,
            x=round(x, 2),
            y=round(y, 2),
            vx=round(vx, 2),
            vy=round(vy, 2),
            speed=round(speed, 2),
            heading=round(heading, 1),
            confidence=0.92,
            last_update=now,
            history=history,
            length=0.8,
            width=0.8,
            is_emergency=False,
            priority_level=0,
            route=None
        )
        self.fused_tracks[track_id] = fused
        return fused

    def update_spat(self, spat: SPaTMessage) -> None:
        self.current_spat = spat

    def purge_stale_tracks(self, max_age_seconds: float = 3.0) -> None:
        """Removes participants that have stopped reporting within max_age_seconds."""
        now = time.time()
        stale_ids = [
            tid for tid, track in self.fused_tracks.items()
            if now - track.last_update > max_age_seconds
        ]
        for tid in stale_ids:
            self.fused_tracks.pop(tid, None)
            self.trackers.pop(tid, None)

    def calculate_approach_queues(self) -> Dict[str, int]:
        """Calculates queue length per approach corridor for adaptive signal optimization."""
        queues = {"NORTH": 0, "SOUTH": 0, "EAST": 0, "WEST": 0}
        stopline_distance = 30.0  # meters from center
        approach_extent = 120.0

        for track in self.fused_tracks.values():
            if track.entity_type != "vehicle":
                continue
            x, y, speed = track.x, track.y, track.speed
            # North approach: x in [-15, 15], y in [stopline, approach_extent]
            if abs(x) <= 15.0 and stopline_distance <= y <= approach_extent and speed < 4.0:
                queues["NORTH"] += 1
            # South approach: x in [-15, 15], y in [-approach_extent, -stopline]
            elif abs(x) <= 15.0 and -approach_extent <= y <= -stopline_distance and speed < 4.0:
                queues["SOUTH"] += 1
            # East approach: y in [-15, 15], x in [stopline, approach_extent]
            elif abs(y) <= 15.0 and stopline_distance <= x <= approach_extent and speed < 4.0:
                queues["EAST"] += 1
            # West approach: y in [-15, 15], x in [-approach_extent, -stopline]
            elif abs(y) <= 15.0 and -approach_extent <= x <= -stopline_distance and speed < 4.0:
                queues["WEST"] += 1

        return queues

    def get_snapshot(self) -> LocalDynamicMap:
        """Serializes current LDM state."""
        self.purge_stale_tracks()
        queues = self.calculate_approach_queues()
        veh_count = sum(1 for t in self.fused_tracks.values() if t.entity_type == "vehicle")
        vru_count = sum(1 for t in self.fused_tracks.values() if t.entity_type == "vru")

        return LocalDynamicMap(
            intersection_id=self.intersection_id,
            timestamp=time.time(),
            tracks=self.fused_tracks,
            active_alerts=[],
            spat=self.current_spat,
            queue_lengths=queues,
            total_vehicles=veh_count,
            total_vrus=vru_count
        )
