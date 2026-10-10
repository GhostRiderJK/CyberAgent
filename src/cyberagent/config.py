"""
Configuration loader for CyberAgent.
Handles loading and accessing configuration from config.yaml.
"""
import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional

class Config:
    """Configuration manager."""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._config:
            self.load_config()
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml file. If None, defaults to
                config.yaml two levels up from this file (project root).
        """
        if config_path is None:
            # Default to config.yaml in project root (two levels up from this file)
            config_file = Path(__file__).resolve().parents[2] / "config.yaml"
        else:
            config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, 'r') as f:
            self._config = yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'dataset.raw_dir')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'dataset.raw_dir')
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()

# Global config instance
config = Config()
