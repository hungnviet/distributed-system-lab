"""
Duplicate Filter Plugin
Prevents transmission of identical data to reduce network bandwidth
"""

import logging
from typing import Any, List, Dict
from plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class DuplicateFilterPlugin(BasePlugin):
    """
    Filter out duplicate metrics to reduce network traffic
    Only sends data when values change
    """

    def initialize(self, config: Dict[str, Any] = None):
        """Initialize plugin with empty cache"""
        self.last_values = {}
        logger.info(f"[{self.name}] Initialized - will filter duplicate metrics")

    def run(self, data: Any) -> Any:
        """
        Filter metrics that have identical values to previous transmission
        Args:
            data: List of monitoring_pb2.MonitoringData objects
        Returns:
            Filtered list containing only changed metrics
        """
        if not data:
            return data

        filtered_data = []

        for metric in data:
            # Create unique key for this metric
            metric_key = f"{metric.hostname}:{metric.metric}"

            # Check if value changed
            last_value = self.last_values.get(metric_key)

            if last_value is None or abs(last_value - metric.value) > 0.01:
                # Value changed or first time seeing this metric
                filtered_data.append(metric)
                self.last_values[metric_key] = metric.value
                logger.debug(f"[{self.name}] Metric changed: {metric.metric} = {metric.value:.2f}")
            else:
                logger.debug(f"[{self.name}] Filtered duplicate: {metric.metric} = {metric.value:.2f}")

        if len(filtered_data) < len(data):
            logger.info(f"[{self.name}] Filtered {len(data) - len(filtered_data)} duplicate metrics")

        return filtered_data

    def finalize(self):
        """Cleanup"""
        total_metrics = len(self.last_values)
        logger.info(f"[{self.name}] Finalized - tracked {total_metrics} unique metrics")
        self.last_values.clear()
