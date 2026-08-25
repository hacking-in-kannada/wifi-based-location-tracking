"""
Prediction smoothing pipeline.
Uses a rolling sliding window of predicted class probabilities to smooth outputs,
preventing classification flicker and rapid transitions.
"""

import collections
from typing import Dict, Tuple


class PredictionSmoother:
    """
    Stabilizes real-time zone predictions by averaging class probability maps
    over a sliding window of recent predictions.
    """

    def __init__(self, window_size: int = 5):
        """
        Args:
            window_size: Size of the rolling history window (K).
        """
        self.window_size = window_size
        self.history = collections.deque(maxlen=window_size)

    def add_prediction(self, raw_probs: Dict[int, float]) -> Dict[int, float]:
        """
        Adds a new raw prediction probability map to the history and returns the smoothed map.
        
        Args:
            raw_probs: Dict mapping position_id (int) -> probability (float)
            
        Returns:
            smoothed_probs: Dict mapping position_id (int) -> smoothed probability (float)
        """
        if not raw_probs:
            return {}

        self.history.append(raw_probs)

        # Extract all unique position IDs in history window
        unique_ids = set()
        for probs in self.history:
            unique_ids.update(probs.keys())

        # Compute average probability for each position ID across the window
        smoothed = {}
        for pos_id in unique_ids:
            total_p = sum(probs.get(pos_id, 0.0) for probs in self.history)
            smoothed[pos_id] = total_p / len(self.history)

        # Normalize probabilities to sum to 1.0 (guards against numerical rounding issues)
        total_sum = sum(smoothed.values())
        if total_sum > 0:
            smoothed = {pos_id: p / total_sum for pos_id, p in smoothed.items()}

        return smoothed

    def get_best_position(self, smoothed_probs: Dict[int, float]) -> Tuple[int, float]:
        """
        Finds the position ID with the highest smoothed probability.
        
        Args:
            smoothed_probs: Smoothed probability map.
            
        Returns:
            position_id: The predicted position ID.
            confidence: The smoothed probability/confidence of that class.
        """
        if not smoothed_probs:
            return -1, 0.0

        best_id = max(smoothed_probs, key=smoothed_probs.get)
        return best_id, smoothed_probs[best_id]
