"""
Fingerprint Database Manager.
Handles saving blueprints, creating positions, capturing RSSI fingerprints,
calculating averaged fingerprints, and exporting/importing datasets.
"""

import datetime
import json
import os
from typing import Dict, Any, List, Optional
from PIL import Image
import numpy as np

from database.db import get_session
from database.models import Room, Blueprint, Position, Fingerprint, FingerprintSample


def extract_rssi_features(rssi_values: List[int]) -> Dict[str, float]:
    """
    Extracts statistical features from a list of RSSI readings (dBm).
    Returns a compact 7-feature dictionary suitable for ML classification.
    """
    arr = np.array(rssi_values, dtype=np.float64)
    if len(arr) == 0:
        return {}
    return {
        "rssi_mean": float(np.mean(arr)),
        "rssi_std": float(np.std(arr)),
        "rssi_min": float(np.min(arr)),
        "rssi_max": float(np.max(arr)),
        "rssi_median": float(np.median(arr)),
        "rssi_range": float(np.max(arr) - np.min(arr)),
        "rssi_variance": float(np.var(arr)),
    }


class FingerprintManager:
    """
    Coordinates fingerprint database updates, capture pipelines,
    and dataset imports/exports.
    """

    @staticmethod
    def create_room(name: str) -> Room:
        session = get_session()
        try:
            room = Room(name=name)
            session.add(room)
            session.commit()
            session.refresh(room)
            return room
        finally:
            session.close()

    @staticmethod
    def save_blueprint(room_id: int, image_path: str, upload_dir: str = "assets/blueprints") -> Blueprint:
        """
        Saves a blueprint image file on disk, reads dimensions, and inserts database record.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source blueprint image not found: {image_path}")

        # Ensure directory structure
        room_blueprint_dir = os.path.join(upload_dir, str(room_id))
        os.makedirs(room_blueprint_dir, exist_ok=True)

        filename = os.path.basename(image_path)
        dest_path = os.path.join(room_blueprint_dir, filename)

        # Copy file
        import shutil
        shutil.copy2(image_path, dest_path)

        # Read dimensions
        with Image.open(dest_path) as img:
            width, height = img.size

        session = get_session()
        try:
            # Check if blueprint already exists for this room
            blueprint = session.query(Blueprint).filter_by(room_id=room_id).first()
            if blueprint:
                blueprint.file_path = dest_path
                blueprint.width_px = width
                blueprint.height_px = height
                blueprint.uploaded_at = datetime.datetime.utcnow()
            else:
                blueprint = Blueprint(
                    room_id=room_id,
                    file_path=dest_path,
                    width_px=width,
                    height_px=height
                )
                session.add(blueprint)
            session.commit()
            session.refresh(blueprint)
            return blueprint
        finally:
            session.close()

    @staticmethod
    def create_position(room_id: int, label: str, x: int, y: int) -> Position:
        """
        Creates a position/zone coordinates mapping.
        """
        session = get_session()
        try:
            pos = Position(room_id=room_id, label=label, blueprint_x=x, blueprint_y=y)
            session.add(pos)
            session.commit()
            session.refresh(pos)
            return pos
        finally:
            session.close()

    @staticmethod
    def delete_position(position_id: int):
        """
        Deletes a position/zone coordinates mapping.
        """
        session = get_session()
        try:
            pos = session.query(Position).filter_by(id=position_id).first()
            if pos:
                session.delete(pos)
                session.commit()
        finally:
            session.close()

    @staticmethod
    def capture_fingerprint(
        room_id: int,
        position_id: int,
        packets: List[Dict[str, Any]],
        sample_rate_hz: float = 50.0
    ) -> List[int]:
        """
        Extracts full CSI features from packets and saves samples.
        Uses sliding windows of CSI values to create multiple feature samples.
        """
        if not packets:
            raise ValueError("No packets provided for fingerprint capture")

        from feature_extraction.features import extract_window_features

        # 1. Extract CSI data from all packets
        csi_list = []
        timestamps = []
        for p in packets:
            if "csi_data" in p:
                csi_list.append(p["csi_data"])
                timestamps.append(p.get("timestamp_us", 0) / 1e6)

        if not csi_list:
            raise ValueError("No CSI data found in packets")

        csi_matrix = np.array(csi_list)

        # 2. Slide windows over CSI data to create multiple samples
        # Window = 1 second of data, 50% overlap
        window_size = max(5, int(sample_rate_hz))  # At least 5 readings per window
        step_size = max(1, window_size // 2)

        session = get_session()
        sample_ids = []
        try:
            n_readings = len(csi_list)
            for start_idx in range(0, n_readings - window_size + 1, step_size):
                end_idx = start_idx + window_size
                window_csi = csi_matrix[start_idx:end_idx]
                t_start = timestamps[start_idx]
                t_end = timestamps[end_idx-1]

                # Extract CSI features for this window
                feat_vector = extract_window_features(window_csi, t_start, t_end, sample_rate_hz)
                if not feat_vector.features_dict:
                    continue

                sample = FingerprintSample(
                    position_id=position_id,
                    feature_vector_json=json.dumps(feat_vector.features_dict)
                )
                session.add(sample)
                session.flush()
                sample_ids.append(sample.id)

            # If not enough data for sliding windows, save one sample from all data
            if not sample_ids and n_readings > 1:
                t_start = timestamps[0]
                t_end = timestamps[-1]
                feat_vector = extract_window_features(csi_matrix, t_start, t_end, sample_rate_hz)
                if feat_vector.features_dict:
                    sample = FingerprintSample(
                        position_id=position_id,
                        feature_vector_json=json.dumps(feat_vector.features_dict)
                    )
                    session.add(sample)
                    session.flush()
                    sample_ids.append(sample.id)

            session.commit()

            # 3. Recompute the averaged fingerprint
            FingerprintManager._recalculate_average(session, room_id, position_id)
            return sample_ids
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def _recalculate_average(session, room_id: int, position_id: int):
        """
        Helper to compute the mean feature vector from all samples and save/update the fingerprint.
        """
        samples = session.query(FingerprintSample).filter_by(position_id=position_id).all()
        if not samples:
            session.query(Fingerprint).filter_by(position_id=position_id).delete()
            session.commit()
            return

        # Parse feature vectors
        feature_dicts = [json.loads(s.feature_vector_json) for s in samples]
        keys = feature_dicts[0].keys()
        
        # Calculate mean features
        mean_features = {}
        for k in keys:
            mean_features[k] = float(np.mean([fd[k] for fd in feature_dicts]))

        fingerprint = session.query(Fingerprint).filter_by(position_id=position_id).first()
        if not fingerprint:
            fingerprint = Fingerprint(
                room_id=room_id,
                position_id=position_id,
                feature_vector_json=json.dumps(mean_features),
                sample_count=len(samples),
                created_at=datetime.datetime.utcnow(),
                updated_at=datetime.datetime.utcnow(),
            )
            session.add(fingerprint)
        else:
            fingerprint.feature_vector_json = json.dumps(mean_features)
            fingerprint.sample_count = len(samples)
            fingerprint.updated_at = datetime.datetime.utcnow()
            
        session.commit()

    @staticmethod
    def delete_position(position_id: int):
        """
        Deletes a position and all associated fingerprints and samples.
        """
        session = get_session()
        try:
            session.query(FingerprintSample).filter_by(position_id=position_id).delete()
            session.query(Fingerprint).filter_by(position_id=position_id).delete()
            pos = session.query(Position).filter_by(id=position_id).first()
            if pos:
                session.delete(pos)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def delete_room(room_id: int):
        """
        Deletes a room and all child positions, fingerprints, samples, and blueprints.
        """
        session = get_session()
        try:
            positions = session.query(Position).filter_by(room_id=room_id).all()
            for p in positions:
                session.query(FingerprintSample).filter_by(position_id=p.id).delete()
                session.query(Fingerprint).filter_by(position_id=p.id).delete()
                session.delete(p)

            session.query(Fingerprint).filter_by(room_id=room_id).delete()
            session.query(Blueprint).filter_by(room_id=room_id).delete()
            room = session.query(Room).filter_by(id=room_id).first()
            if room:
                session.delete(room)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def export_dataset() -> str:
        """
        Serializes all rooms, blueprints, positions, and fingerprints into a single JSON string.
        """
        session = get_session()
        try:
            rooms = session.query(Room).all()
            export_data = []

            for r in rooms:
                blueprint = session.query(Blueprint).filter_by(room_id=r.id).first()
                bp_data = {
                    "file_path": blueprint.file_path,
                    "width_px": blueprint.width_px,
                    "height_px": blueprint.height_px,
                } if blueprint else None

                positions_data = []
                positions = session.query(Position).filter_by(room_id=r.id).all()
                for p in positions:
                    fp = session.query(Fingerprint).filter_by(position_id=p.id).first()
                    samples = session.query(FingerprintSample).filter_by(position_id=p.id).all()
                    
                    positions_data.append({
                        "id": p.id,
                        "label": p.label,
                        "blueprint_x": p.blueprint_x,
                        "blueprint_y": p.blueprint_y,
                        "image_path": p.image_path,
                        "fingerprint": {
                            "feature_vector_json": fp.feature_vector_json,
                            "sample_count": fp.sample_count
                        } if fp else None,
                        "samples": [json.loads(s.feature_vector_json) for s in samples]
                    })

                export_data.append({
                    "room_name": r.name,
                    "blueprint": bp_data,
                    "positions": positions_data
                })

            return json.dumps(export_data, indent=2)
        finally:
            session.close()

    @staticmethod
    def import_dataset(json_str: str):
        """
        Imports rooms, blueprints, positions, and fingerprints from a JSON string.
        """
        data = json.loads(json_str)
        session = get_session()
        try:
            for item in data:
                # 1. Create Room
                room = Room(name=item["room_name"])
                session.add(room)
                session.commit()

                # 2. Create Blueprint if present
                bp = item["blueprint"]
                if bp:
                    blueprint = Blueprint(
                        room_id=room.id,
                        file_path=bp["file_path"],
                        width_px=bp["width_px"],
                        height_px=bp["height_px"]
                    )
                    session.add(blueprint)
                    session.commit()

                # 3. Create Positions and Fingerprints
                for pos_item in item["positions"]:
                    pos = Position(
                        room_id=room.id,
                        label=pos_item["label"],
                        blueprint_x=pos_item["blueprint_x"],
                        blueprint_y=pos_item["blueprint_y"],
                        image_path=pos_item.get("image_path")
                    )
                    session.add(pos)
                    session.commit()

                    # Re-create samples
                    for s_feat in pos_item["samples"]:
                        sample = FingerprintSample(
                            position_id=pos.id,
                            feature_vector_json=json.dumps(s_feat)
                        )
                        session.add(sample)
                    session.commit()

                    # Import or recalculate average
                    fp_item = pos_item["fingerprint"]
                    if fp_item:
                        fp = Fingerprint(
                            room_id=room.id,
                            position_id=pos.id,
                            feature_vector_json=fp_item["feature_vector_json"],
                            sample_count=fp_item["sample_count"]
                        )
                        session.add(fp)
                    else:
                        FingerprintManager._recalculate_average(session, room.id, pos.id)
                    session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    @staticmethod
    def reset_database():
        """
        Deletes all rooms, blueprints, positions, fingerprints, samples, and CSI packets.
        Clears associated image asset folders.
        """
        import shutil
        from database.db import reset_all_tables
        reset_all_tables()

        for sub in ["blueprints", "positions"]:
            path = os.path.join("assets", sub)
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)
                os.makedirs(path, exist_ok=True)


