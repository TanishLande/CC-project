"""
Sub-20ms Edge AI Collision Risk & TTC (Time-to-Collision) Vectorized Engine.
Calculates closest point of approach (CPA), TTC, PET (Post-Encroachment Time),
and generates safety warnings for vehicles and VRUs.
"""

import time
import math
import numpy as np
from typing import List, Dict, Tuple, Optional
from backend.models import FusedTrack, SafetyAlert, AlertSeverity, SignalPhase, SPaTMessage


class EdgeAIEngine:
    def __init__(
        self,
        critical_ttc_sec: float = 2.0,
        warning_ttc_sec: float = 3.5,
        caution_ttc_sec: float = 5.0,
        collision_radius_meters: float = 3.2
    ):
        self.critical_ttc = critical_ttc_sec
        self.warning_ttc = warning_ttc_sec
        self.caution_ttc = caution_ttc_sec
        self.collision_radius = collision_radius_meters
        self.last_inference_latency_ms = 0.0

    def compute_risk_and_alerts(
        self,
        tracks: Dict[str, FusedTrack],
        spat: Optional[SPaTMessage] = None
    ) -> Tuple[List[SafetyAlert], float]:
        """
        Executes collision risk evaluation under the 20ms edge latency budget.
        Returns (alerts_list, inference_latency_ms).
        """
        t_start = time.perf_counter()
        alerts: List[SafetyAlert] = []
        track_list = list(tracks.values())
        n = len(track_list)

        if n < 2:
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            self.last_inference_latency_ms = latency_ms
            return alerts, latency_ms

        # Extract numpy arrays for fast vectorized calculation
        # Positions: shape (N, 2)
        pos = np.array([[t.x, t.y] for t in track_list], dtype=np.float64)
        # Velocities: shape (N, 2)
        vel = np.array([[t.vx, t.vy] for t in track_list], dtype=np.float64)

        # Pairwise relative position and relative velocity tensors
        # pos_diff[i, j] = pos[j] - pos[i]
        pos_diff = pos[None, :, :] - pos[:, None, :]  # shape (N, N, 2)
        # vel_diff[i, j] = vel[j] - vel[i]
        vel_diff = vel[None, :, :] - vel[:, None, :]  # shape (N, N, 2)

        # Dot products: pos_diff . vel_diff
        # (N, N)
        r_dot_v = np.sum(pos_diff * vel_diff, axis=2)
        v_sq = np.sum(vel_diff ** 2, axis=2)
        v_sq = np.where(v_sq < 1e-4, 1e-4, v_sq)  # prevent division by zero

        # Time to Closest Point of Approach (t_cpa)
        t_cpa = -r_dot_v / v_sq

        # Position at CPA
        # pos_cpa[i, j] = pos_diff[i, j] + vel_diff[i, j] * t_cpa[i, j]
        pos_cpa = pos_diff + vel_diff * t_cpa[:, :, None]
        d_cpa = np.sqrt(np.sum(pos_cpa ** 2, axis=2))

        # Check upper triangular matrix (unique pairs i < j)
        for i in range(n):
            for j in range(i + 1, n):
                t_val = float(t_cpa[i, j])
                d_val = float(d_cpa[i, j])
                p1 = track_list[i]
                p2 = track_list[j]

                # Combined collision bounding radius
                eff_radius = (p1.length + p2.length) * 0.35 + (p1.width + p2.width) * 0.45

                # Collision condition: moving towards each other, t_cpa positive, distance within radius
                if 0.05 < t_val <= self.caution_ttc and d_val <= eff_radius:
                    # Determine severity
                    if t_val <= self.critical_ttc:
                        severity = AlertSeverity.CRITICAL
                    elif t_val <= self.warning_ttc:
                        severity = AlertSeverity.WARNING
                    else:
                        severity = AlertSeverity.INFO

                    # VRU specific collision
                    is_vru_involved = (p1.entity_type == "vru" or p2.entity_type == "vru")
                    
                    if is_vru_involved:
                        vru_entity = p1 if p1.entity_type == "vru" else p2
                        veh_entity = p2 if p1.entity_type == "vru" else p1
                        alert = SafetyAlert(
                            alert_id=f"ALT_VRU_{p1.track_id}_{p2.track_id}_{int(time.time()*10)}",
                            timestamp=time.time(),
                            alert_type="VRU_COLLISION_ALERT",
                            severity=severity,
                            primary_entity_id=veh_entity.track_id,
                            target_entity_id=vru_entity.track_id,
                            ttc_seconds=round(t_val, 2),
                            message=f"CRITICAL: Imminent collision with {vru_entity.sub_type} in {t_val:.1f}s at {d_val:.1f}m!",
                            recommended_action="EMERGENCY_AUTONOMOUS_BRAKE" if severity == AlertSeverity.CRITICAL else "YIELD_TO_PEDESTRIAN"
                        )
                    else:
                        # Vehicle to Vehicle
                        alert_type = "FCW" if abs(p1.heading - p2.heading) < 45 else "INTERSECTION_COLLISION_WARNING"
                        action = "EMERGENCY_BRAKE" if severity == AlertSeverity.CRITICAL else "DECELERATE_AND_PREPARE_TO_STOP"
                        alert = SafetyAlert(
                            alert_id=f"ALT_V2V_{p1.track_id}_{p2.track_id}_{int(time.time()*10)}",
                            timestamp=time.time(),
                            alert_type=alert_type,
                            severity=severity,
                            primary_entity_id=p1.track_id,
                            target_entity_id=p2.track_id,
                            ttc_seconds=round(t_val, 2),
                            message=f"{severity.value}: {alert_type} detected with {p2.track_id} (TTC: {t_val:.1f}s)",
                            recommended_action=action
                        )
                    alerts.append(alert)

        # Check Red Light Violations against SPaT
        if spat:
            for p in track_list:
                if p.entity_type == "vehicle" and not p.is_emergency:
                    rl_alert = self._check_red_light_runner(p, spat)
                    if rl_alert:
                        alerts.append(rl_alert)

        latency_ms = (time.perf_counter() - t_start) * 1000.0
        self.last_inference_latency_ms = round(latency_ms, 3)
        return alerts, self.last_inference_latency_ms

    def _check_red_light_runner(self, vehicle: FusedTrack, spat: SPaTMessage) -> Optional[SafetyAlert]:
        """Detects if a vehicle approaching a red signal has insufficient braking distance."""
        # Find which approach the vehicle is in
        approach = None
        dist_to_stopline = 999.0

        if abs(vehicle.x) <= 15.0:
            if vehicle.y > 25.0 and vehicle.vy < -2.0:  # Moving South
                approach = "NORTH"
                dist_to_stopline = vehicle.y - 25.0
            elif vehicle.y < -25.0 and vehicle.vy > 2.0:  # Moving North
                approach = "SOUTH"
                dist_to_stopline = -25.0 - vehicle.y
        elif abs(vehicle.y) <= 15.0:
            if vehicle.x > 25.0 and vehicle.vx < -2.0:  # Moving West
                approach = "EAST"
                dist_to_stopline = vehicle.x - 25.0
            elif vehicle.x < -25.0 and vehicle.vx > 2.0:  # Moving East
                approach = "WEST"
                dist_to_stopline = -25.0 - vehicle.x

        if approach and 0.0 < dist_to_stopline < 45.0:
            # Check signal state for this approach
            for phase in spat.phases.values():
                if phase.approach_direction == approach:
                    if phase.current_state in [SignalPhase.RED, SignalPhase.YELLOW]:
                        # Required braking deceleration a = v^2 / (2 * d)
                        req_decel = (vehicle.speed ** 2) / (2.0 * max(dist_to_stopline, 1.0))
                        # If vehicle is driving fast and deceleration required exceeds comfortable limit (> 4.5 m/s^2)
                        if req_decel > 4.5 and vehicle.speed > 8.0:
                            return SafetyAlert(
                                alert_id=f"ALT_RL_{vehicle.track_id}_{int(time.time()*10)}",
                                timestamp=time.time(),
                                alert_type="RED_LIGHT_RUNNER",
                                severity=AlertSeverity.CRITICAL,
                                primary_entity_id=vehicle.track_id,
                                target_entity_id=f"INT_SIGNAL_{approach}",
                                ttc_seconds=round(dist_to_stopline / max(vehicle.speed, 0.1), 2),
                                message=f"CRITICAL RED LIGHT VIOLATION: {vehicle.track_id} cannot stop safely ({vehicle.speed*3.6:.0f} km/h, {dist_to_stopline:.1f}m to stop line)",
                                recommended_action="HOLD_CROSS_TRAFFIC_AND_APPLY_EMERGENCY_BRAKE"
                            )
        return None
