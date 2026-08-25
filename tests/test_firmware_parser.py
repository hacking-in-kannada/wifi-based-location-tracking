"""
Unit tests for the ESP32-CAM CSI binary packet parser.
Verifies that the Python struct format matches the C packed definition.
"""

import struct
import unittest

# Format string:
# <  : little-endian
# I  : seq_no (uint32_t)
# Q  : timestamp_us (uint64_t)
# 6s : mac (uint8_t[6])
# B  : rssi (uint8_t)
# B  : channel (uint8_t)
# B  : bandwidth (uint8_t)
# H  : csi_len (uint16_t)
# 128b : csi_data (int8_t[128])
CSI_PACKET_FORMAT = "<IQ6sBBBH128b"
CSI_PACKET_SIZE = struct.calcsize(CSI_PACKET_FORMAT)


def parse_csi_packet(data: bytes) -> dict:
    """
    Parses a raw binary buffer into a structured packet dictionary.
    Raises ValueError if size is incorrect.
    """
    if len(data) != CSI_PACKET_SIZE:
        raise ValueError(
            f"Incorrect packet size. Expected {CSI_PACKET_SIZE} bytes, got {len(data)}"
        )

    unpacked = struct.unpack(CSI_PACKET_FORMAT, data)

    # Extract fields
    seq_no = unpacked[0]
    timestamp_us = unpacked[1]
    mac_bytes = unpacked[2]
    rssi = unpacked[3]
    channel = unpacked[4]
    bandwidth = unpacked[5]
    csi_len = unpacked[6]
    csi_data = list(unpacked[7:])

    # Convert MAC to human-readable string
    mac_str = ":".join(f"{b:02x}" for b in mac_bytes)

    # Convert RSSI to signed value if necessary (since rssi is uint8_t in struct but represents int8_t)
    rssi_signed = rssi if rssi < 128 else rssi - 256

    return {
        "seq_no": seq_no,
        "timestamp_us": timestamp_us,
        "mac": mac_str,
        "rssi": rssi_signed,
        "channel": channel,
        "bandwidth": bandwidth,
        "csi_len": csi_len,
        "csi_data": csi_data,
    }


class TestFirmwareParser(unittest.TestCase):
    def test_packet_size(self):
        """Verifies that the packet structure is exactly 151 bytes as designed."""
        self.assertEqual(CSI_PACKET_SIZE, 151)

    def test_pack_and_unpack_valid(self):
        """Tests packing a mock CSI packet and successfully unpacking it."""
        mock_seq_no = 42
        mock_timestamp = 10002000
        mock_mac = b"\x24\x0a\xc4\x00\x11\x22"  # 24:0a:c4:00:11:22
        mock_rssi = 206  # uint8 representation of -50 (256 - 50 = 206)
        mock_channel = 6
        mock_bandwidth = 0  # 20MHz
        mock_csi_len = 64  # 64 pairs
        mock_csi_data = [i for i in range(64)] + [-i for i in range(64)]

        # Pack the binary data
        packed_data = struct.pack(
            CSI_PACKET_FORMAT,
            mock_seq_no,
            mock_timestamp,
            mock_mac,
            mock_rssi,
            mock_channel,
            mock_bandwidth,
            mock_csi_len,
            *mock_csi_data,
        )

        self.assertEqual(len(packed_data), 151)

        # Parse/Unpack
        parsed = parse_csi_packet(packed_data)

        self.assertEqual(parsed["seq_no"], mock_seq_no)
        self.assertEqual(parsed["timestamp_us"], mock_timestamp)
        self.assertEqual(parsed["mac"], "24:0a:c4:00:11:22")
        self.assertEqual(parsed["rssi"], -50)
        self.assertEqual(parsed["channel"], mock_channel)
        self.assertEqual(parsed["bandwidth"], mock_bandwidth)
        self.assertEqual(parsed["csi_len"], mock_csi_len)
        self.assertEqual(parsed["csi_data"], mock_csi_data)

    def test_invalid_packet_size(self):
        """Verifies that parsing raises a ValueError on truncated packets."""
        short_data = b"\x00" * 150
        with self.assertRaises(ValueError):
            parse_csi_packet(short_data)


if __name__ == "__main__":
    unittest.main()
