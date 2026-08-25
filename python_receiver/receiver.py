from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from socket import AF_INET, SOCK_DGRAM, socket
from typing import Protocol

from python_receiver.schema import CSIPacket, parse_csi_packet


class PacketSink(Protocol):
    def append(self, packet: CSIPacket) -> None:
        ...


@dataclass
class InMemoryCSIBuffer:
    maxlen: int = 1024
    packets: deque[CSIPacket] = field(init=False)

    def __post_init__(self) -> None:
        self.packets = deque(maxlen=self.maxlen)

    def append(self, packet: CSIPacket) -> None:
        self.packets.append(packet)

    def snapshot(self) -> list[CSIPacket]:
        return list(self.packets)


@dataclass
class CSIReceiver:
    host: str = "0.0.0.0"
    port: int = 9000
    buffer: PacketSink = field(default_factory=InMemoryCSIBuffer)

    def handle_packet(self, payload: bytes) -> CSIPacket:
        packet = parse_csi_packet(payload)
        self.buffer.append(packet)
        return packet

    def serve_forever(self) -> None:
        with socket(AF_INET, SOCK_DGRAM) as udp_socket:
            udp_socket.bind((self.host, self.port))
            while True:
                payload, _ = udp_socket.recvfrom(65535)
                self.handle_packet(payload)
