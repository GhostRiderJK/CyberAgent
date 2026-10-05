"""
Smoke test to verify basic functionality.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    """Test that we can import our modules."""
    try:
        from src.cyberagent.config import config
        from src.cyberagent.logging_setup import setup_logging
        from src.cyberagent.seed import set_global_seed, get_seed
        print("All imports successful!")
    except ImportError as e:
        print(f"Import failed: {e}")
        raise

def test_seed():
    """Test seed functionality."""
    from src.cyberagent.seed import get_seed, set_global_seed
    seed = get_seed()
    assert isinstance(seed, int), f"Seed should be int, got {type(seed)}"
    set_global_seed(seed)
    print("Seed test passed!")

if __name__ == "__main__":
    test_imports()
    test_seed()
    print("Smoke tests passed!")
