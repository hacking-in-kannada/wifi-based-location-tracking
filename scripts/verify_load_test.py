"""
Script to execute the 60-second load test at 200 Hz.
Measures queue health, drop rates, and database insertion speed.
"""

import os
import sqlite3
import sys
import threading
import time
import yaml

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from python_receiver.udp_server import CSIPacketReceiver
from tests.synthetic_udp_sender import run_sender
from database.db import close_db


def main():
    config_path = "python_receiver/config.yaml"
    db_path = "database/wifisense.db"
    
    # Clean up previous db
    if os.path.exists(db_path):
        os.remove(db_path)

    # Initialize receiver
    receiver = CSIPacketReceiver(config_path)
    receiver.start()

    target_rate = 200.0
    duration = 60.0
    expected_total = int(target_rate * duration)

    print(f"Starting 60s Load Test: pushing {expected_total} packets...")
    
    # Monitor thread to periodically print queue size
    def monitor_queue():
        while receiver.running:
            time.sleep(5)
            qsize = receiver.recv_queue.qsize()
            print(f"   [Monitor] Queue Size: {qsize} | Processed: {receiver.processed_packets} | Dropped: {receiver.dropped_packets}")

    monitor_thread = threading.Thread(target=monitor_queue, daemon=True)
    monitor_thread.start()

    # Run synthetic sender
    run_sender("127.0.0.1", 5566, target_rate, duration)

    # Give receiver a moment to flush remaining packets
    print("Waiting for receiver to flush remaining packets...")
    time.sleep(3.0)

    # Stop receiver
    receiver.stop()
    close_db()

    # Read final row count from database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM csi_packets")
    db_count = cursor.fetchone()[0]
    conn.close()

    processed = receiver.processed_packets
    dropped = receiver.dropped_packets
    total_received = processed + dropped
    drop_rate = (dropped / total_received * 100.0) if total_received > 0 else 0.0

    print("\n================ LOAD TEST RESULTS ================")
    print(f"Expected Sent:      {expected_total}")
    print(f"Total Processed:    {processed}")
    print(f"Total Dropped:      {dropped}")
    print(f"Drop Rate:          {drop_rate:.4f}%")
    print(f"SQLite Row Count:   {db_count}")
    print("===================================================\n")

    if drop_rate >= 1.0:
        print("FAIL: Drop rate is >= 1%!")
        sys.exit(1)
    if db_count != processed:
        print("FAIL: SQLite row count does not match processed count!")
        sys.exit(1)
    if db_count < expected_total * 0.9:
        print("FAIL: Received less than 90% of expected packets!")
        sys.exit(1)
        
    print("SUCCESS: 60-second load test completed successfully under limits!")


if __name__ == "__main__":
    main()
