"""
SPaT and MAP Broadcaster for V2X Roadside Units.
Encodes intersection geometric topology (MAP) and phase timings (SPaT)
for broadcasting to in-vehicle OBUs.
"""

from typing import Dict, Any
from backend.models import SPaTMessage


class SPaTBroadcaster:
    def __init__(self, intersection_id: str = "INT_01"):
        self.intersection_id = intersection_id

    def get_map_message(self) -> Dict[str, Any]:
        """SAE J2735 MAP intersection geometry descriptor."""
        return {
            "intersection_id": self.intersection_id,
            "ref_point": {"lat": 20.2961, "lon": 85.8245, "elevation": 45.0},  # Bhubaneswar Odisha reference point from problem statement!
            "lane_width": 3.5,
            "approaches": [
                {"id": 1, "name": "North Ave", "direction": "NORTH", "lanes": [1, 2], "signal_group": 1},
                {"id": 2, "name": "South Ave", "direction": "SOUTH", "lanes": [3, 4], "signal_group": 2},
                {"id": 3, "name": "East Blvd", "direction": "EAST", "lanes": [5, 6], "signal_group": 3},
                {"id": 4, "name": "West Blvd", "direction": "WEST", "lanes": [7, 8], "signal_group": 4},
            ],
            "crosswalks": [
                {"id": "CW_NORTH", "linked_phase": 3},
                {"id": "CW_SOUTH", "linked_phase": 3},
                {"id": "CW_EAST", "linked_phase": 1},
                {"id": "CW_WEST", "linked_phase": 1},
            ]
        }

    def format_spat_broadcast(self, spat: SPaTMessage) -> Dict[str, Any]:
        """Encodes SPaT for transmission to connected vehicles."""
        return {
            "msg_type": "SPaT",
            "intersection_id": spat.intersection_id,
            "timestamp": spat.timestamp,
            "preemption_active": spat.preemption_active,
            "emergency_vehicle": spat.emergency_vehicle_id,
            "phases": {
                pid: {
                    "direction": p.approach_direction,
                    "state": p.current_state.value,
                    "time_remaining_sec": p.time_remaining_seconds,
                    "is_preempted": p.is_preempted
                }
                for pid, p in spat.phases.items()
            }
        }
