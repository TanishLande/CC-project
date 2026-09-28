"""
High-Speed Event Streaming Bus (Kafka-compatible interface).
Streams and broadcasts events across topics:
- v2x.telemetry.raw
- v2x.ldm.fused
- v2x.safety.alerts
- v2x.emergency.preemption
- v2x.incidents.cloud
"""

import asyncio
from typing import Dict, List, Callable, Any
import time


class EventStreamingBus:
    def __init__(self, max_buffer_per_topic: int = 1000):
        self.max_buffer = max_buffer_per_topic
        # topic -> list of event records
        self._buffers: Dict[str, List[Dict[str, Any]]] = {
            "v2x.telemetry.raw": [],
            "v2x.ldm.fused": [],
            "v2x.safety.alerts": [],
            "v2x.emergency.preemption": [],
            "v2x.incidents.cloud": []
        }
        # topic -> list of subscriber callables
        self._subscribers: Dict[str, List[Callable]] = {
            k: [] for k in self._buffers.keys()
        }

    def publish(self, topic: str, payload: Any) -> None:
        """Publish an event record onto a streaming topic."""
        record = {
            "timestamp": time.time(),
            "topic": topic,
            "data": payload
        }
        if topic not in self._buffers:
            self._buffers[topic] = []
            self._subscribers[topic] = []

        buf = self._buffers[topic]
        buf.append(record)
        if len(buf) > self.max_buffer:
            buf.pop(0)

        # Notify subscribers
        for sub in self._subscribers.get(topic, []):
            try:
                sub(record)
            except Exception:
                pass

    def subscribe(self, topic: str, callback: Callable) -> None:
        if topic not in self._subscribers:
            self._subscribers[topic] = []
            self._buffers[topic] = []
        self._subscribers[topic].append(callback)

    def get_recent(self, topic: str, count: int = 50) -> List[Dict[str, Any]]:
        buf = self._buffers.get(topic, [])
        return buf[-count:]
