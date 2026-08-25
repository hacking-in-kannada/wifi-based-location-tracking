"""
Unit tests for the localization models and prediction smoother.
"""

import unittest
import numpy as np

from localization.knn import KNNLocalizer
from localization.random_forest import RandomForestLocalizer
from localization.svm import SVMLocalizer
from localization.neural_net import NeuralNetLocalizer
from localization.smoothing import PredictionSmoother


class TestLocalization(unittest.TestCase):
    def setUp(self):
        # Generate simple training data: 3 classes, 30 samples each, 10 features
        np.random.seed(42)
        self.n_features = 10
        self.X_train = np.vstack([
            np.random.normal(loc=0.0, scale=0.2, size=(30, self.n_features)),
            np.random.normal(loc=2.0, scale=0.2, size=(30, self.n_features)),
            np.random.normal(loc=4.0, scale=0.2, size=(30, self.n_features))
        ])
        self.y_train = np.hstack([
            np.full(30, 10),  # Position 10
            np.full(30, 20),  # Position 20
            np.full(30, 30)   # Position 30
        ])

        # Test samples matching each class cluster
        self.test_alpha = np.random.normal(loc=0.0, scale=0.1, size=(1, self.n_features))
        self.test_beta = np.random.normal(loc=2.0, scale=0.1, size=(1, self.n_features))
        self.test_gamma = np.random.normal(loc=4.0, scale=0.1, size=(1, self.n_features))

    def _test_model_interface(self, model):
        """Helper to assert conformity of a model instance."""
        # 1. Fit
        model.fit(self.X_train, self.y_train)

        # 2. Predict
        pos, conf = model.predict(self.test_alpha)
        self.assertIn(pos, [10, 20, 30])
        self.assertTrue(0.0 <= conf <= 1.0)

        # 3. Predict Proba
        prob_dict = model.predict_proba(self.test_alpha)
        self.assertEqual(len(prob_dict), 3)
        self.assertIn(10, prob_dict)
        self.assertIn(20, prob_dict)
        self.assertIn(30, prob_dict)
        self.assertAlmostEqual(sum(prob_dict.values()), 1.0, places=5)

        # 4. Check classification accuracy on centroids
        pos_a, _ = model.predict(self.test_alpha)
        self.assertEqual(pos_a, 10)
        
        pos_b, _ = model.predict(self.test_beta)
        self.assertEqual(pos_b, 20)
        
        pos_c, _ = model.predict(self.test_gamma)
        self.assertEqual(pos_c, 30)

    def test_knn_localizer(self):
        """Verifies KNNLocalizer fits and predicts correctly."""
        self._test_model_interface(KNNLocalizer(n_neighbors=3))

    def test_random_forest_localizer(self):
        """Verifies RandomForestLocalizer fits and predicts correctly."""
        self._test_model_interface(RandomForestLocalizer(n_estimators=10, random_state=42))

    def test_svm_localizer(self):
        """Verifies SVMLocalizer fits and predicts correctly."""
        self._test_model_interface(SVMLocalizer(C=1.0, random_state=42))

    def test_neural_net_localizer(self):
        """Verifies NeuralNetLocalizer fits and predicts correctly."""
        self._test_model_interface(NeuralNetLocalizer(epochs=50, lr=0.01))

    def test_prediction_smoother(self):
        """Verifies prediction smoother stabilizes probability fluctuations."""
        smoother = PredictionSmoother(window_size=3)

        # Pred 1: 10 is dominant
        p1 = {10: 0.8, 20: 0.2}
        res1 = smoother.add_prediction(p1)
        self.assertEqual(res1, p1)

        # Pred 2: temporary flicker, 20 is dominant
        p2 = {10: 0.1, 20: 0.9}
        res2 = smoother.add_prediction(p2)
        # Smoothed should be average:
        # 10: (0.8 + 0.1)/2 = 0.45
        # 20: (0.2 + 0.9)/2 = 0.55
        self.assertAlmostEqual(res2[10], 0.45)
        self.assertAlmostEqual(res2[20], 0.55)

        # Pred 3: 10 returns dominant
        p3 = {10: 0.9, 20: 0.1}
        res3 = smoother.add_prediction(p3)
        # Smoothed should average all 3:
        # 10: (0.8 + 0.1 + 0.9)/3 = 0.60
        # 20: (0.2 + 0.9 + 0.1)/3 = 0.40
        self.assertAlmostEqual(res3[10], 0.60)
        self.assertAlmostEqual(res3[20], 0.40)

        # Best position should be 10, confidence 60%
        best_id, confidence = smoother.get_best_position(res3)
        self.assertEqual(best_id, 10)
        self.assertAlmostEqual(confidence, 0.60)


if __name__ == "__main__":
    unittest.main()
