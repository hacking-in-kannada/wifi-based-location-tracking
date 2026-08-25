"""
Feature vector exporting utilities.
Supports exporting lists of FeatureVector objects to CSV and Apache Parquet formats.
"""

import os
from typing import List
import pandas as pd

from feature_extraction.features import FeatureVector


def _vectors_to_dataframe(feature_vectors: List[FeatureVector]) -> pd.DataFrame:
    """
    Helper function to convert a list of FeatureVector objects into a flat pandas DataFrame.
    """
    if not feature_vectors:
        return pd.DataFrame()
        
    rows = [vector.to_dict() for vector in feature_vectors]
    return pd.DataFrame(rows)


def export_to_csv(feature_vectors: List[FeatureVector], filepath: str):
    """
    Exports a list of FeatureVector objects to a CSV file.
    
    Args:
        feature_vectors: List of FeatureVector objects.
        filepath: Absolute file path where the CSV will be saved.
    """
    df = _vectors_to_dataframe(feature_vectors)
    
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    df.to_csv(filepath, index=False)


def export_to_parquet(feature_vectors: List[FeatureVector], filepath: str):
    """
    Exports a list of FeatureVector objects to an Apache Parquet file.
    
    Args:
        feature_vectors: List of FeatureVector objects.
        filepath: Absolute file path where the Parquet will be saved.
    """
    df = _vectors_to_dataframe(feature_vectors)
    
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Save as parquet using PyArrow engine
    df.to_parquet(filepath, index=False, engine="pyarrow")
