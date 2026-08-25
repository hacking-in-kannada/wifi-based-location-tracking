"""
Integration and load tests for the Python UDP CSI receiver.
"""

import os
import queue
import sqlite3
import tempfile
import threading
import time
import unittest
import yaml

from python_receiver.udp_server import CSIPacketReceiver
from tests.synthetic_udp_sender import run_sender
from database.db import close_db


class TestReceiverLoad(unittest.TestCase):
    def setUp(self):
        # Create a temporary config file and SQLite DB path
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_wifisense.db")
        self.config_path = os.path.join(self.temp_dir.name, "test_config.yaml")

        test_config = {
            "server": {
                "host": "127.0.0.1",
                "port": 15566,  # Alternate port to avoid conflicts
                "control_port": 15567,
            },
            "pipeline": {
                "worker_threads": 4,
                "max_queue_size": 10000,
                "flush_interval_ms": 100,  # Flush faster for tests
                "batch_size": 100,
            },
            "buffer": {
                "window_seconds": 2,
                "expected_hz": 200,
            },
            "storage": {
                "backend": "sqlite",
                "sqlite": {
                    "db_url": f"sqlite:///{self.db_path}"
                }
            }
        }

        with open(self.config_path, "w") as f:
            yaml.dump(test_config, f)

    def tearDown(self):
        close_db()
        self.temp_dir.cleanup()

    def test_load_ingestion(self):
        """
        Runs a load test pushing 200 pkts/sec.
        Verifies that:
        1. Queue size remains bounded.
        2. Drop rate is < 1%.
        3. DB record count matches expected packet count minus drops.
        """
        receiver = CSIPacketReceiver(self.config_path)
        receiver.start()

        # Target rate: 200 Hz
        # Duration: 5 seconds for fast unit test execution.
        # Note: We can also run a 60-second test from command line.
        target_rate = 200.0
        duration = 5.0
        expected_total = int(target_rate * duration)

        # Run synthetic sender in a separate thread
        sender_thread = threading.Thread(
            target=run_sender,
            args=("127.0.0.1", 15566, target_rate, duration),
            name="TestSenderThread"
        )
        sender_thread.start()
        sender_thread.join()

        # Give receiver a moment to flush remaining packets
        time.sleep(2.0)
        
        # Stop receiver
        receiver.stop()

        # Metrics verification
        processed = receiver.processed_packets
        dropped = receiver.dropped_packets
        queue_size = receiver.recv_queue.qsize()

        print(f"\n--- Load Test Metrics ---")
        print(f"Expected Sent: {expected_total}")
        print(f"Processed by Receiver: {processed}")
        print(f"Dropped by Receiver: {dropped}")
        print(f"Final Ingestion Queue Size: {queue_size}")

        # Assertions
        # 1. Queue depth remains bounded and is empty at the end
        self.assertEqual(queue_size, 0, "Queue did not empty after completion.")
        
        # 2. Drop rate is < 1%
        total_received = processed + dropped
        self.assertGreater(total_received, 0, "No packets were received.")
        drop_rate = dropped / total_received
        print(f"Drop Rate: {drop_rate * 100:.2f}%")
        self.assertLess(drop_rate, 0.01, f"Drop rate was {drop_rate * 100:.2f}%, which is >= 1%")

        # 3. SQLite database row verification
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM csi_packets")
        db_count = cursor.fetchone()[0]
        conn.close()

        print(f"DB Row Count: {db_count}")
        print(f"-------------------------\n")

        self.assertEqual(db_count, processed, "Database row count does not match processed count.")
        self.assertGreaterEqual(db_count, expected_total * 0.8, "Received far fewer packets than expected.")


if __name__ == "__main__":
    unittest.main()
