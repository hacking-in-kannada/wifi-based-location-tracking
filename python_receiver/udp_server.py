"""
Multi-threaded UDP Receiver Service for Wi-Fi CSI data.
Features a high-throughput ingestion queue, multiple parser workers,
an in-memory thread-safe sliding window ring buffer, and periodic bulk storage flushing.
"""

import collections
import logging
import os
import queue
import socket
import sys
import threading
import time
from typing import Dict, Any, List, Optional
import yaml

from python_receiver.packet_parser import PacketParser, CSI_PACKET_SIZE
from python_receiver.storage import get_storage_backend

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s - %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("wifisense.receiver")


class CSIPacketReceiver:
    """
    Core receiver that coordinates UDP sockets, ingestion queues,
    worker pools, memory buffers, and storage writers.
    """

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

        # Components
        self.parser = PacketParser()
        self.storage = get_storage_backend(self.config)

        # Queues
        self.max_queue_size = self.config["pipeline"].get("max_queue_size", 10000)
        self.recv_queue: queue.Queue = queue.Queue(maxsize=self.max_queue_size)
        self.persist_queue: queue.Queue = queue.Queue()

        # Ring Buffer (Sliding Window in Memory)
        window_sec = self.config["buffer"].get("window_seconds", 10)
        expected_hz = self.config["buffer"].get("expected_hz", 50)
        self.ring_buffer_maxlen = window_sec * expected_hz
        self.ring_buffer: collections.deque = collections.deque(maxlen=self.ring_buffer_maxlen)
        self.ring_buffer_lock = threading.Lock()

        # Threading state
        self.running = False
        self.threads: List[threading.Thread] = []

        # Socket details
        self.host = self.config["server"].get("host", "0.0.0.0")
        self.port = self.config["server"].get("port", 5566)
        self.ctrl_port = self.config["server"].get("control_port", 5567)

        # Stats
        self.dropped_packets = 0
        self.processed_packets = 0
        self.stats_lock = threading.Lock()

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r") as f:
            return yaml.safe_load(f)

    def get_window_data(self) -> List[Dict[str, Any]]:
        """
        Thread-safe method to retrieve a snapshot of all packets in the ring buffer.
        """
        with self.ring_buffer_lock:
            return list(self.ring_buffer)

    def _recv_loop(self):
        """
        Reads raw packets from UDP socket and places them onto the queue.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)  # 1MB buffer
        try:
            sock.bind((self.host, self.port))
            sock.settimeout(1.0)
            logger.info(f"CSI UDP Server listening on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to bind socket to {self.host}:{self.port}: {e}")
            self.running = False
            return

        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                try:
                    self.recv_queue.put((data, addr), block=False)
                except queue.Full:
                    with self.stats_lock:
                        self.dropped_packets += 1
                    logger.warning("Incoming queue full! Dropped packet.")
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error in recv socket: {e}")
                break

        sock.close()
        logger.info("Socket receiver thread stopped.")

    def _ctrl_loop(self):
        """
        Listens for control logs and events on UDP control port.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((self.host, self.ctrl_port))
            sock.settimeout(1.0)
            logger.info(f"Control UDP Server listening on {self.host}:{self.ctrl_port}")
        except Exception as e:
            logger.error(f"Failed to bind Control socket to {self.host}:{self.ctrl_port}: {e}")
            return

        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                message = data.decode("utf-8", errors="ignore").strip()
                logger.info(f"[FIRMWARE LOG] from {addr[0]}: {message}")
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error in control socket: {e}")
                break

        sock.close()
        logger.info("Control receiver thread stopped.")

    def _worker_loop(self):
        """
        Pops raw bytes from queue, parses, validates, and adds to ring buffer & storage queues.
        """
        while self.running or not self.recv_queue.empty():
            try:
                item = self.recv_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            raw_data, addr = item
            parsed = self.parser.parse(raw_data)
            
            if parsed is None:
                with self.stats_lock:
                    self.dropped_packets += 1
                self.recv_queue.task_done()
                continue

            # Add to thread-safe in-memory ring buffer
            with self.ring_buffer_lock:
                self.ring_buffer.append(parsed)

            # Queue for periodic persistence flush
            self.persist_queue.put(parsed)

            with self.stats_lock:
                self.processed_packets += 1

            self.recv_queue.task_done()

        logger.info("Worker thread stopped.")

    def _flush_loop(self):
        """
        Periodically flushes accumulated packets from persistence queue to storage.
        """
        flush_interval = self.config["pipeline"].get("flush_interval_ms", 1000) / 1000.0
        batch_size = self.config["pipeline"].get("batch_size", 500)

        while self.running or not self.persist_queue.empty():
            # Wait for the next flush interval
            time.sleep(flush_interval)

            batch = []
            while len(batch) < batch_size:
                try:
                    # Non-blocking fetch
                    packet = self.persist_queue.get_nowait()
                    batch.append(packet)
                    self.persist_queue.task_done()
                except queue.Empty:
                    break

            if batch:
                try:
                    self.storage.write_batch(batch)
                    logger.debug(f"Flushed batch of {len(batch)} packets to storage.")
                except Exception as e:
                    logger.error(f"Failed to write batch to storage: {e}")

        logger.info("Flush thread stopped.")

    def start(self):
        """
        Starts all threads in the service.
        """
        self.running = True

        # 1. Start Socket Recv Thread
        recv_thread = threading.Thread(target=self._recv_loop, name="RecvThread")
        recv_thread.daemon = True
        recv_thread.start()
        self.threads.append(recv_thread)

        # 2. Start Control Recv Thread
        ctrl_thread = threading.Thread(target=self._ctrl_loop, name="CtrlThread")
        ctrl_thread.daemon = True
        ctrl_thread.start()
        self.threads.append(ctrl_thread)

        # 3. Start Workers
        num_workers = self.config["pipeline"].get("worker_threads", 4)
        for i in range(num_workers):
            worker = threading.Thread(target=self._worker_loop, name=f"WorkerThread-{i}")
            worker.daemon = True
            worker.start()
            self.threads.append(worker)

        # 4. Start Flush Thread
        flush_thread = threading.Thread(target=self._flush_loop, name="FlushThread")
        flush_thread.daemon = True
        flush_thread.start()
        self.threads.append(flush_thread)

        logger.info("CSI Receiver service started completely.")

    def stop(self):
        """
        Stops all running threads and joins them.
        """
        logger.info("Stopping CSI Receiver service...")
        self.running = False

        for t in self.threads:
            t.join(timeout=2.0)

        logger.info("CSI Receiver service stopped.")


if __name__ == "__main__":
    # Standard standalone runner
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "config.yaml")
    
    receiver = CSIPacketReceiver(config_file)
    try:
        receiver.start()
        while True:
            time.sleep(1)
            metrics = receiver.parser.get_metrics()
            logger.info(
                f"Status - Queue size: {receiver.recv_queue.qsize()} | "
                f"Processed: {receiver.processed_packets} | "
                f"Dropped: {receiver.dropped_packets} | "
                f"Gaps (Packet Loss): {metrics['gap_count']}"
            )
    except KeyboardInterrupt:
        receiver.stop()
