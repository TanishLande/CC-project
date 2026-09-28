"""
Tests for Emergency Vehicle Preemption (EVP) Engine and Corridor Clearance.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
from backend.signal_control.adaptive_controller import AdaptiveSignalController
from backend.models import SignalPhase


def test_emergency_preemption_lifecycle():
    controller = AdaptiveSignalController(intersection_id="INT_01", min_green_sec=5.0, yellow_sec=2.0)
    
    # 1. Start normal operation
    spat = controller.step(dt=1.0, queue_lengths={"NORTH": 4, "SOUTH": 4, "EAST": 2, "WEST": 2})
    assert spat.preemption_active is False

    # 2. Trigger preemption for Ambulance arriving on EAST approach (Phases 3 & 4)
    # Notice: NS was GREEN, so EW was RED
    event = controller.trigger_preemption(vehicle_id="AMB_911", approach="EAST", eta_seconds=7.0)
    assert event["stage"] == "TRANSITION_CLEARANCE"

    # Step through clearance yellow
    spat = controller.step(dt=1.0, queue_lengths={})
    assert controller.preemption_engine.active_preemption is not None

    # Step past yellow duration (2.5s) to ALL_RED
    controller.preemption_engine.active_preemption["stage_started_at"] -= 3.0
    spat = controller.step(dt=0.1, queue_lengths={})
    assert controller.preemption_engine.active_preemption["stage"] == "ALL_RED"

    # Step past all-red duration (1.0s) to ACTIVE_GREEN
    controller.preemption_engine.active_preemption["stage_started_at"] -= 1.5
    spat = controller.step(dt=0.1, queue_lengths={})
    assert controller.preemption_engine.active_preemption["stage"] == "ACTIVE_GREEN"
    
    # Assert EAST approach (Phase 3) is now PREEMPTION_GREEN
    assert spat.phases[3].current_state == SignalPhase.PREEMPTION_GREEN
    assert spat.phases[1].current_state == SignalPhase.RED

    # 3. Vehicle clears intersection
    cleared = controller.clear_preemption()
    assert cleared is not None
    assert cleared["vehicle_id"] == "AMB_911"
    assert controller.preemption_engine.active_preemption is None

    print("ALL EMERGENCY PREEMPTION TESTS PASSED!")


if __name__ == "__main__":
    test_emergency_preemption_lifecycle()
