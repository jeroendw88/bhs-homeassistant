"""One-time BHS device registration; private material remains in HA config storage.

BHS REST encryption is not supported by this integration. The RSA private key
is nevertheless retained so a future implementation does not orphan devices.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from aiohttp import ClientError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .exceptions import BHSApiError, BHSConnectionError


def create_device_credentials() -> tuple[str, str, str]:
    """Generate a fresh UUID v4 and an RSA 2048-bit key pair (executor only)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return str(uuid4()), private_key, public_key


async def register_bhs_device(
    session: Any, host: str, port: int, device_id: str,
    public_key: str, name: str,
) -> str:
    """Register exactly once, returning Approved or Pending.

    Do not retry automatically: request delivery may succeed despite a lost
    response. BHS would reject the second call with HTTP 409.
    """
    address = host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
    url = f"http://{address}:{port}/api/device/register"
    try:
        async with session.post(
            url,
            headers={"x-device-id": device_id, "Content-Type": "application/json"},
            json={"name": name, "platf": "android", "publicKey": public_key},
            timeout=15,
        ) as response:
            payload = await response.json(content_type=None)
            if response.status != 201:
                message = payload.get("error", "registration failed") if isinstance(payload, dict) else "registration failed"
                raise BHSApiError(f"BHS registration HTTP {response.status}: {message}")
    except (ClientError, TimeoutError, ValueError) as err:
        raise BHSConnectionError("Unable to contact BHS for device registration") from err
    if not isinstance(payload, dict) or payload.get("registered") is not True:
        raise BHSApiError("BHS did not confirm device registration")
    if payload.get("device") != device_id:
        raise BHSApiError("BHS registration returned an unexpected device ID")
    status = payload.get("status", "Approved")
    if status not in ("Approved", "Pending"):
        raise BHSApiError(f"Unexpected BHS registration status: {status}")
    return status
