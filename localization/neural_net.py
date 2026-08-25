"""
Neural Network (PyTorch Multi-Layer Perceptron) Localization Model.
Conforms to the LocalizationModel interface.
"""

from typing import Dict, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from localization.base import LocalizationModel


class PyTorchMLP(nn.Module):
    """
    Standard PyTorch MLP architecture.
    """
    def __init__(self, input_dim: int, num_classes: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class NeuralNetLocalizer(LocalizationModel):
    """
    PyTorch MLP classifier for CSI room zone classification.
    """

    def __init__(self, epochs: int = 150, lr: float = 0.01, batch_size: int = 32):
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        
        self.model = None
        self.classes_ = None
        self.input_dim = None
        
        # Mappings between database position IDs and contiguous class indices [0..num_classes-1]
        self._id_to_idx: Dict[int, int] = {}
        self._idx_to_id: Dict[int, int] = {}

    def fit(self, X: np.ndarray, y: np.ndarray) -> "NeuralNetLocalizer":
        # Identify classes and build index mappings
        self.classes_ = np.unique(y)
        num_classes = len(self.classes_)
        self.input_dim = X.shape[1]
        
        self._id_to_idx = {int(cls): idx for idx, cls in enumerate(self.classes_)}
        self._idx_to_id = {idx: int(cls) for idx, cls in enumerate(self.classes_)}

        # Map labels to contiguous indexes
        y_mapped = np.array([self._id_to_idx[int(val)] for val in y], dtype=np.int64)

        # Convert to PyTorch Tensors
        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y_mapped, dtype=torch.long)

        # Create model, optimizer and loss function
        self.model = PyTorchMLP(self.input_dim, num_classes)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.lr)

        dataset = torch.utils.data.TensorDataset(X_tensor, y_tensor)
        loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        # Training loop
        self.model.train()
        for epoch in range(self.epochs):
            for batch_x, batch_y in loader:
                optimizer.zero_grad()
                outputs = self.model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()

        self.model.eval()
        return self

    def predict(self, x: np.ndarray) -> Tuple[int, float]:
        if self.model is None:
            raise RuntimeError("Model has not been trained yet. Call fit() first.")
        
        if x.ndim == 1:
            x = x.reshape(1, -1)

        x_tensor = torch.tensor(x, dtype=torch.float32)
        
        self.model.eval()
        with torch.no_grad():
            logits = self.model(x_tensor)
            probs = torch.softmax(logits, dim=-1).numpy()[0]

        max_idx = int(np.argmax(probs))
        pred_class = self._idx_to_id[max_idx]
        confidence = float(probs[max_idx])

        return pred_class, confidence

    def predict_proba(self, x: np.ndarray) -> Dict[int, float]:
        if self.model is None:
            raise RuntimeError("Model has not been trained yet. Call fit() first.")

        if x.ndim == 1:
            x = x.reshape(1, -1)

        x_tensor = torch.tensor(x, dtype=torch.float32)
        
        self.model.eval()
        with torch.no_grad():
            logits = self.model(x_tensor)
            probs = torch.softmax(logits, dim=-1).numpy()[0]

        return {self._idx_to_id[idx]: float(prob) for idx, prob in enumerate(probs)}
