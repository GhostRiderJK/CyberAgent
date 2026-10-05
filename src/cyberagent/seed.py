"""
Global seed utility for CyberAgent.
Sets seeds for reproducibility across numpy, random, torch, etc.
"""
import os
import random
import numpy as np
from .config import config

def set_global_seed(seed: int = None) -> None:
    """
    Set global seed for reproducibility.
    
    Args:
        seed: Seed value. If None, uses seed from config.
    """
    if seed is None:
        seed = config.get("seed", 42)
    
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    
    # Try to set torch seed if available
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        # Below settings may slow down training but ensure reproducibility
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass  # torch not available, ignore
    
    # Try to set tensorflow seed if available
    try:
        import tensorflow as tf
        tf.random.set_seed(seed)
    except ImportError:
        pass  # tensorflow not available, ignore

def get_seed() -> int:
    """
    Get the global seed from config.
    
    Returns:
        Seed value from config or default 42.
    """
    return config.get("seed", 42)
