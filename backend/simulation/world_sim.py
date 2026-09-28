"""
High-Fidelity Multi-Intersection Digital Twin & Traffic Simulator.
Generates realistic connected vehicles (BSM/CAM), VRUs (pedestrians/cyclists),
RSU radar sensors, and emergency vehicle preemption scenarios.
"""

import time
import random
import math
from typing import Dict, List, Any, Optional
from backend.models import VehicleType, VRUType, SignalPhase
from backend.gateway.pki import PKISecurityEngine


class SimulatedVehicle:
    def __init__(
        self,
        vehicle_id: str,
        vehicle_type: VehicleType,
        approach: str,
        x: float,
        y: float,
        speed: float,
        target_speed: float,
        is_emergency: bool = False
    ):
        self.vehicle_id = vehicle_id
        self.vehicle_type = vehicle_type
        self.approach = approach  # "NORTH", "SOUTH", "EAST", "WEST"
        self.x = x
        self.y = y
        self.speed = speed
        self.target_speed = target_speed
        self.is_emergency = is_emergency
        self.cert_id = f"CERT_{vehicle_id}"
        self.stopped_waiting_time = 0.0
        self.emergency_cleared = False
        
        # Directions:
        # NORTH: moving -y (towards y=0), heading 180
        # SOUTH: moving +y (towards y=0), heading 0
        # EAST: moving -x (towards x=0), heading 270
        # WEST: moving +x (towards x=0), heading 90
        if approach == "NORTH":
            self.heading = 180.0
            self.vx = 0.0
            self.vy = -speed
        elif approach == "SOUTH":
            self.heading = 0.0
            self.vx = 0.0
            self.vy = speed
        elif approach == "EAST":
            self.heading = 270.0
            self.vx = -speed
            self.vy = 0.0
        else:  # WEST
            self.heading = 90.0
            self.vx = speed
            self.vy = 0.0

    def update_motion(self, dt: float, distance_to_lead: float, signal_state: SignalPhase):
        """Simulates car-following behavior and signal observance."""
        stop_line_dist = 999.0
        
        # Compute distance to stop line (at +/- 25m from center)
        if self.approach == "NORTH":
            stop_line_dist = self.y - 25.0 if self.y > 25.0 else 999.0
        elif self.approach == "SOUTH":
            stop_line_dist = -25.0 - self.y if self.y < -25.0 else 999.0
        elif self.approach == "EAST":
            stop_line_dist = self.x - 25.0 if self.x > 25.0 else 999.0
        elif self.approach == "WEST":
            stop_line_dist = -25.0 - self.x if self.x < -25.0 else 999.0

        # Emergency vehicle with active green or preemption doesn't stop unless blocked
        must_stop_for_signal = False
        if not self.is_emergency:
            if signal_state in [SignalPhase.RED, SignalPhase.YELLOW] and 0.0 < stop_line_dist < 40.0:
                must_stop_for_signal = True

        effective_gap = min(distance_to_lead, stop_line_dist if must_stop_for_signal else 999.0)

        # Acceleration / Deceleration logic (IDM-like)
        if effective_gap < 12.0:
            # Urgent braking
            self.speed = max(0.0, self.speed - 6.0 * dt)
        elif effective_gap < 25.0:
            # Gentle deceleration
            self.speed = max(0.0, self.speed - 2.5 * dt)
        elif self.speed < self.target_speed:
            # Acceleration
            accel = 3.5 if self.is_emergency else 2.0
            self.speed = min(self.target_speed, self.speed + accel * dt)

        if self.speed < 0.2:
            self.speed = 0.0
            self.stopped_waiting_time += dt

        # Update position
        if self.approach == "NORTH":
            self.y -= self.speed * dt
            self.vy = -self.speed
        elif self.approach == "SOUTH":
            self.y += self.speed * dt
            self.vy = self.speed
        elif self.approach == "EAST":
            self.x -= self.speed * dt
            self.vx = -self.speed
        elif self.approach == "WEST":
            self.x += self.speed * dt
            self.vx = self.speed


class SimulatedVRU:
    def __init__(self, vru_id: str, vru_type: VRUType, start_pos: tuple, end_pos: tuple, speed: float = 1.3):
        self.vru_id = vru_id
        self.vru_type = vru_type
        self.x, self.y = start_pos
        self.end_x, self.end_y = end_pos
        self.speed = speed
        self.cert_id = f"CERT_{vru_id}"
        
        dx = self.end_x - self.x
        dy = self.end_y - self.y
        dist = math.sqrt(dx*dx + dy*dy)
        self.vx = (dx / dist) * speed if dist > 0 else 0.0
        self.vy = (dy / dist) * speed if dist > 0 else 0.0
        self.heading = (math.degrees(math.atan2(self.vx, self.vy)) + 360.0) % 360.0

    def update_motion(self, dt: float):
        self.x += self.vx * dt
        self.y += self.vy * dt


class WorldSimulator:
    def __init__(self, pki: PKISecurityEngine):
        self.pki = pki
        self.vehicles: Dict[str, SimulatedVehicle] = {}
        self.vrus: Dict[str, SimulatedVRU] = {}
        self.vehicle_counter = 100
        self.vru_counter = 500
        self.active_scenario = "NORMAL_FLOW"
        self.spawn_timer = 0.0
        self.vru_spawn_timer = 0.0

        # Initial seed vehicles
        self._seed_initial_traffic()

    def _seed_initial_traffic(self):
        approaches = ["NORTH", "SOUTH", "EAST", "WEST"]
        for app in approaches:
            self._spawn_vehicle(app, offset=40.0)
            self._spawn_vehicle(app, offset=80.0)

        # Seed initial pedestrians
        self._spawn_pedestrian()

    def _spawn_vehicle(self, approach: str, offset: float = 110.0, is_emergency: bool = False) -> SimulatedVehicle:
        self.vehicle_counter += 1
        vid = f"AMB_911" if is_emergency else f"VEH_{self.vehicle_counter}"
        vtype = VehicleType.EMERGENCY_AMBULANCE if is_emergency else (
            VehicleType.BUS if random.random() < 0.15 else VehicleType.PASSENGER_CAR
        )

        target_speed = 18.0 if is_emergency else random.uniform(9.0, 13.5)  # 35-50 km/h
        init_speed = target_speed

        # Lateral lane offset to allow two lanes
        lane_offset = random.choice([-2.5, 2.5])

        if approach == "NORTH":
            x, y = lane_offset, offset
        elif approach == "SOUTH":
            x, y = lane_offset, -offset
        elif approach == "EAST":
            x, y = offset, lane_offset
        else:  # WEST
            x, y = -offset, lane_offset

        veh = SimulatedVehicle(
            vehicle_id=vid,
            vehicle_type=vtype,
            approach=approach,
            x=x,
            y=y,
            speed=init_speed,
            target_speed=target_speed,
            is_emergency=is_emergency
        )
        self.vehicles[vid] = veh
        self.pki.register_pseudonym(veh.cert_id)
        return veh

    def _spawn_pedestrian(self) -> SimulatedVRU:
        self.vru_counter += 1
        vid = f"VRU_{self.vru_counter}"
        # Spawn near North or South crosswalk
        if random.random() < 0.5:
            # North crosswalk (-20, 26) -> (20, 26)
            start = (-18.0, 26.0) if random.random() < 0.5 else (18.0, 26.0)
            end = (18.0, 26.0) if start[0] < 0 else (-18.0, 26.0)
        else:
            # South crosswalk (-20, -26) -> (20, -26)
            start = (-18.0, -26.0) if random.random() < 0.5 else (18.0, -26.0)
            end = (18.0, -26.0) if start[0] < 0 else (-18.0, -26.0)

        vru = SimulatedVRU(vru_id=vid, vru_type=VRUType.PEDESTRIAN, start_pos=start, end_pos=end)
        self.vrus[vid] = vru
        self.pki.register_pseudonym(vru.cert_id)
        return vru

    def trigger_ambulance_scenario(self, approach: str = "SOUTH") -> SimulatedVehicle:
        """Injects emergency vehicle with high priority approaching intersection."""
        self.active_scenario = "EMERGENCY_AMBULANCE"
        # Clear existing ambulance if any
        if "AMB_911" in self.vehicles:
            del self.vehicles["AMB_911"]

        # Clear any traffic blocking the emergency approach corridor
        for vid, v in list(self.vehicles.items()):
            if v.approach == approach and abs(v.y if approach in ["NORTH", "SOUTH"] else v.x) < 55.0:
                v.speed = max(v.speed, 14.0)

        # Spawn right in visible view (offset 52m from center)
        amb = self._spawn_vehicle(approach=approach, offset=52.0, is_emergency=True)
        amb.speed = 13.0
        amb.target_speed = 17.5
        return amb

    def trigger_jaywalking_scenario(self) -> SimulatedVRU:
        """Injects a pedestrian crossing directly in front of approaching vehicle."""
        self.active_scenario = "VRU_HAZARD"
        vid = f"VRU_JAYWALK_{int(time.time())%1000}"
        # Start at curb and cross right in middle of Southbound lane
        start = (14.0, 15.0)
        end = (-14.0, 15.0)
        vru = SimulatedVRU(vru_id=vid, vru_type=VRUType.PEDESTRIAN, start_pos=start, end_pos=end, speed=1.5)
        self.vrus[vid] = vru
        self.pki.register_pseudonym(vru.cert_id)
        return vru

    def step(self, dt: float, signal_phases: Dict[int, Any]) -> Tuple_Sim_Outputs:
        """Updates physics and returns generated BSM and VRU telemetry packets."""
        self.spawn_timer += dt
        self.vru_spawn_timer += dt

        # Spawn rate depending on scenario
        spawn_interval = 1.8 if self.active_scenario == "PEAK_HOUR" else 3.2
        if self.spawn_timer >= spawn_interval:
            self.spawn_timer = 0.0
            if len(self.vehicles) < 24:
                approach = random.choice(["NORTH", "SOUTH", "EAST", "WEST"])
                self._spawn_vehicle(approach, offset=random.uniform(55.0, 75.0))

        if self.vru_spawn_timer >= 6.0:
            self.vru_spawn_timer = 0.0
            if len(self.vrus) < 6:
                self._spawn_pedestrian()

        # Phase lookup: NS is phase 1, EW is phase 3
        ns_phase = signal_phases[1].current_state if 1 in signal_phases else SignalPhase.GREEN
        ew_phase = signal_phases[3].current_state if 3 in signal_phases else SignalPhase.RED

        # Sort vehicles per approach to calculate car-following gap
        bsm_messages: List[Dict[str, Any]] = []
        vr_messages: List[Dict[str, Any]] = []
        vehicles_to_remove = []

        # Update Vehicles
        for vid, v in list(self.vehicles.items()):
            sig = ns_phase if v.approach in ["NORTH", "SOUTH"] else ew_phase

            # Find distance to leading vehicle on same approach
            dist_lead = 999.0
            for other_id, other in self.vehicles.items():
                if other_id == vid or other.approach != v.approach:
                    continue
                # Ahead condition
                if v.approach == "NORTH" and other.y < v.y:
                    dist_lead = min(dist_lead, v.y - other.y)
                elif v.approach == "SOUTH" and other.y > v.y:
                    dist_lead = min(dist_lead, other.y - v.y)
                elif v.approach == "EAST" and other.x < v.x:
                    dist_lead = min(dist_lead, v.x - other.x)
                elif v.approach == "WEST" and other.x > v.x:
                    dist_lead = min(dist_lead, other.x - v.x)

            v.update_motion(dt, dist_lead, sig)

            # Check if vehicle has cleared intersection and left bounds
            out_of_bounds = False
            if v.approach == "NORTH" and v.y < -120.0:
                out_of_bounds = True
            elif v.approach == "SOUTH" and v.y > 120.0:
                out_of_bounds = True
            elif v.approach == "EAST" and v.x < -120.0:
                out_of_bounds = True
            elif v.approach == "WEST" and v.x > 120.0:
                out_of_bounds = True

            if out_of_bounds:
                vehicles_to_remove.append(vid)
                continue

            # Generate BSM packet
            summary = f"{v.vehicle_id}:{v.x:.1f}:{v.y:.1f}:{v.speed:.1f}"
            sig_hash = self.pki.generate_signature(f"BSM_{vid}", summary, v.cert_id)
            
            bsm_messages.append({
                "msg_id": f"BSM_{vid}_{int(time.time()*10)%100000}",
                "vehicle_id": v.vehicle_id,
                "vehicle_type": v.vehicle_type.value,
                "timestamp": time.time(),
                "latitude": 20.2961 + (v.y / 111111.0),
                "longitude": 85.8245 + (v.x / (111111.0 * math.cos(math.radians(20.2961)))),
                "x": round(v.x, 2),
                "y": round(v.y, 2),
                "speed": round(v.speed, 2),
                "heading": v.heading,
                "priority_level": 1 if v.is_emergency else 0,
                "siren_active": v.is_emergency,
                "cert_id": v.cert_id,
                "signature": sig_hash
            })

        for vid in vehicles_to_remove:
            del self.vehicles[vid]

        # Update VRUs
        vrus_to_remove = []
        for vrid, vru in list(self.vrus.items()):
            vru.update_motion(dt)
            dist_left = math.sqrt((vru.end_x - vru.x)**2 + (vru.end_y - vru.y)**2)
            if dist_left < 1.0 or abs(vru.x) > 40.0 or abs(vru.y) > 40.0:
                vrus_to_remove.append(vrid)
                continue

            vr_messages.append({
                "msg_id": f"VRU_{vrid}_{int(time.time()*10)%100000}",
                "vru_id": vru.vru_id,
                "vru_type": vru.vru_type.value,
                "timestamp": time.time(),
                "latitude": 20.2961 + (vru.y / 111111.0),
                "longitude": 85.8245 + (vru.x / 111111.0),
                "x": round(vru.x, 2),
                "y": round(vru.y, 2),
                "speed": round(vru.speed, 2),
                "heading": round(vru.heading, 1),
                "crossing_crosswalk": True,
                "confidence_radius": 0.5,
                "cert_id": vru.cert_id,
                "signature": ""
            })

        for vrid in vrus_to_remove:
            del self.vrus[vrid]

        return bsm_messages, vr_messages


Tuple_Sim_Outputs = tuple[List[Dict[str, Any]], List[Dict[str, Any]]]
