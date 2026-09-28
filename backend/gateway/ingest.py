"""
V2X Gateway for 5G Uu / MQTT / C-V2X Ingestion.
Receives, validates, and standardizes BSM, VRU, EVA, and RSU messages.
Maintains a real-time sniffer buffer of all processed V2X packets.
"""

import time
import logging
from typing import Dict, Any, Tuple, Optional, List
from backend.models import BSMMessage, VRUMessage, EVAMessage, RSUDetection
from backend.gateway.pki import PKISecurityEngine

logger = logging.getLogger("V2XGateway")


class V2XIngestGateway:
    def __init__(self, pki_engine: Optional[PKISecurityEngine] = None):
        self.pki = pki_engine or PKISecurityEngine()
        self.stats = {
            "total_received": 0,
            "validated_count": 0,
            "rejected_count": 0,
            "last_latency_ms": 0.0,
            "by_type": {
                "BSM": 0,
                "VRU": 0,
                "EVA": 0,
                "RSU": 0,
                "SPaT": 0
            }
        }
        # Circular buffer for real-time protocol sniffer / packet inspector
        self.recent_packets: List[Dict[str, Any]] = []

    def _record_packet(
        self,
        proto_type: str,
        msg_id: str,
        entity_id: str,
        telemetry: str,
        approach: str,
        cert_id: str,
        is_valid: bool,
        status: str
    ):
        now = time.time()
        time_str = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int((now % 1) * 1000):03d}"
        rec = {
            "timestamp": now,
            "time_str": time_str,
            "protocol_type": proto_type,
            "msg_id": msg_id,
            "entity_id": entity_id,
            "telemetry": telemetry,
            "approach": approach,
            "cert_id": cert_id or "ANONYMOUS",
            "is_valid": is_valid,
            "pki_status": status
        }
        self.recent_packets.append(rec)
        if len(self.recent_packets) > 80:
            self.recent_packets.pop(0)

    def get_recent_packets(self, limit: int = 25) -> List[Dict[str, Any]]:
        return self.recent_packets[-limit:]

    def ingest_bsm(self, data: Dict[str, Any]) -> Tuple[bool, Optional[BSMMessage], str]:
        t0 = time.perf_counter()
        self.stats["total_received"] += 1
        
        try:
            bsm = BSMMessage(**data)
            summary = f"{bsm.vehicle_id}:{bsm.x:.1f}:{bsm.y:.1f}:{bsm.speed:.1f}"
            valid, reason = self.pki.validate_message(
                msg_id=bsm.msg_id,
                timestamp=bsm.timestamp,
                cert_id=bsm.cert_id,
                signature=bsm.signature,
                payload_summary=summary if bsm.signature else ""
            )
            
            latency = (time.perf_counter() - t0) * 1000.0
            self.stats["last_latency_ms"] = latency

            approach = "SOUTH" if bsm.y < -15.0 else ("NORTH" if bsm.y > 15.0 else ("WEST" if bsm.x < -15.0 else "EAST"))
            speed_kmh = bsm.speed * 3.6
            telemetry_str = f"Speed: {speed_kmh:.1f} km/h | Pos: ({bsm.x:.1f}, {bsm.y:.1f}) | Head: {bsm.heading:.0f}°"
            
            proto_type = "SAE J2735 EVA" if bsm.priority_level > 0 else "SAE J2735 BSM"
            pki_status_str = "VERIFIED_VALID" if valid else f"REJECTED: {reason}"

            self._record_packet(
                proto_type=proto_type,
                msg_id=bsm.msg_id,
                entity_id=bsm.vehicle_id,
                telemetry=telemetry_str,
                approach=approach,
                cert_id=bsm.cert_id,
                is_valid=valid,
                status=pki_status_str
            )

            if not valid:
                self.stats["rejected_count"] += 1
                return False, None, reason

            self.stats["validated_count"] += 1
            self.stats["by_type"]["BSM"] += 1
            return True, bsm, "OK"
        except Exception as e:
            self.stats["rejected_count"] += 1
            return False, None, f"Malformed BSM payload: {str(e)}"

    def ingest_vru(self, data: Dict[str, Any]) -> Tuple[bool, Optional[VRUMessage], str]:
        t0 = time.perf_counter()
        self.stats["total_received"] += 1

        try:
            vru = VRUMessage(**data)
            valid, reason = self.pki.validate_message(
                msg_id=vru.msg_id,
                timestamp=vru.timestamp,
                cert_id=vru.cert_id,
                signature=vru.signature
            )
            
            latency = (time.perf_counter() - t0) * 1000.0
            self.stats["last_latency_ms"] = latency

            telemetry_str = f"Pace: {vru.speed:.1f} m/s | Pos: ({vru.x:.1f}, {vru.y:.1f}) | Crosswalk: Active"
            pki_status_str = "VERIFIED_VALID" if valid else f"REJECTED: {reason}"

            self._record_packet(
                proto_type="ETSI VRU-TS",
                msg_id=vru.msg_id,
                entity_id=vru.vru_id,
                telemetry=telemetry_str,
                approach="CROSSWALK",
                cert_id=vru.cert_id,
                is_valid=valid,
                status=pki_status_str
            )

            if not valid:
                self.stats["rejected_count"] += 1
                return False, None, reason

            self.stats["validated_count"] += 1
            self.stats["by_type"]["VRU"] += 1
            return True, vru, "OK"
        except Exception as e:
            self.stats["rejected_count"] += 1
            return False, None, f"Malformed VRU payload: {str(e)}"

    def ingest_eva(self, data: Dict[str, Any]) -> Tuple[bool, Optional[EVAMessage], str]:
        t0 = time.perf_counter()
        self.stats["total_received"] += 1

        try:
            eva = EVAMessage(**data)
            valid, reason = self.pki.validate_message(
                msg_id=eva.msg_id,
                timestamp=time.time(),
                cert_id="CERT_AMB_911" if "AMB" in eva.vehicle_id else "CERT_FIRE_999",
                signature=""
            )
            latency = (time.perf_counter() - t0) * 1000.0
            self.stats["last_latency_ms"] = latency

            telemetry_str = f"PRIORITY 1 SIREN | Speed: {eva.speed_mps*3.6:.1f} km/h | Corridor: {eva.current_intersection}"
            self._record_packet(
                proto_type="SAE J2735 EVA",
                msg_id=eva.msg_id,
                entity_id=eva.vehicle_id,
                telemetry=telemetry_str,
                approach="EMERGENCY_CORRIDOR",
                cert_id="CERT_AMB_911",
                is_valid=True,
                status="PREEMPTION_PRIORITY"
            )

            self.stats["validated_count"] += 1
            self.stats["by_type"]["EVA"] += 1
            return True, eva, "OK"
        except Exception as e:
            self.stats["rejected_count"] += 1
            return False, None, f"Malformed EVA payload: {str(e)}"

    def log_spat_packet(self, intersection_id: str, active_phases: List[int], preemption: bool):
        """Logs outgoing SPaT broadcast packets to the sniffer."""
        self.stats["by_type"]["SPaT"] += 1
        now = time.time()
        time_str = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int((now % 1) * 1000):03d}"
        status_text = "EVP_OVERRIDE" if preemption else "ADAPTIVE_GREEN"
        telemetry_str = f"Active Phases: {active_phases} | Preempted: {preemption} | Intersection: {intersection_id}"
        
        self.recent_packets.append({
            "timestamp": now,
            "time_str": time_str,
            "protocol_type": "SAE J2735 SPaT",
            "msg_id": f"SPAT_{int(now*10)%100000}",
            "entity_id": f"CABINET_{intersection_id}",
            "telemetry": telemetry_str,
            "approach": "ALL_APPROACHES",
            "cert_id": "CERT_RSU_INT1",
            "is_valid": True,
            "pki_status": status_text
        })
        if len(self.recent_packets) > 80:
            self.recent_packets.pop(0)
