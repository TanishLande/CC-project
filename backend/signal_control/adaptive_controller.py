"""
Adaptive Signal Controller using Max-Pressure & RL Heuristics.
Dynamically adjusts phase splits, green extensions, and interfaces with
Emergency Preemption Engine to guarantee zero-delay emergency corridors.
"""

import time
from typing import Dict, List, Optional, Tuple, Any
from backend.models import SignalPhase, PhaseState, SPaTMessage
from backend.signal_control.preemption import EmergencyPreemptionEngine


class AdaptiveSignalController:
    def __init__(
        self,
        intersection_id: str = "INT_01",
        min_green_sec: float = 8.0,
        max_green_sec: float = 40.0,
        yellow_sec: float = 3.0,
        all_red_sec: float = 1.0
    ):
        self.intersection_id = intersection_id
        self.min_green = min_green_sec
        self.max_green = max_green_sec
        self.yellow = yellow_sec
        self.all_red = all_red_sec
        
        self.preemption_engine = EmergencyPreemptionEngine()

        # Phases:
        # Phase 1: North-South Through & Right (Phases 1 & 2)
        # Phase 2: East-West Through & Right (Phases 3 & 4)
        self.phases: Dict[int, PhaseState] = {
            1: PhaseState(phase_id=1, approach_direction="NORTH", current_state=SignalPhase.GREEN, time_remaining_seconds=20.0),
            2: PhaseState(phase_id=2, approach_direction="SOUTH", current_state=SignalPhase.GREEN, time_remaining_seconds=20.0),
            3: PhaseState(phase_id=3, approach_direction="EAST", current_state=SignalPhase.RED, time_remaining_seconds=20.0),
            4: PhaseState(phase_id=4, approach_direction="WEST", current_state=SignalPhase.RED, time_remaining_seconds=20.0),
        }
        
        # 0: NS Green, 1: NS Yellow, 2: EW Green, 3: EW Yellow
        self.cycle_state = "NS_GREEN"
        self.state_time_elapsed = 0.0
        self.last_step_time = time.time()
        
        # RL / Pressure optimization metrics
        self.total_delay_saved_sec = 0.0
        self.green_waves_granted = 0

    def step(self, dt: float, queue_lengths: Dict[str, int]) -> SPaTMessage:
        """
        Steps the signal controller by dt seconds.
        Integrates queue pressures and emergency preemption.
        """
        self.state_time_elapsed += dt

        # 1. Check if Preemption is currently active
        is_preempted, updated_phases = self.preemption_engine.update_preemption_lifecycle(self.phases)
        if is_preempted:
            self.phases = updated_phases
            return self._build_spat(preempted=True)

        # 2. Normal Adaptive Signal Operation
        q_ns = queue_lengths.get("NORTH", 0) + queue_lengths.get("SOUTH", 0)
        q_ew = queue_lengths.get("EAST", 0) + queue_lengths.get("WEST", 0)

        # State machine for regular adaptive cycling
        if self.cycle_state == "NS_GREEN":
            # Check if we should switch to EW
            # If max green reached, or if EW pressure is significantly higher and min green satisfied
            should_switch = (
                self.state_time_elapsed >= self.max_green or
                (self.state_time_elapsed >= self.min_green and q_ew > q_ns + 2)
            )
            time_left = max(0.0, self.max_green - self.state_time_elapsed)
            self._set_phase_states(ns_state=SignalPhase.GREEN, ew_state=SignalPhase.RED, time_left=time_left)

            if should_switch:
                self.cycle_state = "NS_YELLOW"
                self.state_time_elapsed = 0.0

        elif self.cycle_state == "NS_YELLOW":
            time_left = max(0.0, self.yellow - self.state_time_elapsed)
            self._set_phase_states(ns_state=SignalPhase.YELLOW, ew_state=SignalPhase.RED, time_left=time_left)

            if self.state_time_elapsed >= self.yellow:
                self.cycle_state = "EW_GREEN"
                self.state_time_elapsed = 0.0

        elif self.cycle_state == "EW_GREEN":
            should_switch = (
                self.state_time_elapsed >= self.max_green or
                (self.state_time_elapsed >= self.min_green and q_ns > q_ew + 2)
            )
            time_left = max(0.0, self.max_green - self.state_time_elapsed)
            self._set_phase_states(ns_state=SignalPhase.RED, ew_state=SignalPhase.GREEN, time_left=time_left)

            if should_switch:
                self.cycle_state = "EW_YELLOW"
                self.state_time_elapsed = 0.0

        elif self.cycle_state == "EW_YELLOW":
            time_left = max(0.0, self.yellow - self.state_time_elapsed)
            self._set_phase_states(ns_state=SignalPhase.RED, ew_state=SignalPhase.YELLOW, time_left=time_left)

            if self.state_time_elapsed >= self.yellow:
                self.cycle_state = "NS_GREEN"
                self.state_time_elapsed = 0.0

        return self._build_spat(preempted=False)

    def _set_phase_states(self, ns_state: SignalPhase, ew_state: SignalPhase, time_left: float):
        for pid in [1, 2]:
            self.phases[pid].current_state = ns_state
            self.phases[pid].time_remaining_seconds = round(time_left, 1)
            self.phases[pid].is_preempted = False
        for pid in [3, 4]:
            self.phases[pid].current_state = ew_state
            self.phases[pid].time_remaining_seconds = round(time_left, 1)
            self.phases[pid].is_preempted = False

    def trigger_preemption(self, vehicle_id: str, approach: str, eta_seconds: float = 8.0) -> Dict[str, Any]:
        """Triggers emergency preemption for given approach."""
        target_pids = [1, 2] if approach in ["NORTH", "SOUTH"] else [3, 4]
        self.green_waves_granted += 1
        return self.preemption_engine.request_preemption(
            vehicle_id=vehicle_id,
            approach_direction=approach,
            target_phase_ids=target_pids,
            eta_seconds=eta_seconds
        )

    def clear_preemption(self) -> Optional[Dict[str, Any]]:
        return self.preemption_engine.clear_preemption()

    def _build_spat(self, preempted: bool) -> SPaTMessage:
        active_ids = [pid for pid, p in self.phases.items() if p.current_state in [SignalPhase.GREEN, SignalPhase.PREEMPTION_GREEN]]
        ev_id = self.preemption_engine.active_preemption["vehicle_id"] if self.preemption_engine.active_preemption else None
        
        return SPaTMessage(
            intersection_id=self.intersection_id,
            timestamp=time.time(),
            phases=self.phases,
            active_phase_ids=active_ids,
            preemption_active=preempted,
            emergency_vehicle_id=ev_id
        )
