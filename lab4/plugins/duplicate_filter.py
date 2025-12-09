import logging
from typing import Any, List, Dict
from plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class DuplicateFilterPlugin(BasePlugin):

    def initialize(self, config: Dict[str, Any] = None):
        self.last_values = {}
        logger.info(f"[{self.name}] Initialized - will filter duplicate metrics")

    def run(self, data: Any) -> Any:
        if not data:
            return data

        filtered_data = []

        for metric in data:
            metric_key = f"{metric.hostname}:{metric.metric}"
            last_value = self.last_values.get(metric_key)

            if last_value is None or abs(last_value - metric.value) > 0.01:
                filtered_data.append(metric)
                self.last_values[metric_key] = metric.value
                logger.debug(f"[{self.name}] Metric changed: {metric.metric} = {metric.value:.2f}")
            else:
                logger.debug(f"[{self.name}] Filtered duplicate: {metric.metric} = {metric.value:.2f}")

        if len(filtered_data) < len(data):
            logger.info(f"[{self.name}] Filtered {len(data) - len(filtered_data)} duplicate metrics")

        return filtered_data

    def finalize(self):
        total_metrics = len(self.last_values)
        logger.info(f"[{self.name}] Finalized - tracked {total_metrics} unique metrics")
        self.last_values.clear()
