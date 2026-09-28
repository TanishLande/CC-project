"""
Safety Alert Manager.
Handles formatting, dispatching, and filtering safety alerts sent over C-V2X PC5.
"""

from typing import List, Dict
import time
from backend.models import SafetyAlert, AlertSeverity


class SafetyAlertManager:
    def __init__(self, suppression_window_sec: float = 1.0):
        self.suppression_window_sec = suppression_window_sec
        self._recent_alerts: Dict[str, float] = {}  # key -> timestamp

    def filter_and_broadcast(self, incoming_alerts: List[SafetyAlert]) -> List[SafetyAlert]:
        """Suppresses redundant repetitive alerts for the same pair within suppression window."""
        now = time.time()
        dispatched: List[SafetyAlert] = []

        for alert in incoming_alerts:
            key = f"{alert.alert_type}:{alert.primary_entity_id}:{alert.target_entity_id}"
            last_time = self._recent_alerts.get(key, 0.0)

            if now - last_time >= self.suppression_window_sec:
                self._recent_alerts[key] = now
                dispatched.append(alert)

        # Cleanup old suppression keys
        if len(self._recent_alerts) > 1000:
            cutoff = now - self.suppression_window_sec * 3
            self._recent_alerts = {k: v for k, v in self._recent_alerts.items() if v > cutoff}

        return dispatched
