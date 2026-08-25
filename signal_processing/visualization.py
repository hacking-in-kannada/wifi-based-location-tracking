"""
Visualization utilities for Channel State Information (CSI).
Generates heatmaps and time-series plots using Matplotlib.
Supports saving directly to disk or returning figures.
"""

import os
from typing import Optional
import matplotlib
# Set backend to Agg to allow server-side headless image generation without GUI
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def plot_amplitude_heatmap(
    amp: np.ndarray,
    title: str = "CSI Amplitude Heatmap",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Renders a 2D heatmap showing CSI amplitude across packets (time) and subcarriers.
    
    Args:
        amp: Array of shape (n_packets, n_subcarriers)
        title: Title of the plot
        save_path: If provided, saves the plot to this absolute file path
        
    Returns:
        fig: Matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # X-axis is subcarriers, Y-axis is packet index
    cax = ax.imshow(amp, aspect='auto', cmap='viridis', origin='lower')
    
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Subcarrier Index", fontsize=12)
    ax.set_ylabel("Packet Index (Time)", fontsize=12)
    
    # Add colorbar
    fig.colorbar(cax, label="Normalized Amplitude")
    fig.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
    return fig


def plot_phase_over_time(
    phase: np.ndarray,
    title: str = "CSI Phase over Time",
    subcarriers_to_plot: int = 5,
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Plots the phase series over time for a subset of subcarriers.
    
    Args:
        phase: Array of shape (n_packets, n_subcarriers)
        title: Title of the plot
        subcarriers_to_plot: Number of subcarriers to plot (to avoid visual clutter)
        save_path: If provided, saves the plot to this absolute file path
        
    Returns:
        fig: Matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    n_packets, n_subcarriers = phase.shape
    step = max(1, n_subcarriers // subcarriers_to_plot)
    indices = range(0, n_subcarriers, step)[:subcarriers_to_plot]

    packets = np.arange(n_packets)

    for idx in indices:
        ax.plot(packets, phase[:, idx], label=f"Subcarrier {idx}", alpha=0.8)

    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Packet Index (Time)", fontsize=12)
    ax.set_ylabel("Phase (Radians)", fontsize=12)
    ax.legend(loc="upper right", framealpha=0.5)
    ax.grid(True, linestyle='--', alpha=0.5)
    fig.tight_layout()

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

    return fig
