import pandas as pd
import os
from pathlib import Path
import sys
sys.path.insert(0, '.')

from src.cyberagent.data_loader import load_traffic_labelling_data
from src.cyberagent.config import config

# Create test data
import tempfile
with tempfile.TemporaryDirectory() as temp_dir:
    data = {
        'Flow ID': [1, 2, 3],
        'Source IP': ['192.168.1.1', '192.168.1.2', '192.168.1.3'],
        'Source Port': [8080, 8081, 8082],
        'Destination IP': ['10.0.0.1', '10.0.0.2', '10.0.0.3'],
        'Destination Port': [80, 443, 80],
        'Protocol': [6, 6, 17],
        'Fwd Header Length': [100, 100, 100],
        'Fwd Header Length.1': [200, 200, 200],
        'Label': ['BENIGN', 'DoS Hulk', 'PortScan']
    }
    df = pd.DataFrame(data)
    csv_path = Path(temp_dir) / "test.csv"
    df.to_csv(csv_path, index=False)

    # Override config
    original_raw_dir = config.get("dataset.raw_dir")
    original_primary_folder = config.get("dataset.primary_folder")
    original_file_extension = config.get("dataset.file_extension")

    config.set("dataset.raw_dir", temp_dir)
    config.set("dataset.primary_folder", ".")
    config.set("dataset.file_extension", ".csv")

    try:
        features_df, metadata_df = load_traffic_labelling_data()
        print("Features columns:", list(features_df.columns))
        print("Metadata columns:", list(metadata_df.columns))
    finally:
        config.set("dataset.raw_dir", original_raw_dir)
        config.set("dataset.primary_folder", original_primary_folder)
        config.set("dataset.file_extension", original_file_extension)