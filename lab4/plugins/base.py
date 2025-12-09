"""
Plugin Base Class for Lab 4
Defines the abstract interface that all plugins must implement
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BasePlugin(ABC):
    """Base class for all monitoring plugins"""

    def __init__(self):
        self.name = self.__class__.__name__

    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None):
        """
        Initialize plugin with configuration
        Args:
            config: Plugin-specific configuration dictionary
        """
        pass

    @abstractmethod
    def run(self, data: Any) -> Any:
        """
        Main plugin logic - process data
        Args:
            data: Input data to process (e.g., list of metrics)
        Returns:
            Processed data
        """
        pass

    @abstractmethod
    def finalize(self):
        """
        Cleanup resources and finalize plugin execution
        """
        pass
