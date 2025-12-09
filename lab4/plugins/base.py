from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BasePlugin(ABC):

    def __init__(self):
        self.name = self.__class__.__name__

    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None):
        pass

    @abstractmethod
    def run(self, data: Any) -> Any:
        pass

    @abstractmethod
    def finalize(self):
        pass
