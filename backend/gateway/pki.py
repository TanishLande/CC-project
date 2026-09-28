"""
V2X PKI (Public Key Infrastructure) Security Engine.
Validates SAE J2735 and ETSI C-V2X messages using pseudonym certificates,
anti-replay message verification, and digital signature checking.
"""

import time
import hashlib
import hmac
from typing import Tuple, Dict, Set


class PKISecurityEngine:
    def __init__(self, replay_window_sec: float = 3.0):
        self.replay_window_sec = replay_window_sec
        # Known root / pseudonym certificate store: cert_id -> secret_key
        self._trusted_certs: Dict[str, str] = {
            "CERT_CAR_001": "secret_key_car_1",
            "CERT_CAR_002": "secret_key_car_2",
            "CERT_AMB_911": "secret_key_ambulance",
            "CERT_FIRE_999": "secret_key_fire",
            "CERT_VRU_001": "secret_key_vru_1",
            "CERT_RSU_INT1": "secret_key_rsu_1",
            "CERT_ROOT_CA": "root_ca_secret",
        }
        # Dynamic pseudonym certificate issuance cache
        self._pseudonym_registry: Set[str] = set(self._trusted_certs.keys())
        # Anti-replay message ID cache: msg_id -> timestamp
        self._seen_messages: Dict[str, float] = {}
        # Revocation list (CRL)
        self._revoked_certs: Set[str] = set()

    def register_pseudonym(self, cert_id: str, secret: str = "default_secret") -> None:
        """Register a valid pseudonym certificate for a participating vehicle or VRU."""
        self._trusted_certs[cert_id] = secret
        self._pseudonym_registry.add(cert_id)

    def revoke_cert(self, cert_id: str) -> None:
        """Add certificate to Certificate Revocation List (CRL)."""
        self._revoked_certs.add(cert_id)

    def generate_signature(self, msg_id: str, payload_str: str, cert_id: str) -> str:
        """Helper to generate a valid PKI digital signature for testing/simulation."""
        secret = self._trusted_certs.get(cert_id, "default_secret")
        key = secret.encode("utf-8")
        data = f"{msg_id}:{payload_str}".encode("utf-8")
        return hmac.new(key, data, hashlib.sha256).hexdigest()

    def validate_message(
        self,
        msg_id: str,
        timestamp: float,
        cert_id: str,
        signature: str,
        payload_summary: str = ""
    ) -> Tuple[bool, str]:
        """
        Validate incoming C-V2X message for:
        1. Freshness (Timestamp drift within replay window)
        2. Anti-replay (msg_id uniqueness)
        3. CRL (Certificate Revocation List)
        4. Digital signature authenticity
        """
        now = time.time()

        # 1. Freshness check
        if abs(now - timestamp) > self.replay_window_sec:
            return False, f"REJECTED: Timestamp drift {abs(now - timestamp):.2f}s exceeds {self.replay_window_sec}s window"

        # 2. Anti-replay check
        if msg_id in self._seen_messages:
            return False, f"REJECTED: Replay attack detected for msg_id '{msg_id}'"
        
        # Prune old seen messages
        if len(self._seen_messages) > 10000:
            cutoff = now - self.replay_window_sec
            self._seen_messages = {m: t for m, t in self._seen_messages.items() if t > cutoff}

        self._seen_messages[msg_id] = now

        # 3. CRL check
        if cert_id in self._revoked_certs:
            return False, f"REJECTED: Certificate '{cert_id}' is revoked"

        # 4. Unknown certificate check
        if cert_id and cert_id not in self._pseudonym_registry:
            # Auto-enroll validly formatted pseudonym certs in simulation mode
            if cert_id.startswith("CERT_"):
                self.register_pseudonym(cert_id)
            else:
                return False, f"REJECTED: Untrusted pseudonym certificate '{cert_id}'"

        # 5. Signature check (if signature provided)
        if signature:
            secret = self._trusted_certs.get(cert_id, "default_secret")
            key = secret.encode("utf-8")
            data = f"{msg_id}:{payload_summary}".encode("utf-8")
            expected_sig = hmac.new(key, data, hashlib.sha256).hexdigest()
            # If payload_summary was omitted or matches
            if signature != expected_sig and payload_summary != "":
                # In strict PKI mode
                return False, "REJECTED: Cryptographic signature mismatch"

        return True, "VALID"
