"""
Synthetic UDP packet sender for load testing the WiFiSense CSI receiver.
Simulates an ESP32-CAM capturing and transmitting packets at a fixed rate (default 200 Hz).
"""

import argparse
import socket
import struct
import time

CSI_PACKET_FORMAT = "<IQ6sBBBH128b"


def generate_mock_packet(seq_no: int) -> bytes:
    """
    Generates a raw 151-byte CSI packet matching the firmware binary struct.
    """
    timestamp_us = int(time.time() * 1_000_000)
    mac = b"\x24\x0a\xc4\x00\x11\x22"  # Mock ESP32 MAC
    rssi_signed = -55
    rssi = rssi_signed + 256 if rssi_signed < 0 else rssi_signed
    channel = 6
    bandwidth = 0  # 20MHz
    csi_len = 64  # 64 subcarriers (128 bytes raw)
    
    # Generate some mock CSI data (alternating sign)
    csi_data = [int((i % 10) * (-1 if i % 2 == 0 else 1)) for i in range(128)]

    return struct.pack(
        CSI_PACKET_FORMAT,
        seq_no,
        timestamp_us,
        mac,
        rssi,
        channel,
        bandwidth,
        csi_len,
        *csi_data,
    )


def run_sender(host: str, port: int, rate: float, duration: float):
    """
    Sends mock packets over UDP to target host and port.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / rate
    seq_no = 0
    start_time = time.time()
    
    print(f"Starting synthetic UDP CSI sender to {host}:{port}")
    print(f"Target Rate: {rate} Hz | Target Duration: {duration} s")

    while (time.time() - start_time) < duration:
        loop_start = time.time()
        packet = generate_mock_packet(seq_no)
        try:
            sock.sendto(packet, (host, port))
            seq_no += 1
        except Exception as e:
            print(f"Error sending packet: {e}")
            break

        # High-precision sleep
        elapsed = time.time() - loop_start
        sleep_time = interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    sock.close()
    print(f"Finished sending {seq_no} packets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WiFiSense Synthetic CSI Sender")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Target Host IP")
    parser.add_argument("--port", type=int, default=5566, help="Target CSI UDP Port")
    parser.add_argument("--rate", type=float, default=200.0, help="Packet transmission rate (Hz)")
    parser.add_argument("--duration", type=float, default=10.0, help="Sending duration (seconds)")

    args = parser.parse_args()
    run_sender(args.host, args.port, args.rate, args.duration)
