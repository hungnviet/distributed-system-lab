import logging
from typing import Any, Dict
from plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class ThresholdAlertPlugin(BasePlugin):

    def initialize(self, config: Dict[str, Any] = None):
        self.thresholds = config or {
            "cpu": 80.0,
            "memory": 85.0,
            "disk": 90.0
        }
        self.alert_count = 0
        logger.info(f"[{self.name}] Initialized with thresholds: {self.thresholds}")

    def run(self, data: Any) -> Any:
        if not data:
            return data

        for metric in data:
            metric_name = metric.metric.lower()

            for threshold_key, threshold_value in self.thresholds.items():
                if threshold_key in metric_name:
                    if metric.value > threshold_value:
                        self.alert_count += 1
                        logger.warning(
                            f"[{self.name}] ⚠️  ALERT #{self.alert_count}: "
                            f"{metric.hostname} - {metric.metric} = {metric.value:.2f}% "
                            f"(threshold: {threshold_value}%)"
                        )

        return data

    def finalize(self):
        logger.info(f"[{self.name}] Finalized - Total alerts generated: {self.alert_count}")
