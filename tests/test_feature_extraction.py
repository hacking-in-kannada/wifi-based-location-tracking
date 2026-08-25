"""
Unit and snapshot tests for CSI feature extraction.
"""

import json
import os
import unittest
import numpy as np

from feature_extraction.features import extract_window_features, FeatureVector
from feature_extraction.export import export_to_csv, export_to_parquet


class TestFeatureExtraction(unittest.TestCase):
    def setUp(self):
        # Create a deterministic synthetic CSI window: 50 packets, 4 subcarriers
        np.random.seed(42)
        n_packets = 50
        n_subcarriers = 4
        self.sample_rate = 50.0
        
        t = np.linspace(0, 1.0, n_packets)[:, np.newaxis]
        # Introduce distinct behaviors per subcarrier
        sc0 = 5.0 + 2.0 * np.sin(2 * np.pi * 5 * t)  # 5 Hz sine wave
        sc1 = 3.0 + np.random.normal(0, 0.1, size=(n_packets, 1))  # quiet noise
        sc2 = 1.0 + 5.0 * t  # linear ramp
        sc3 = np.zeros((n_packets, 1))  # static flat zero
        
        self.csi_window = np.hstack([sc0, sc1, sc2, sc3])
        self.timestamp_start = 100.0
        self.timestamp_end = 101.0

        # Output folder for exports during tests
        self.test_output_dir = "tests/test_outputs"
        os.makedirs(self.test_output_dir, exist_ok=True)

    def tearDown(self):
        # Clean up test outputs
        for filename in ["test_features.csv", "test_features.parquet"]:
            path = os.path.join(self.test_output_dir, filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        if os.path.exists(self.test_output_dir):
            try:
                os.rmdir(self.test_output_dir)
            except OSError:
                pass

    def test_feature_determinism(self):
        """Verifies feature extraction output is identical across identical inputs."""
        feat1 = extract_window_features(
            self.csi_window, self.timestamp_start, self.timestamp_end, self.sample_rate
        )
        feat2 = extract_window_features(
            self.csi_window, self.timestamp_start, self.timestamp_end, self.sample_rate
        )
        self.assertEqual(feat1.timestamp_start, feat2.timestamp_start)
        self.assertEqual(feat1.timestamp_end, feat2.timestamp_end)
        self.assertEqual(feat1.features_dict.keys(), feat2.features_dict.keys())
        
        for k in feat1.features_dict:
            self.assertAlmostEqual(feat1.features_dict[k], feat2.features_dict[k], places=6)

    def test_feature_values(self):
        """Verifies mathematical validity of specific extracted features."""
        feat = extract_window_features(
            self.csi_window, self.timestamp_start, self.timestamp_end, self.sample_rate
        )
        fd = feat.features_dict

        # Subcarrier 3 is all zeros, mean/var should be 0
        self.assertAlmostEqual(fd["mean_sc_3"], 0.0)
        self.assertAlmostEqual(fd["var_sc_3"], 0.0)
        self.assertAlmostEqual(fd["autocorr_sc_3"], 0.0)

        # Subcarrier 0 has a 5 Hz sine wave
        self.assertGreater(fd["mean_sc_0"], 4.0)
        # Dominant frequency should be close to 5 Hz
        self.assertAlmostEqual(fd["dom_freq_sc_0"], 5.0, delta=1.5)

        # Verify aggregate values are averages of individual values
        expected_agg_mean = (fd["mean_sc_0"] + fd["mean_sc_1"] + fd["mean_sc_2"] + fd["mean_sc_3"]) / 4
        self.assertAlmostEqual(fd["agg_mean"], expected_agg_mean, places=6)

    def test_snapshot(self):
        """
        Snapshot test to guard against schema and calculation drift.
        Compares results with a golden snapshot file.
        """
        feat = extract_window_features(
            self.csi_window, self.timestamp_start, self.timestamp_end, self.sample_rate
        )
        
        snapshot_path = "tests/feature_snapshot_v1.json"
        
        current_snapshot = {
            "timestamp_start": feat.timestamp_start,
            "timestamp_end": feat.timestamp_end,
            "features": feat.features_dict
        }

        # If snapshot does not exist, write it (initial generation)
        if not os.path.exists(snapshot_path):
            with open(snapshot_path, "w") as f:
                json.dump(current_snapshot, f, indent=2)
            print(f"\n[Snapshot] Created golden snapshot at {snapshot_path}")
            return

        # Load golden snapshot
        with open(snapshot_path, "r") as f:
            golden_snapshot = json.load(f)

        # Assert key structure matches
        self.assertEqual(
            current_snapshot["features"].keys(),
            golden_snapshot["features"].keys(),
            "Feature schema drift detected!"
        )

        # Assert all values are close to golden values
        for k in current_snapshot["features"]:
            self.assertAlmostEqual(
                current_snapshot["features"][k],
                golden_snapshot["features"][k],
                places=5,
                msg=f"Value drift detected for key: {k}"
            )

    def test_exports(self):
        """Verifies exporting to CSV and Parquet completes without exceptions."""
        feat = extract_window_features(
            self.csi_window, self.timestamp_start, self.timestamp_end, self.sample_rate
        )
        vectors = [feat, feat]  # 2 rows
        
        csv_path = os.path.join(self.test_output_dir, "test_features.csv")
        parquet_path = os.path.join(self.test_output_dir, "test_features.parquet")

        # Export CSV
        export_to_csv(vectors, csv_path)
        self.assertTrue(os.path.exists(csv_path))
        self.assertGreater(os.path.getsize(csv_path), 0)

        # Export Parquet
        export_to_parquet(vectors, parquet_path)
        self.assertTrue(os.path.exists(parquet_path))
        self.assertGreater(os.path.getsize(parquet_path), 0)


if __name__ == "__main__":
    unittest.main()
