"""
Model Cycler Node - Sequentially cycles through Models from a pool.

This node accepts optional pool_config input to filter available Models, and outputs
a ckpt_name string. Returns UI updates with current/next Model info
and tracks the cycle progress which persists across workflow save/load.
"""

import logging

logger = logging.getLogger(__name__)


class ModelCyclerLM:
    """Node that sequentially cycles through Models from a pool"""

    NAME = "Model Cycler (LoraManager)"
    CATEGORY = "Lora Manager/randomizer"

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "cycler_config": ("MODEL_CYCLER_CONFIG", {}),
            },
            "optional": {
                "pool_config": ("MODEL_POOL_CONFIG", {}),
                "repeat_count_override": ("INT", {"default": 0, "min": 0, "max": 9999, "forceInput": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("ckpt_name",)

    FUNCTION = "cycle"
    OUTPUT_NODE = False

    async def cycle(self, cycler_config, pool_config=None, repeat_count_override=None):
        """
        Cycle through Checkpoints based on configuration and pool filters.

        Args:
            cycler_config: Dict with cycler settings (current_index, sort_by)
            pool_config: Optional config from Model Pool node for filtering
            repeat_count_override: Optional integer to override the repeat count

        Returns:
            Dictionary with 'result' (ckpt_name tuple) and 'ui' (for widget display)
        """
        from ..services.service_registry import ServiceRegistry
        from ..services.checkpoint_service import CheckpointService

        # Extract settings from cycler_config
        current_index = cycler_config.get("current_index", 1)  # 1-based
        sort_by = "filename"

        # Dual-index mechanism for batch queue synchronization
        execution_index = cycler_config.get("execution_index")  # Can be None

        # Get scanner and service
        scanner = await ServiceRegistry.get_checkpoint_scanner()
        service = CheckpointService(scanner)

        # Get filtered and sorted list
        ckpt_list = await service.get_cycler_list(
            pool_config=pool_config, sort_by=sort_by
        )

        total_count = len(ckpt_list)

        if total_count == 0:
            logger.warning("[ModelCyclerLM] No Models available in pool")
            return {
                "result": ("",),
                "ui": {
                    "current_index": [1],
                    "next_index": [1],
                    "total_count": [0],
                    "current_model_name": [""],
                    "current_model_filename": [""],
                    "error": ["No Models available in pool"],
                },
            }

        # Override repeat count if input is provided AND valid (>0)
        # Note: we don't actually control the index logic here (it's in the Vue widget),
        # but we pass the override back in the UI dict so the Vue widget knows to use it
        # on the next execution.
        repeat_count = cycler_config.get("repeat_count", 1)
        if repeat_count_override is not None and repeat_count_override > 0:
            repeat_count = repeat_count_override

        # Determine which index to use for this execution
        # If execution_index is provided (batch queue case), use it
        # Otherwise use current_index (first execution or non-batch case)
        if execution_index is not None:
            actual_index = execution_index
        else:
            actual_index = current_index

        # Clamp index to valid range (1-based)
        clamped_index = max(1, min(actual_index, total_count))

        # Get Model at current index (convert to 0-based for list access)
        current_ckpt = ckpt_list[clamped_index - 1]

        # Calculate next index (wrap to 1 if at end)
        next_index = clamped_index + 1
        if next_index > total_count:
            next_index = 1

        # Get next Model for UI display
        next_ckpt = ckpt_list[next_index - 1]
        next_display_name = next_ckpt["file_name"]

        return {
            "result": (current_ckpt["file_name"],),
            "ui": {
                "current_index": [clamped_index],
                "next_index": [next_index],
                "total_count": [total_count],
                "current_model_name": [current_ckpt["file_name"]],
                "current_model_filename": [current_ckpt["file_name"]],
                "next_model_name": [next_display_name],
                "next_model_filename": [next_ckpt["file_name"]],
                "repeat_count_override": [repeat_count], # Tell frontend about the override
            },
        }
