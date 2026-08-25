"""
Motion Detection Module.
Provides a 4-state hysteresis state machine for motion classification
and relative movement trajectory heuristics from CSI data.
"""

from dataclasses import dataclass, asdict
import datetime
import enum
import json
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from database.db import get_session
from database.models import Event, Position


class MotionState(enum.Enum):
    NO_MOTION = 1
    MOTION_STARTED = 2
    CONTINUOUS_MOTION = 3
    MOTION_STOPPED = 4


@dataclass
class MotionEvent:
    state: str
    variance: float
    direction: str
    speed: str
    timestamp: str


class MotionDetector:
    """
    State machine that processes sliding windows of CSI amplitudes 
    to detect human motion and estimate relative trajectories.
    """

    def __init__(
        self,
        start_threshold: float = 0.5,
        stop_threshold: float = 0.2,
        history_size: int = 10
    ):
        """
        Args:
            start_threshold: Variance threshold above which motion is detected.
            stop_threshold: Variance threshold below which motion is considered stopped (hysteresis).
            history_size: Number of past position predictions to keep for trajectory calculations.
        """
        self.start_threshold = start_threshold
        self.stop_threshold = stop_threshold
        
        self.state = MotionState.NO_MOTION
        self.position_history: List[Tuple[int, str]] = []  # List of (position_id, label)
        self.history_size = history_size

        # Heuristics
        self.relative_direction = "stationary"
        self.relative_speed = "none"

    def update_predictions_history(self, position_id: int, label: str):
        """
        Pushes the latest estimated position onto the history stack.
        """
        self.position_history.append((position_id, label))
        if len(self.position_history) > self.history_size:
            self.position_history.pop(0)

        self._recalculate_trajectory()

    def _recalculate_trajectory(self):
        """
        Heuristically estimates direction and speed based on the sequence of visited zones.
        """
        if not self.position_history:
            self.relative_direction = "stationary"
            self.relative_speed = "none"
            return

        if len(self.position_history) == 1:
            self.relative_direction = f"stationary in {self.position_history[0][1]}"
            self.relative_speed = "none"
            return


        # Unique zones in history in order of appearance
        visited_zones = []
        for _, label in self.position_history:
            if not visited_zones or visited_zones[-1] != label:
                visited_zones.append(label)

        if len(visited_zones) >= 2:
            self.relative_direction = f"moving from {visited_zones[-2]} toward {visited_zones[-1]}"
            
            # Estimate speed based on how fast the zones are changing in history
            switches = len(visited_zones) - 1
            if switches >= 3:
                self.relative_speed = "fast"
            elif switches == 2:
                self.relative_speed = "moderate"
            else:
                self.relative_speed = "slow"
        else:
            self.relative_direction = f"stationary in {self.position_history[-1][1]}"
            self.relative_speed = "none"

    def process_window(self, csi_window: np.ndarray) -> Optional[MotionEvent]:
        """
        Computes window variance, updates the state machine, logs database events on transition,
        and returns the MotionEvent if a state transition occurred.
        
        Args:
            csi_window: Array of shape (n_packets, n_subcarriers) containing CSI amplitudes.
            
        Returns:
            motion_event: MotionEvent if state changed, else None.
        """
        if csi_window.shape[0] <= 1:
            return None

        # 1. Compute rolling variance metric: mean of subcarrier variances
        subcarrier_vars = np.var(csi_window, axis=0)
        variance_metric = float(np.mean(subcarrier_vars))

        previous_state = self.state

        # 2. Hysteresis State Machine
        if self.state == MotionState.NO_MOTION:
            if variance_metric > self.start_threshold:
                self.state = MotionState.MOTION_STARTED

        elif self.state == MotionState.MOTION_STARTED:
            if variance_metric > self.stop_threshold:
                self.state = MotionState.CONTINUOUS_MOTION
            else:
                self.state = MotionState.MOTION_STOPPED

        elif self.state == MotionState.CONTINUOUS_MOTION:
            if variance_metric < self.stop_threshold:
                self.state = MotionState.MOTION_STOPPED

        elif self.state == MotionState.MOTION_STOPPED:
            if variance_metric > self.start_threshold:
                self.state = MotionState.MOTION_STARTED
            else:
                self.state = MotionState.NO_MOTION

        # 3. Log Event on transition
        if self.state != previous_state:
            event_payload = MotionEvent(
                state=self.state.name,
                variance=variance_metric,
                direction=self.relative_direction,
                speed=self.relative_speed,
                timestamp=datetime.datetime.utcnow().isoformat()
            )
            
            self._log_event_to_db(event_payload)
            return event_payload

        return None

    def _log_event_to_db(self, motion_event: MotionEvent):
        """
        Saves the motion event to the database.
        """
        session = get_session()
        try:
            event = Event(
                event_type="motion_event",
                payload_json=json.dumps(asdict(motion_event))
            )
            session.add(event)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
