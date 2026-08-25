"""
CSI packet parser and validation module.
Parses the raw binary datagrams sent by the ESP32-CAM firmware into structured format.
Tracks packet gaps per transmitter MAC to estimate network packet loss.
"""

import logging
import struct
import threading
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("wifisense.parser")

# Binary format mirroring the C csi_packet_t struct:
# <  : Little endian
# I  : seq_no (uint32_t)
# Q  : timestamp_us (uint64_t)
# 6s : mac (uint8_t[6])
# B  : rssi (uint8_t, representing int8_t)
# B  : channel (uint8_t)
# B  : bandwidth (uint8_t)
# H  : csi_len (uint16_t)
# 128b : csi_data (int8_t[128])
CSI_PACKET_FORMAT = "<IQ6sBBBH128b"
CSI_PACKET_SIZE = struct.calcsize(CSI_PACKET_FORMAT)


class PacketParser:
    """
    Parser for Wi-Fi CSI packets.
    Maintains internal thread-safe sequence tracking to identify packet loss.
    """

    def __init__(self):
        # Sequence number tracking: MAC string -> last received seq_no
        self._last_seq: Dict[str, int] = {}
        self._lock = threading.Lock()
        
        # Diagnostics
        self.gap_count = 0
        self.packet_count = 0

    def parse(self, raw_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parses a raw 151-byte packet into a dictionary.
        Returns None if packet is invalid or validation fails.
        """
        if len(raw_data) != CSI_PACKET_SIZE:
            logger.warning(
                f"Validation failed: Invalid packet length. Expected {CSI_PACKET_SIZE}, got {len(raw_data)}"
            )
            return None

        try:
            unpacked = struct.unpack(CSI_PACKET_FORMAT, raw_data)
        except struct.error as e:
            logger.warning(f"Struct unpacking failed: {e}")
            return None

        # Unpack fields
        seq_no = unpacked[0]
        timestamp_us = unpacked[1]
        mac_bytes = unpacked[2]
        rssi_raw = unpacked[3]
        channel = unpacked[4]
        bandwidth = unpacked[5]
        csi_len = unpacked[6]
        csi_data = list(unpacked[7:])

        # Convert MAC address to standard string representation
        mac_str = ":".join(f"{b:02x}" for b in mac_bytes)

        # Basic validations
        if not (1 <= channel <= 14):
            logger.warning(f"Validation failed: Invalid channel {channel}")
            return None

        if not (0 <= csi_len <= 64):
            logger.warning(f"Validation failed: Invalid csi_len {csi_len}")
            return None

        # Convert RSSI to signed int
        rssi = rssi_raw if rssi_raw < 128 else rssi_raw - 256

        # Check sequence number gaps (thread-safe)
        with self._lock:
            self.packet_count += 1
            if mac_str in self._last_seq:
                last_seq = self._last_seq[mac_str]
                # Account for sequence number wrap-around at 2^32 - 1
                expected_seq = (last_seq + 1) & 0xFFFFFFFF
                if seq_no != expected_seq:
                    gap = (seq_no - expected_seq) & 0xFFFFFFFF
                    self.gap_count += gap
                    logger.debug(
                        f"Packet gap detected for MAC {mac_str}: expected {expected_seq}, got {seq_no} (gap={gap})"
                    )
            self._last_seq[mac_str] = seq_no

        return {
            "seq_no": seq_no,
            "timestamp_us": timestamp_us,
            "mac": mac_str,
            "rssi": rssi,
            "channel": channel,
            "bandwidth": bandwidth,
            "csi_len": csi_len,
            "csi_data": csi_data,
            "raw_bytes": raw_data,
        }

    def get_metrics(self) -> Dict[str, int]:
        """
        Returns parser metrics.
        """
        with self._lock:
            return {
                "packet_count": self.packet_count,
                "gap_count": self.gap_count,
            }
