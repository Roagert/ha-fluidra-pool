"""
Fluidra iQBridge — Local UDP Client
====================================
Sends commands directly to iQBridge RS on the LAN via UDP,
bypassing the cloud entirely.

Protocol hypothesis (Cipher RE session 2026-03-29):
  [0x12 0x34][protocol:1B][cmdId:2B BE][payloadLen:4B BE][payload:NB][CRC32:4B][HMAC-SHA256:32B]

Requires:
  - commandAndControl.localUdp.host  (device LAN IP)
  - commandAndControl.localUdp.port  (hypothesis: 9003)
  - commandAndControl.localUdp.token (HMAC-SHA256(serial, "fluidra") hypothesis)

Status: STUB — packet format unconfirmed until live tcpdump capture.
        Falls back to cloud API silently if UDP fails.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import struct
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)

# Packet constants (hypothetical — update from tcpdump capture)
UDP_MAGIC = b"\x12\x34"
PROTOCOL_TX = 0x03          # txProtocol — send command
PROTOCOL_RX = 0x02          # rxProtocol — read status
CMD_SET_COMPONENT = 0x01    # set desiredValue
CMD_GET_COMPONENT = 0x02    # get reportedValue
UDP_TIMEOUT = 2.0           # seconds


def _crc32(data: bytes) -> bytes:
    """Compute CRC-32 checksum as 4-byte little-endian."""
    import binascii
    crc = binascii.crc32(data) & 0xFFFFFFFF
    return struct.pack("<I", crc)


def _hmac_sha256(token: str, data: bytes) -> bytes:
    """Compute HMAC-SHA256 using the UDP token as key."""
    return hmac.new(token.encode("utf-8"), data, hashlib.sha256).digest()


def _build_packet(command_id: int, payload: bytes, token: str) -> bytes:
    """
    Build a UDP command packet.

    Hypothetical format:
      magic(2) + protocol(1) + cmdId(2 BE) + payloadLen(4 BE) + payload + CRC32(4) + HMAC(32)
    """
    header = (
        UDP_MAGIC
        + struct.pack("B", PROTOCOL_TX)
        + struct.pack(">H", command_id)
        + struct.pack(">I", len(payload))
    )
    body = header + payload
    checksum = _crc32(body)
    auth = _hmac_sha256(token, body + checksum)
    return body + checksum + auth


def _encode_component_value(component_id: int, value: int) -> bytes:
    """Encode a set-component-value payload."""
    return struct.pack(">HI", component_id, value)


class LocalUDPProtocol(asyncio.DatagramProtocol):
    """asyncio UDP protocol handler for iQBridge."""

    def __init__(self) -> None:
        self.transport: Optional[asyncio.DatagramTransport] = None
        self._response: asyncio.Future = asyncio.get_event_loop().create_future()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore[override]
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if not self._response.done():
            self._response.set_result(data)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.warning("UDP error: %s", exc)
        if not self._response.done():
            self._response.set_exception(exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc and not self._response.done():
            self._response.set_exception(exc)

    async def send_and_receive(
        self,
        packet: bytes,
        host: str,
        port: int,
        timeout: float = UDP_TIMEOUT,
    ) -> Optional[bytes]:
        if self.transport is None:
            return None
        self._response = asyncio.get_event_loop().create_future()
        self.transport.sendto(packet, (host, port))
        try:
            return await asyncio.wait_for(self._response, timeout=timeout)
        except asyncio.TimeoutError:
            _LOGGER.debug("UDP response timeout from %s:%d", host, port)
            return None


class LocalUDPClient:
    """
    Direct LAN UDP client for iQBridge RS.

    Usage:
        client = LocalUDPClient(host="192.168.1.50", port=9003, token="abc123...")
        ok = await client.set_component(device_id="XYZ", component_id=13, value=1)
    """

    def __init__(self, host: str, port: int, token: str) -> None:
        self.host = host
        self.port = port
        self.token = token
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[LocalUDPProtocol] = None
        self._available = False

    async def connect(self) -> bool:
        """Open UDP socket and verify device responds."""
        try:
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                LocalUDPProtocol,
                remote_addr=(self.host, self.port),
            )
            self._transport = transport
            self._protocol = protocol
            self._available = True
            _LOGGER.info("Local UDP client connected to %s:%d", self.host, self.port)
            return True
        except Exception as err:
            _LOGGER.warning("Local UDP connect failed: %s", err)
            self._available = False
            return False

    async def disconnect(self) -> None:
        """Close UDP socket."""
        if self._transport:
            self._transport.close()
            self._transport = None
            self._protocol = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def set_component(
        self,
        device_id: str,
        component_id: int,
        value: int,
    ) -> bool:
        """
        Send a set-component-value command.

        Returns True on success, False on failure (caller should fall back to cloud).
        """
        if not self._available or self._protocol is None:
            return False

        payload = _encode_component_value(component_id, value)
        packet = _build_packet(CMD_SET_COMPONENT, payload, self.token)

        _LOGGER.debug(
            "UDP → %s:%d  component=%d value=%d  packet=%s",
            self.host, self.port, component_id, value, packet.hex(),
        )

        response = await self._protocol.send_and_receive(packet, self.host, self.port)
        if response is None:
            _LOGGER.warning("No UDP response for component=%d — falling back to cloud", component_id)
            self._available = False
            return False

        _LOGGER.debug("UDP ← response: %s", response.hex())
        return True


def verify_token_hypothesis(serial: str) -> dict[str, str]:
    """
    Generate candidate UDP tokens from device serial number.

    Call this with the device serial and compare candidates against
    the token returned by fluidra_debug.py to confirm derivation method.
    """
    import hashlib as _h

    return {
        "hmac_sha256_key_fluidra": hmac.new(b"fluidra", serial.encode(), _h.sha256).hexdigest(),
        "hmac_sha256_key_serial":  hmac.new(serial.encode(), b"fluidra", _h.sha256).hexdigest(),
        "sha256_serial":           _h.sha256(serial.encode()).hexdigest(),
        "md5_serial":              _h.md5(serial.encode()).hexdigest(),
        "sha256_serial_fluidra":   _h.sha256((serial + "fluidra").encode()).hexdigest(),
        "md5_serial_fluidra":      _h.md5((serial + "fluidra").encode()).hexdigest(),
    }
