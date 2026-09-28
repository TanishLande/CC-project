"""
Mobility Data Lake & Cloud Telemetry Analytics.
Stores trajectory history, near-miss events, preemption clearance logs,
and calculates city-scale impact projections aligned with SIH benchmarks.
"""

import time
from typing import List, Dict, Any, Optional


class MobilityDataLake:
    def __init__(self):
        self.trajectories_logged: int = 0
        self.near_miss_incidents: List[Dict[str, Any]] = []
        self.preemption_runs: List[Dict[str, Any]] = []
        self.start_time = time.time()

        # Benchmark Statistics based on SIH proposal (Odisha road safety pilot study)
        self.impact_benchmarks = {
            "conservative": {
                "crash_reduction_pct": 26,
                "lives_saved_per_year": 1130,
                "lives_saved_10yr_cumulative": 12428,
            },
            "optimistic": {
                "crash_reduction_pct": 80,
                "lives_saved_per_year": 3476,
                "lives_saved_10yr_cumulative": 38240,
            },
            "emergency_preemption": {
                "avg_response_time_reduction_pct": 48.5,
                "ambulance_delay_saved_sec_per_run": 74.2,
                "zero_delay_corridors_created": 0,
            }
        }

    def log_incident(self, incident: Dict[str, Any]) -> None:
        """Stores a near-miss or safety critical incident."""
        incident["logged_at"] = time.time()
        self.near_miss_incidents.append(incident)
        if len(self.near_miss_incidents) > 500:
            self.near_miss_incidents.pop(0)

    def log_preemption_event(self, event: Dict[str, Any]) -> None:
        """Stores emergency preemption performance."""
        event["logged_at"] = time.time()
        self.preemption_runs.append(event)
        self.impact_benchmarks["emergency_preemption"]["zero_delay_corridors_created"] += 1
        if len(self.preemption_runs) > 200:
            self.preemption_runs.pop(0)

    def get_summary_metrics(self) -> Dict[str, Any]:
        uptime_sec = round(time.time() - self.start_time, 1)
        total_incidents_prevented = len(self.near_miss_incidents)
        preemptions_cleared = len(self.preemption_runs)
        
        # Computed live lives saved estimate in current simulation runtime
        simulated_lives_saved = round(total_incidents_prevented * 0.18 + preemptions_cleared * 0.45, 1)

        return {
            "uptime_seconds": uptime_sec,
            "trajectories_logged": self.trajectories_logged,
            "near_miss_count": total_incidents_prevented,
            "preemptions_count": preemptions_cleared,
            "simulated_lives_saved": simulated_lives_saved,
            "impact_benchmarks": self.impact_benchmarks,
            "recent_incidents": self.near_miss_incidents[-10:],
            "recent_preemptions": self.preemption_runs[-10:]
        }
