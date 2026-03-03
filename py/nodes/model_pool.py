"""
Model Pool Node - Defines filter configuration for Model selection.

This node provides a visual filter editor that generates a MODEL_POOL_CONFIG
object for use by downstream nodes (like Model Randomizer or Cycler).
"""

import logging

logger = logging.getLogger(__name__)


class ModelPoolLM:
    """
    A node that defines Model filter criteria through a Vue-based widget.

    Outputs a MODEL_POOL_CONFIG that can be consumed by backend Cycler/Randomizer nodes,
    and a POOL_SIZE integer indicating the number of models matching the filter.
    """

    NAME = "Model Pool (LoraManager)"
    CATEGORY = "Lora Manager/randomizer"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pool_config": ("MODEL_POOL_CONFIG", {}),
            },
            "hidden": {
                # Hidden input to pass through unique node ID for frontend
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("MODEL_POOL_CONFIG", "INT")
    RETURN_NAMES = ("MODEL_POOL_CONFIG", "POOL_SIZE")

    FUNCTION = "process"
    OUTPUT_NODE = False

    async def process(self, pool_config, unique_id=None):
        """
        Pass through the pool configuration filters and calculate the pool size.

        Args:
            pool_config: Dict containing filter criteria from widget
            unique_id: Node's unique ID (hidden)

        Returns:
            Tuple containing the filters dict and the count of matching models
        """
        from ..services.service_registry import ServiceRegistry
        from ..services.checkpoint_service import CheckpointService

        # Validate required structure
        if not isinstance(pool_config, dict):
            logger.warning("Invalid pool_config type, using empty config")
            pool_config = self._default_config()

        # Ensure version field exists
        if "version" not in pool_config:
            pool_config["version"] = 1

        # Extract filters field
        filters = pool_config.get("filters", self._default_config()["filters"])

        # Log for debugging
        logger.debug(f"[ModelPoolLM] Processing filters: {filters}")

        # Calculate pool size by fetching the cycler list
        scanner = await ServiceRegistry.get_checkpoint_scanner()
        service = CheckpointService(scanner)
        cycler_list = await service.get_cycler_list(pool_config=filters)
        pool_size = len(cycler_list)

        return (filters, pool_size)

    @staticmethod
    def _default_config():
        """Return default empty configuration."""
        return {
            "version": 1,
            "filters": {
                "baseModels": [],
                "tags": {"include": [], "exclude": []},
                "folders": {"include": [], "exclude": []},
                "favoritesOnly": False,
                "license": {"noCreditRequired": False, "allowSelling": False},
            },
            "preview": {"matchCount": 0, "lastUpdated": 0},
        }
