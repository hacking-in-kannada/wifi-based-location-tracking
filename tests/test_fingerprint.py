"""
Integration tests for the CSI Fingerprint collection database and manager.
Tests room creation, blueprint uploads, position marking, capture averaging, and import/export flows.
"""

import json
import os
import shutil
import tempfile
import unittest
from PIL import Image

from database.db import init_db, get_session, close_db
from database.models import Base, Room, Blueprint, Position, Fingerprint, FingerprintSample
from fingerprint_database.fingerprint_manager import FingerprintManager
from tests.synthetic_udp_sender import generate_mock_packet
from python_receiver.packet_parser import PacketParser


class TestFingerprintCollection(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for database and uploads
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_wifisense.db")
        self.upload_dir = os.path.join(self.temp_dir.name, "blueprints")
        
        # Initialize test database
        init_db(f"sqlite:///{self.db_path}")

        # Create a mock blueprint image
        self.mock_image_path = os.path.join(self.temp_dir.name, "blueprint.png")
        img = Image.new("RGB", (800, 600), color="white")
        img.save(self.mock_image_path)

        # Initialize packet parser to create mock packets
        self.parser = PacketParser()
        self.mock_packets = []
        # Generate 100 mock packets (approx 2s of data at 50Hz)
        for i in range(100):
            raw_pkt = generate_mock_packet(i)
            parsed = self.parser.parse(raw_pkt)
            self.mock_packets.append(parsed)

    def tearDown(self):
        close_db()
        self.temp_dir.cleanup()

    def test_end_to_end_fingerprint_flow(self):
        """
        Covers the complete Phase 5 Definition of Done:
        1. Upload a blueprint image.
        2. Record 3 positions with 2 samples each.
        3. Confirm averaged fingerprints exist and are calculated correctly.
        4. Confirm export/import produces an identical structure.
        """
        # 1. Create Room
        room = FingerprintManager.create_room("Training Lab")
        self.assertEqual(room.name, "Training Lab")

        # 2. Save Blueprint
        blueprint = FingerprintManager.save_blueprint(
            room_id=room.id,
            image_path=self.mock_image_path,
            upload_dir=self.upload_dir
        )
        self.assertEqual(blueprint.width_px, 800)
        self.assertEqual(blueprint.height_px, 600)
        self.assertTrue(os.path.exists(blueprint.file_path))

        # 3. Create 3 Positions
        pos1 = FingerprintManager.create_position(room.id, "Zone Alpha", 150, 200)
        pos2 = FingerprintManager.create_position(room.id, "Zone Beta", 400, 300)
        pos3 = FingerprintManager.create_position(room.id, "Zone Gamma", 650, 450)

        # 4. Record 2 samples for each position
        # Sample capture 1 & 2 for Alpha
        samples_a1 = FingerprintManager.capture_fingerprint(room.id, pos1.id, self.mock_packets, sample_rate_hz=50.0)
        samples_a2 = FingerprintManager.capture_fingerprint(room.id, pos1.id, self.mock_packets, sample_rate_hz=50.0)
        
        # Sample capture 1 & 2 for Beta
        FingerprintManager.capture_fingerprint(room.id, pos2.id, self.mock_packets, sample_rate_hz=50.0)
        FingerprintManager.capture_fingerprint(room.id, pos2.id, self.mock_packets, sample_rate_hz=50.0)

        # Sample capture 1 & 2 for Gamma
        FingerprintManager.capture_fingerprint(room.id, pos3.id, self.mock_packets, sample_rate_hz=50.0)
        FingerprintManager.capture_fingerprint(room.id, pos3.id, self.mock_packets, sample_rate_hz=50.0)

        # 5. Verify database records
        session = get_session()
        try:
            # Verify Positions exist
            positions = session.query(Position).filter_by(room_id=room.id).all()
            self.assertEqual(len(positions), 3)

            # Verify samples are captured
            # Since each capture window of 100 packets (2s) at 50Hz with 1s window (50 packets) and 50% overlap (25 packets step)
            # gives (100 - 50)//25 + 1 = 3 sliding windows, each capture generates 3 samples.
            # 2 captures * 3 samples = 6 samples per position.
            samples_count = session.query(FingerprintSample).filter_by(position_id=pos1.id).count()
            self.assertEqual(samples_count, 6)

            # Verify Averaged Fingerprints are materialized
            fps = session.query(Fingerprint).filter_by(room_id=room.id).all()
            self.assertEqual(len(fps), 3)

            for fp in fps:
                self.assertEqual(fp.sample_count, 6)
                # Verify feature vector JSON has content
                feat_dict = json.loads(fp.feature_vector_json)
                self.assertIn("agg_mean", feat_dict)
                self.assertIn("mean_sc_0", feat_dict)
        finally:
            session.close()

        # 6. Export Dataset
        exported_json = FingerprintManager.export_dataset()
        data = json.loads(exported_json)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["room_name"], "Training Lab")
        self.assertEqual(len(data[0]["positions"]), 3)

        # 7. Clear Database tables to test import integrity
        session = get_session()
        try:
            session.query(FingerprintSample).delete()
            session.query(Fingerprint).delete()
            session.query(Position).delete()
            session.query(Blueprint).delete()
            session.query(Room).delete()
            session.commit()

            self.assertEqual(session.query(Room).count(), 0)
            self.assertEqual(session.query(Position).count(), 0)
            self.assertEqual(session.query(Fingerprint).count(), 0)
        finally:
            session.close()

        # 8. Import Dataset
        FingerprintManager.import_dataset(exported_json)

        # 9. Verify restored records
        session = get_session()
        try:
            self.assertEqual(session.query(Room).count(), 1)
            self.assertEqual(session.query(Blueprint).count(), 1)
            self.assertEqual(session.query(Position).count(), 3)
            self.assertEqual(session.query(Fingerprint).count(), 3)
            self.assertEqual(session.query(FingerprintSample).count(), 18)

            restored_room = session.query(Room).first()
            self.assertEqual(restored_room.name, "Training Lab")
            
            restored_fp = session.query(Fingerprint).filter_by(room_id=restored_room.id).first()
            self.assertEqual(restored_fp.sample_count, 6)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
