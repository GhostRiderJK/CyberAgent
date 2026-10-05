"""
Test configuration loading.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cyberagent.config import config

def test_config_loading():
    """Test that configuration loads correctly."""
    # Test that we can get values
    seed = config.get("seed")
    assert seed == 42, f"Expected seed 42, got {seed}"
    
    raw_dir = config.get("dataset.raw_dir")
    assert raw_dir == "data/raw", f"Expected 'data/raw', got {raw_dir}"
    
    print("Config loading test passed!")

if __name__ == "__main__":
    test_config_loading()
