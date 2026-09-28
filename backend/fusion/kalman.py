"""
Kalman Filter for multi-object tracking and state estimation in V2X.
Estimates 2D position (x, y) and velocity (vx, vy) for vehicles and VRUs.
"""

import numpy as np
import math
import time
from typing import Tuple


class KalmanTrack:
    def __init__(self, track_id: str, x: float, y: float, vx: float = 0.0, vy: float = 0.0):
        self.track_id = track_id
        # State vector: [x, y, vx, vy]^T
        self.x = np.array([[x], [y], [vx], [vy]], dtype=np.float64)
        
        # State covariance matrix P
        self.P = np.eye(4, dtype=np.float64) * 10.0
        self.P[2, 2] = 25.0
        self.P[3, 3] = 25.0
        
        # Measurement matrix H (measuring [x, y])
        self.H = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0]
        ], dtype=np.float64)
        
        # Measurement noise covariance R
        self.R = np.array([
            [1.5, 0.0],
            [0.0, 1.5]
        ], dtype=np.float64)
        
        # Process noise variance
        self.q_var = 0.8
        self.last_timestamp = time.time()
        self.hit_count = 1
        self.miss_count = 0

    def predict(self, dt: float = 0.1) -> np.ndarray:
        if dt <= 0:
            dt = 0.05
            
        # State transition matrix F
        F = np.array([
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ], dtype=np.float64)

        # Process noise covariance Q
        dt2 = dt * dt
        dt3 = dt2 * dt / 2.0
        dt4 = dt2 * dt2 / 4.0
        Q = np.array([
            [dt4, 0.0, dt3, 0.0],
            [0.0, dt4, 0.0, dt3],
            [dt3, 0.0, dt2, 0.0],
            [0.0, dt3, 0.0, dt2]
        ], dtype=np.float64) * self.q_var

        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q
        return self.x

    def update(self, meas_x: float, meas_y: float) -> None:
        z = np.array([[meas_x], [meas_y]], dtype=np.float64)
        y = z - (self.H @ self.x)  # Measurement residual
        S = self.H @ self.P @ self.H.T + self.R  # Residual covariance
        K = self.P @ self.H.T @ np.linalg.inv(S)  # Optimal Kalman gain

        self.x = self.x + (K @ y)
        I = np.eye(4, dtype=np.float64)
        self.P = (I - K @ self.H) @ self.P

        self.hit_count += 1
        self.miss_count = 0
        self.last_timestamp = time.time()

    def get_state(self) -> Tuple[float, float, float, float, float, float]:
        """Returns (x, y, vx, vy, speed, heading_deg)"""
        pos_x = float(self.x[0, 0])
        pos_y = float(self.x[1, 0])
        vx = float(self.x[2, 0])
        vy = float(self.x[3, 0])
        speed = math.sqrt(vx * vx + vy * vy)
        
        # Heading: 0 deg = North (+y), 90 deg = East (+x), 180 deg = South (-y), 270 = West (-x)
        heading_rad = math.atan2(vx, vy)
        heading_deg = (math.degrees(heading_rad) + 360.0) % 360.0
        
        return pos_x, pos_y, vx, vy, speed, heading_deg
