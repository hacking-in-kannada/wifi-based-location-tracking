"""
Unit tests for the motion detection state machine and relative trajectory tracker.
"""

import os
import tempfile
import unittest
import numpy as np

from database.db import init_db, close_db
from database.models import Event
from localization.motion import MotionDetector, MotionState


class TestMotionDetection(unittest.TestCase):
    def setUp(self):
        # Temp database setup for event logging
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_wifisense.db")
        init_db(f"sqlite:///{self.db_path}")

        # Initialize detector with default thresholds
        self.detector = MotionDetector(
            start_threshold=0.5,
            stop_threshold=0.2,
            history_size=5
        )

    def tearDown(self):
        close_db()
        self.temp_dir.cleanup()

    def _generate_window(self, variance: float) -> np.ndarray:
        """Helper to create a mock window of shape (100, 4) with a specific subcarrier variance."""
        # Standard deviation is sqrt(variance)
        std = np.sqrt(variance)
        # Create a quiet base (constant 1.0) and add noise
        clean = np.ones((100, 4))
        noise = np.random.normal(0, std, size=clean.shape)
        return clean + noise

    def test_state_machine_transitions(self):
        """
        DOD Verification: Feeds a quiet -> active -> quiet sequence 
        and asserts the detector triggers the exact expected transitions.
        """
        # 1. Start Quiet
        q_window = self._generate_window(variance=0.04)
        evt = self.detector.process_window(q_window)
        self.assertIsNone(evt, "Quiet window triggered transition from NO_MOTION")
        self.assertEqual(self.detector.state, MotionState.NO_MOTION)

        # 2. Transition: Active (exceeds start_threshold 0.5)
        active_window_1 = self._generate_window(variance=0.8)
        evt_started = self.detector.process_window(active_window_1)
        self.assertIsNotNone(evt_started, "Active window failed to trigger transition")
        self.assertEqual(evt_started.state, "MOTION_STARTED")
        self.assertEqual(self.detector.state, MotionState.MOTION_STARTED)

        # 3. Transition: Continuous Active (remains above stop_threshold 0.2)
        active_window_2 = self._generate_window(variance=0.7)
        evt_cont = self.detector.process_window(active_window_2)
        self.assertIsNotNone(evt_cont)
        self.assertEqual(evt_cont.state, "CONTINUOUS_MOTION")
        self.assertEqual(self.detector.state, MotionState.CONTINUOUS_MOTION)

        # 4. Stay in Continuous Active
        active_window_3 = self._generate_window(variance=0.6)
        evt_stay = self.detector.process_window(active_window_3)
        self.assertIsNone(evt_stay, "Quiet active window triggered transition prematurely")
        self.assertEqual(self.detector.state, MotionState.CONTINUOUS_MOTION)

        # 5. Transition: Quiet down (drops below stop_threshold 0.2)
        quiet_window_1 = self._generate_window(variance=0.08)
        evt_stopped = self.detector.process_window(quiet_window_1)
        self.assertIsNotNone(evt_stopped)
        self.assertEqual(evt_stopped.state, "MOTION_STOPPED")
        self.assertEqual(self.detector.state, MotionState.MOTION_STOPPED)

        # 6. Transition: Returns to No Motion
        quiet_window_2 = self._generate_window(variance=0.05)
        evt_nomotion = self.detector.process_window(quiet_window_2)
        self.assertIsNotNone(evt_nomotion)
        self.assertEqual(evt_nomotion.state, "NO_MOTION")
        self.assertEqual(self.detector.state, MotionState.NO_MOTION)

    def test_trajectory_and_speed_heuristics(self):
        """Verifies that predicted zone sequences update direction and speed correctly."""
        # Initial empty state
        self.assertEqual(self.detector.relative_direction, "stationary")
        self.assertEqual(self.detector.relative_speed, "none")

        # Set first prediction
        self.detector.update_predictions_history(101, "Kitchen")
        self.assertEqual(self.detector.relative_direction, "stationary in Kitchen")
        self.assertEqual(self.detector.relative_speed, "none")

        # Set second prediction
        self.detector.update_predictions_history(102, "Living Room")
        self.assertEqual(self.detector.relative_direction, "moving from Kitchen toward Living Room")
        self.assertEqual(self.detector.relative_speed, "slow")

        # Simulate fast moving through zones: Kitchen -> Living Room -> Desk -> Door
        self.detector.update_predictions_history(103, "Desk")
        self.assertEqual(self.detector.relative_direction, "moving from Living Room toward Desk")
        self.assertEqual(self.detector.relative_speed, "moderate")

        self.detector.update_predictions_history(104, "Door")
        self.assertEqual(self.detector.relative_direction, "moving from Desk toward Door")
        self.assertEqual(self.detector.relative_speed, "fast")


if __name__ == "__main__":
    unittest.main()
