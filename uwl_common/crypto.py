from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from Crypto.Cipher import AES


class CryptoError(Exception):
    pass


def b64decode_key(key_b64: str) -> bytes:
    key = base64.b64decode(key_b64)
    if len(key) not in (16, 24, 32):
        raise CryptoError(f"Invalid AES key length {len(key)}; expected 16/24/32 bytes.")
    return key


@dataclass(frozen=True)
class EncryptedPacket:
    """UWL encrypted envelope.

    payload is AES-GCM with:
      - nonce: 12 bytes
      - aad: optional
    """
    nonce_hex: str
    ciphertext_hex: str
    tag_hex: str
    sha256_hex: str
    prev_sha256_hex: Optional[str] = None


def encrypt_gcm(key: bytes, payload: Dict[str, Any], *, aad: bytes = b"", prev_hash_hex: Optional[str] = None) -> Dict[str, Any]:
    nonce = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    if aad:
        cipher.update(aad)

    pt = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ct, tag = cipher.encrypt_and_digest(pt)

    sha = hashlib.sha256(nonce + ct + tag + (prev_hash_hex.encode() if prev_hash_hex else b"")).hexdigest()
    pkt = EncryptedPacket(
        nonce_hex=nonce.hex(),
        ciphertext_hex=ct.hex(),
        tag_hex=tag.hex(),
        sha256_hex=sha,
        prev_sha256_hex=prev_hash_hex,
    )
    return pkt.__dict__


def decrypt_gcm(key: bytes, envelope: Dict[str, Any], *, aad: bytes = b"") -> Dict[str, Any]:
    try:
        nonce = bytes.fromhex(envelope["nonce_hex"])
        ct = bytes.fromhex(envelope["ciphertext_hex"])
        tag = bytes.fromhex(envelope["tag_hex"])
    except Exception as e:
        raise CryptoError(f"Malformed envelope: {e}") from e

    # Optional integrity chain verification (best-effort)
    prev_hash_hex = envelope.get("prev_sha256_hex")
    expected_sha = hashlib.sha256(nonce + ct + tag + (prev_hash_hex.encode() if prev_hash_hex else b"")).hexdigest()
    if expected_sha != envelope.get("sha256_hex"):
        raise CryptoError("SHA256 mismatch (tampered or corrupted packet).")

    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    if aad:
        cipher.update(aad)

    try:
        pt = cipher.decrypt_and_verify(ct, tag)
    except Exception as e:
        raise CryptoError(f"Auth failed: {e}") from e

    try:
        return json.loads(pt.decode("utf-8"))
    except Exception as e:
        raise CryptoError(f"Invalid JSON payload: {e}") from e
