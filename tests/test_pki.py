"""
Tests for PKI Security Engine and Ingest Gateway.
Validates certificate verification, digital signatures, and replay attack rejection.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
from backend.gateway.pki import PKISecurityEngine
from backend.gateway.ingest import V2XIngestGateway


def test_pki_valid_message():
    pki = PKISecurityEngine()
    cert_id = "CERT_CAR_001"
    msg_id = "MSG_1001"
    now = time.time()
    payload = "VEH_1:0.0:10.0:12.5"
    sig = pki.generate_signature(msg_id, payload, cert_id)

    valid, reason = pki.validate_message(msg_id, now, cert_id, sig, payload)
    assert valid is True
    assert reason == "VALID"


def test_pki_replay_attack_rejected():
    pki = PKISecurityEngine()
    cert_id = "CERT_CAR_001"
    msg_id = "MSG_REPLAY_TEST"
    now = time.time()
    payload = "VEH_1:0.0:10.0:12.5"
    sig = pki.generate_signature(msg_id, payload, cert_id)

    # First ingest should pass
    valid, reason = pki.validate_message(msg_id, now, cert_id, sig, payload)
    assert valid is True

    # Immediate replay of the exact same msg_id must be rejected
    valid_replay, reason_replay = pki.validate_message(msg_id, now, cert_id, sig, payload)
    assert valid_replay is False
    assert "Replay attack detected" in reason_replay


def test_pki_revoked_certificate():
    pki = PKISecurityEngine()
    cert_id = "CERT_REVOKED_001"
    pki.register_pseudonym(cert_id)
    pki.revoke_cert(cert_id)

    valid, reason = pki.validate_message("MSG_2002", time.time(), cert_id, "")
    assert valid is False
    assert "revoked" in reason


def test_gateway_ingest_bsm():
    gateway = V2XIngestGateway()
    data = {
        "msg_id": f"TEST_BSM_{time.time()}",
        "vehicle_id": "CAR_42",
        "timestamp": time.time(),
        "latitude": 20.2961,
        "longitude": 85.8245,
        "x": 10.5,
        "y": -20.0,
        "speed": 12.0,
        "heading": 0.0,
        "cert_id": "CERT_CAR_42",
        "signature": ""
    }
    valid, bsm, reason = gateway.ingest_bsm(data)
    assert valid is True
    assert bsm is not None
    assert bsm.vehicle_id == "CAR_42"


if __name__ == "__main__":
    test_pki_valid_message()
    test_pki_replay_attack_rejected()
    test_pki_revoked_certificate()
    test_gateway_ingest_bsm()
    print("ALL PKI TESTS PASSED!")
