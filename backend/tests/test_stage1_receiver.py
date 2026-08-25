from datetime import datetime, timezone

from python_receiver.receiver import CSIReceiver, InMemoryCSIBuffer
from python_receiver.schema import parse_csi_packet


def test_parse_csi_packet() -> None:
    packet = parse_csi_packet(
        b'{"timestamp":"2026-07-12T00:00:00Z","rssi":-41,"mac_address":"AA:BB:CC:DD:EE:FF","channel":6,"bandwidth_mhz":20,"amplitude":[0.1,0.2],"phase":[1.1,1.2]}'
    )

    assert packet.rssi == -41.0
    assert packet.channel == 6
    assert packet.amplitude == (0.1, 0.2)


def test_receiver_buffers_packets() -> None:
    buffer = InMemoryCSIBuffer()
    receiver = CSIReceiver(buffer=buffer)

    payload = b'{"timestamp":"2026-07-12T00:00:00Z","rssi":-40,"mac_address":"AA:BB:CC:DD:EE:FF","channel":11,"bandwidth_mhz":20,"amplitude":[0.3,0.4,0.5],"phase":[1.0,1.1,1.2]}'
    packet = receiver.handle_packet(payload)

    assert packet.timestamp == datetime(2026, 7, 12, tzinfo=timezone.utc)
    assert len(buffer.snapshot()) == 1
