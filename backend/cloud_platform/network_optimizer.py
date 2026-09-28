"""
Network-Wide Corridor Optimizer.
Calculates progression offsets and green-wave coordination across multi-intersection corridors.
"""

from typing import List, Dict, Any


class NetworkOptimizer:
    def __init__(self, target_corridor_speed_mps: float = 13.88):  # 50 km/h
        self.target_speed = target_corridor_speed_mps
        # Corridor: Intersection 1 (0m) -> Intersection 2 (300m) -> Intersection 3 (600m)
        self.corridor_intersections = [
            {"id": "INT_01", "name": "Janpath & Master Canteen", "offset_meters": 0.0},
            {"id": "INT_02", "name": "Janpath & Ram Mandir", "offset_meters": 300.0},
            {"id": "INT_03", "name": "Janpath & Vani Vihar", "offset_meters": 600.0},
        ]

    def calculate_green_wave_offsets(self, cycle_time_sec: float = 60.0) -> List[Dict[str, Any]]:
        """
        Calculates time offsets for downstream intersections to maintain
        a continuous green wave at target speed (50 km/h).
        """
        plan = []
        for int_data in self.corridor_intersections:
            dist = int_data["offset_meters"]
            # Time taken to travel from origin intersection
            travel_time = dist / self.target_speed
            offset_in_cycle = travel_time % cycle_time_sec
            plan.append({
                "intersection_id": int_data["id"],
                "name": int_data["name"],
                "distance_meters": dist,
                "ideal_offset_seconds": round(offset_in_cycle, 1),
                "advisory_speed_kmh": round(self.target_speed * 3.6, 1)
            })
        return plan
