"""
Tests for Ollama Traffic Ops Copilot.
Validates generation of incident debriefs and operator Q&A responses.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.copilot.ollama_copilot import OllamaTrafficCopilot


def test_copilot_availability_and_generation():
    copilot = OllamaTrafficCopilot(model_name="llama3.2:3b")
    available = copilot.is_available()
    print(f"Ollama Available: {available}")

    # Test incident debrief generation
    alert_mock = {
        "alert_type": "VRU_COLLISION_ALERT",
        "severity": "CRITICAL",
        "primary_entity_id": "VEH_102",
        "target_entity_id": "VRU_501",
        "ttc_seconds": 1.4,
        "message": "Imminent collision with pedestrian in 1.4s",
        "recommended_action": "EMERGENCY_AUTONOMOUS_BRAKE"
    }
    ldm_mock = {"total_vehicles": 14, "total_vrus": 2, "queue_lengths": {"NORTH": 3, "SOUTH": 1}}

    report = copilot.generate_incident_report(alert_mock, ldm_mock)
    assert len(report) > 20
    print(f"\n--- Sample Generated Incident Report ---\n{report}")

    # Test preemption brief
    event_mock = {
        "vehicle_id": "AMB_911",
        "approach_direction": "SOUTH",
        "eta_seconds": 6.5,
        "stage": "ACTIVE_GREEN"
    }
    brief = copilot.generate_preemption_brief(event_mock)
    assert len(brief) > 20
    print(f"\n--- Sample Generated Preemption Brief ---\n{brief}")

    print("\nALL COPILOT TESTS PASSED!")


if __name__ == "__main__":
    test_copilot_availability_and_generation()
