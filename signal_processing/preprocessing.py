from __future__ import annotations

from collections.abc import Iterable
from statistics import mean, median

from backend.models.csi import CSIFrame


def moving_average(values: Iterable[float], window_size: int = 3) -> list[float]:
    samples = list(values)
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    if window_size > len(samples):
        return []

    smoothed: list[float] = []
    for index in range(len(samples) - window_size + 1):
        window = samples[index : index + window_size]
        smoothed.append(mean(window))
    return smoothed


def median_filter(values: Iterable[float], window_size: int = 3) -> list[float]:
    samples = list(values)
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    if window_size > len(samples):
        return []

    filtered: list[float] = []
    for index in range(len(samples) - window_size + 1):
        window = samples[index : index + window_size]
        filtered.append(float(median(window)))
    return filtered


def amplitude_normalize(values: Iterable[float]) -> list[float]:
    samples = list(values)
    if not samples:
        return []

    minimum = min(samples)
    maximum = max(samples)
    spread = maximum - minimum
    if spread == 0:
        return [0.0 for _ in samples]

    return [(value - minimum) / spread for value in samples]


def phase_calibrate(values: Iterable[float]) -> list[float]:
    samples = list(values)
    if not samples:
        return []

    reference = mean(samples)
    return [value - reference for value in samples]


def remove_outliers(values: Iterable[float], threshold: float = 2.5) -> list[float]:
    samples = list(values)
    if len(samples) < 2:
        return samples

    center = median(samples)
    deviations = [abs(value - center) for value in samples]
    mad = median(deviations)
    if mad == 0:
        return samples

    scale = 1.4826 * mad
    return [value for value in samples if abs(value - center) / scale <= threshold]


def process_csi_frame(frame: CSIFrame) -> dict[str, list[float] | float | int]:
    cleaned_amplitude = remove_outliers(frame.amplitude)
    cleaned_phase = phase_calibrate(frame.phase)

    return {
        "subcarriers": frame.subcarrier_count,
        "amplitude_smoothed": moving_average(amplitude_normalize(cleaned_amplitude), window_size=3),
        "phase_smoothed": moving_average(cleaned_phase, window_size=3),
        "amplitude_median": median_filter(cleaned_amplitude, window_size=3),
    }
