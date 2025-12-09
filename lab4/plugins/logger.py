import logging
from typing import Any, Dict
from plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class LoggerPlugin(BasePlugin):

    def initialize(self, config: Dict[str, Any] = None):
        self.metric_count = 0
        self.enabled = config.get("enabled", True) if config else True
        logger.info(f"[{self.name}] Initialized - logging enabled: {self.enabled}")

    def run(self, data: Any) -> Any:
        if not self.enabled or not data:
            return data

        for metric in data:
            self.metric_count += 1
            logger.info(
                f"[{self.name}] Metric #{self.metric_count}: "
                f"{metric.hostname} | {metric.metric} = {metric.value:.2f}"
            )

        return data

    def finalize(self):
        logger.info(f"[{self.name}] Finalized - Logged {self.metric_count} metrics")
