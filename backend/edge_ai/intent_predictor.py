"""
Edge AI Intent Predictor.
Predicts vehicle turning intentions, VRU crossing intentions, and trajectory anomalies.
"""

import math
from typing import Dict, List, Tuple
from backend.models import FusedTrack, VRUType


class IntentPredictor:
    def predict_intent(self, track: FusedTrack) -> str:
        """
        Classifies short-term behavioral intent:
        - "STRAIGHT_CRUISING"
        - "TURNING_LEFT"
        - "TURNING_RIGHT"
        - "CROSSING_ROADWAY"
        - "STOPPING"
        """
        if track.entity_type == "vru":
            if track.speed > 0.4:
                # If moving perpendicular to sidewalk
                if abs(track.vx) > abs(track.vy):
                    return "CROSSING_ROADWAY"
                return "WALKING_ALONG_SIDEWALK"
            return "WAITING_AT_CURB"

        # Vehicle intent
        if track.speed < 1.0:
            return "STOPPED_IN_QUEUE"

        if len(track.history) >= 4:
            p_old = track.history[-4]
            p_now = track.history[-1]
            dx = p_now[0] - p_old[0]
            dy = p_now[1] - p_old[1]
            heading_change = (math.atan2(dx, dy) - math.radians(track.heading))
            if heading_change > 0.2:
                return "TURNING_RIGHT"
            elif heading_change < -0.2:
                return "TURNING_LEFT"

        return "STRAIGHT_CRUISING"
