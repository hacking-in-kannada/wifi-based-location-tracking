"""
Storage backends for parsed Wi-Fi CSI packets.
Supports SQLite, CSV, and JSONL (newline-delimited JSON) formats.
"""

import csv
import datetime
import json
import os
from typing import List, Dict, Any
from database.db import get_session, init_db
from database.models import CSIPacket


class CSVStorage:
    """
    Append-only CSV storage backend with daily rotation.
    """

    def __init__(self, directory: str):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)
        self.current_date = datetime.date.today()
        self.file_path = self._get_filepath(self.current_date)
        self._check_and_write_header()

    def _get_filepath(self, date: datetime.date) -> str:
        return os.path.join(self.directory, f"csi_packets_{date.strftime('%Y%m%d')}.csv")

    def _check_and_write_header(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, mode="w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp",
                        "seq_no",
                        "timestamp_us",
                        "mac",
                        "rssi",
                        "channel",
                        "bandwidth",
                        "csi_len",
                        "csi_data",
                    ]
                )

    def write_batch(self, packets: List[Dict[str, Any]]):
        if not packets:
            return

        # Check for rotation
        today = datetime.date.today()
        if today != self.current_date:
            self.current_date = today
            self.file_path = self._get_filepath(today)
            self._check_and_write_header()

        with open(self.file_path, mode="a", newline="") as f:
            writer = csv.writer(f)
            for p in packets:
                # Convert CSI data array to string representation to store in CSV cell
                csi_str = json.dumps(p["csi_data"])
                writer.writerow(
                    [
                        datetime.datetime.utcnow().isoformat(),
                        p["seq_no"],
                        p["timestamp_us"],
                        p["mac"],
                        p["rssi"],
                        p["channel"],
                        p["bandwidth"],
                        p["csi_len"],
                        csi_str,
                    ]
                )


class JSONLStorage:
    """
    Append-only JSONL (newline-delimited JSON) storage backend with daily rotation.
    """

    def __init__(self, directory: str):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)
        self.current_date = datetime.date.today()
        self.file_path = self._get_filepath(self.current_date)

    def _get_filepath(self, date: datetime.date) -> str:
        return os.path.join(self.directory, f"csi_packets_{date.strftime('%Y%m%d')}.jsonl")

    def write_batch(self, packets: List[Dict[str, Any]]):
        if not packets:
            return

        today = datetime.date.today()
        if today != self.current_date:
            self.current_date = today
            self.file_path = self._get_filepath(today)

        with open(self.file_path, mode="a") as f:
            for p in packets:
                row = {
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "seq_no": p["seq_no"],
                    "timestamp_us": p["timestamp_us"],
                    "mac": p["mac"],
                    "rssi": p["rssi"],
                    "channel": p["channel"],
                    "bandwidth": p["bandwidth"],
                    "csi_len": p["csi_len"],
                    "csi_data": p["csi_data"],
                }
                f.write(json.dumps(row) + "\n")


class SQLiteStorage:
    """
    SQLAlchemy-based SQLite storage backend using bulk inserts.
    """

    def __init__(self, db_url: str):
        init_db(db_url)

    def write_batch(self, packets: List[Dict[str, Any]]):
        if not packets:
            return

        session = get_session()
        try:
            db_packets = []
            for p in packets:
                # Store the csi_data array as a packed byte array (int8 bytes) in the database
                # since raw_blob is LargeBinary, we convert the int8 list to bytes
                raw_bytes = bytes(x & 0xFF for x in p["csi_data"])
                
                db_packets.append(
                    CSIPacket(
                        seq_no=p["seq_no"],
                        mac=p["mac"],
                        rssi=p["rssi"],
                        channel=p["channel"],
                        bandwidth=p["bandwidth"],
                        timestamp_us=p["timestamp_us"],
                        raw_blob=raw_bytes,
                    )
                )
            
            # Using bulk_save_objects is highly optimized in SQLAlchemy 2.0
            session.bulk_save_objects(db_packets)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


def get_storage_backend(config: Dict[str, Any]):
    """
    Factory function returning the configured storage backend.
    """
    storage_type = config.get("storage", {}).get("backend", "sqlite")
    if storage_type == "sqlite":
        db_url = config["storage"]["sqlite"]["db_url"]
        return SQLiteStorage(db_url)
    elif storage_type == "csv":
        directory = config["storage"]["csv"]["directory"]
        return CSVStorage(directory)
    elif storage_type == "jsonl":
        directory = config["storage"]["jsonl"]["directory"]
        return JSONLStorage(directory)
    else:
        raise ValueError(f"Unknown storage backend: {storage_type}")
