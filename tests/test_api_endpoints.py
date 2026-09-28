"""
Integration test for FastAPI REST API endpoints and Edge AI orchestrator.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from starlette.testclient import TestClient
from backend.main import app


def test_api_endpoints():
    client = TestClient(app)

    # 1. Test /api/status
    res = client.get("/api/status")
    assert res.status_code == 200
    status_data = res.json()
    assert status_data["status"] == "ONLINE"
    assert status_data["problem_statement"] == "SIH26203"
    assert "edge_compute" in status_data
    print("GET /api/status: OK")

    # 2. Test /api/ldm
    res = client.get("/api/ldm")
    assert res.status_code == 200
    ldm_data = res.json()
    assert ldm_data["intersection_id"] == "INT_01"
    print("GET /api/ldm: OK")

    # 3. Test /api/metrics
    res = client.get("/api/metrics")
    assert res.status_code == 200
    metrics_data = res.json()
    assert "impact_benchmarks" in metrics_data
    assert metrics_data["impact_benchmarks"]["conservative"]["crash_reduction_pct"] == 26
    print("GET /api/metrics: OK")

    # 4. Test /api/corridor
    res = client.get("/api/corridor")
    assert res.status_code == 200
    corridor_data = res.json()
    assert len(corridor_data["intersections"]) >= 3
    print("GET /api/corridor: OK")

    # 5. Test /api/scenario
    res = client.post("/api/scenario", json={"scenario": "PEAK_HOUR"})
    assert res.status_code == 200
    res = client.post("/api/scenario", json={"scenario": "EMERGENCY_AMBULANCE"})
    assert res.status_code == 200
    assert "vehicle_id" in res.json()
    print("POST /api/scenario: OK")

    # 6. Test /api/preempt
    res = client.post("/api/preempt", json={"vehicle_id": "AMB_911", "approach": "SOUTH", "eta_seconds": 6.0})
    assert res.status_code == 200
    assert res.json()["status"] == "PREEMPTION_ACTIVE"
    print("POST /api/preempt: OK")

    # 7. Test /api/copilot/debrief
    res = client.post("/api/copilot/debrief")
    assert res.status_code == 200
    assert "content" in res.json()
    print("POST /api/copilot/debrief: OK")

    # 8. Test /api/copilot/chat
    res = client.post("/api/copilot/chat", json={"query": "What is the status of the emergency corridor?"})
    assert res.status_code == 200
    assert "answer" in res.json()
    print(f"POST /api/copilot/chat: OK -> {res.json()['answer'][:60]}...")

    print("\nALL API INTEGRATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_api_endpoints()
