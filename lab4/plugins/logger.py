"""
Logger Plugin
Simple plugin that logs all metrics passing through
"""

import logging
from typing import Any, Dict
from plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class LoggerPlugin(BasePlugin):
    """
    Logs all metrics for debugging purposes
    """

    def initialize(self, config: Dict[str, Any] = None):
        """Initialize plugin"""
        self.metric_count = 0
        self.enabled = config.get("enabled", True) if config else True
        logger.info(f"[{self.name}] Initialized - logging enabled: {self.enabled}")

    def run(self, data: Any) -> Any:
        """
        Log all metrics
        Args:
            data: List of monitoring_pb2.MonitoringData objects
        Returns:
            Original data unchanged
        """
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
        """Cleanup"""
        logger.info(f"[{self.name}] Finalized - Logged {self.metric_count} metrics")
