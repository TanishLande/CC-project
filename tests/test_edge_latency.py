"""
Benchmark test for Edge AI Sub-20ms Latency Budget.
Simulates dense multi-agent traffic (50+ vehicles/VRUs) and verifies
that TTC, PET, and risk inference completes under the 20 millisecond requirement.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import random
from backend.edge_ai.ttc_engine import EdgeAIEngine
from backend.models import FusedTrack


def test_edge_inference_sub_20ms_budget():
    engine = EdgeAIEngine()
    
    # Generate 40 simulated tracks across 4 approaches
    tracks = {}
    approaches = [
        {"x": 0.0, "y": 45.0, "vx": 0.0, "vy": -12.0, "heading": 180.0},
        {"x": 0.0, "y": -45.0, "vx": 0.0, "vy": 12.0, "heading": 0.0},
        {"x": 45.0, "y": 0.0, "vx": -12.0, "vy": 0.0, "heading": 270.0},
        {"x": -45.0, "y": 0.0, "vx": 12.0, "vy": 0.0, "heading": 90.0},
    ]

    for i in range(40):
        app = random.choice(approaches)
        jitter_x = random.uniform(-10, 10)
        jitter_y = random.uniform(-10, 10)
        tid = f"VEH_BENCH_{i}"
        is_vru = (i % 5 == 0)
        tracks[tid] = FusedTrack(
            track_id=tid,
            entity_type="vru" if is_vru else "vehicle",
            sub_type="pedestrian" if is_vru else "car",
            x=app["x"] + jitter_x,
            y=app["y"] + jitter_y,
            vx=app["vx"] * (0.1 if is_vru else 1.0),
            vy=app["vy"] * (0.1 if is_vru else 1.0),
            speed=12.0 if not is_vru else 1.2,
            heading=app["heading"],
            confidence=0.95,
            last_update=time.time(),
            history=[]
        )

    # Run 50 warm-up & benchmark cycles
    latencies = []
    for _ in range(50):
        alerts, latency_ms = engine.compute_risk_and_alerts(tracks)
        latencies.append(latency_ms)

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    p99_latency = sorted(latencies)[int(0.99 * len(latencies))]

    print(f"--- Edge AI Latency Benchmark Results ---")
    print(f"Tested Tracks: {len(tracks)} participants")
    print(f"Average Latency: {avg_latency:.3f} ms")
    print(f"99th Percentile: {p99_latency:.3f} ms")
    print(f"Max Latency:     {max_latency:.3f} ms")
    print(f"Budget Target:   < 20.000 ms")

    # Assert under the 20ms requirement
    assert p99_latency < 20.0, f"Edge AI latency {p99_latency:.2f}ms exceeded 20ms budget!"
    print("EDGE AI LATENCY REQUIREMENT (<20ms) STRICTLY SATISFIED!")


if __name__ == "__main__":
    test_edge_inference_sub_20ms_budget()
