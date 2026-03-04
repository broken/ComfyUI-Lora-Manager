import os
import logging
from typing import Dict

from .base_model_service import BaseModelService
from ..utils.models import CheckpointMetadata
from ..config import config

logger = logging.getLogger(__name__)

class CheckpointService(BaseModelService):
    """Checkpoint-specific service implementation"""
    
    def __init__(self, scanner, update_service=None):
        """Initialize Checkpoint service
        
        Args:
            scanner: Checkpoint scanner instance
            update_service: Optional service for remote update tracking.
        """
        super().__init__("checkpoint", scanner, CheckpointMetadata, update_service=update_service)
    
    async def format_response(self, checkpoint_data: Dict) -> Dict:
        """Format Checkpoint data for API response"""
        # Get sub_type from cache entry (new canonical field)
        sub_type = checkpoint_data.get("sub_type", "checkpoint")
        
        return {
            "model_name": checkpoint_data["model_name"],
            "file_name": checkpoint_data["file_name"],
            "preview_url": config.get_preview_static_url(checkpoint_data.get("preview_url", "")),
            "preview_nsfw_level": checkpoint_data.get("preview_nsfw_level", 0),
            "base_model": checkpoint_data.get("base_model", ""),
            "folder": checkpoint_data["folder"],
            "sha256": checkpoint_data.get("sha256", ""),
            "file_path": checkpoint_data["file_path"].replace(os.sep, "/"),
            "file_size": checkpoint_data.get("size", 0),
            "modified": checkpoint_data.get("modified", ""),
            "tags": checkpoint_data.get("tags", []),
            "from_civitai": checkpoint_data.get("from_civitai", True),
            "usage_count": checkpoint_data.get("usage_count", 0),
            "notes": checkpoint_data.get("notes", ""),
            "sub_type": sub_type,
            "favorite": checkpoint_data.get("favorite", False),
            "update_available": bool(checkpoint_data.get("update_available", False)),
            "skip_metadata_refresh": bool(checkpoint_data.get("skip_metadata_refresh", False)),
            "civitai": self.filter_civitai_data(checkpoint_data.get("civitai", {}), minimal=True)
        }
    
    def find_duplicate_hashes(self) -> Dict:
        """Find Checkpoints with duplicate SHA256 hashes"""
        return self.scanner._hash_index.get_duplicate_hashes()
    
    def find_duplicate_filenames(self) -> Dict:
        """Find Checkpoints with conflicting filenames"""
        return self.scanner._hash_index.get_duplicate_filenames()

    async def _apply_pool_filters(
        self, available_checkpoints: list[Dict], pool_config: Dict
    ) -> list[Dict]:
        """
        Apply pool_config filters to available Checkpoints.

        Args:
            available_checkpoints: List of all Checkpoint dicts
            pool_config: Dict with filter settings from Pool node

        Returns:
            Filtered list of Checkpoint dicts
        """
        from .model_query import FilterCriteria

        filter_section = pool_config

        # Extract filter parameters
        selected_base_models = filter_section.get("baseModels", [])
        tags_dict = filter_section.get("tags", {})
        include_tags = tags_dict.get("include", [])
        exclude_tags = tags_dict.get("exclude", [])
        folders_dict = filter_section.get("folders", {})
        include_folders = folders_dict.get("include", [])
        exclude_folders = folders_dict.get("exclude", [])
        license_dict = filter_section.get("license", {})
        no_credit_required = license_dict.get("noCreditRequired", False)
        allow_selling = license_dict.get("allowSelling", False)

        # Build tag filters dict
        tag_filters = {}
        for tag in include_tags:
            tag_filters[tag] = "include"
        for tag in exclude_tags:
            tag_filters[tag] = "exclude"

        # Build folder filter
        if include_folders or exclude_folders:
            filtered = []
            for ckpt in available_checkpoints:
                folder = ckpt.get("folder", "")

                # Check exclude folders first
                excluded = False
                for exclude_folder in exclude_folders:
                    if folder.startswith(exclude_folder):
                        excluded = True
                        break

                if excluded:
                    continue

                # Check include folders
                if include_folders:
                    included = False
                    for include_folder in include_folders:
                        if folder.startswith(include_folder):
                            included = True
                            break
                    if not included:
                        continue

                filtered.append(ckpt)

            available_checkpoints = filtered

        # Apply base model filter
        if selected_base_models:
            available_checkpoints = [
                ckpt
                for ckpt in available_checkpoints
                if ckpt.get("base_model") in selected_base_models
            ]

        # Apply tag filters
        if tag_filters:
            criteria = FilterCriteria(tags=tag_filters)
            available_checkpoints = self.filter_set.apply(available_checkpoints, criteria)

        # Apply license filters
        if no_credit_required:
            available_checkpoints = [
                ckpt for ckpt in available_checkpoints
                if bool(ckpt.get("license_flags", 127) & (1 << 0))
            ]

        if allow_selling:
            available_checkpoints = [
                ckpt for ckpt in available_checkpoints
                if bool(ckpt.get("license_flags", 127) & (1 << 1))
            ]

        return available_checkpoints

    async def get_cycler_list(
        self,
        pool_config: dict | None = None,
        sort_by: str = "filename"
    ) -> list[Dict]:
        """
        Get filtered and sorted Checkpoint list for cycling.

        Args:
            pool_config: Optional pool config for filtering (filters dict)
            sort_by: Sort field - 'filename' or 'model_name'

        Returns:
            List of Checkpoint dicts with file_name and model_name
        """
        # Get cached data
        cache = await self.scanner.get_cached_data(force_refresh=False)
        available_checkpoints = cache.raw_data if cache else []

        # Apply pool filters if provided
        if pool_config:
            available_checkpoints = await self._apply_pool_filters(
                available_checkpoints, pool_config
            )

        # Sort by specified field
        if sort_by == "model_name":
            available_checkpoints = sorted(
                available_checkpoints,
                key=lambda x: (x.get("model_name") or x.get("file_name", "")).lower()
            )
        else:  # Default to filename
            available_checkpoints = sorted(
                available_checkpoints,
                key=lambda x: x.get("file_name", "").lower()
            )

        # Return minimal data needed for cycling
        return [
            {
                "file_name": ckpt["file_name"],
                "model_name": ckpt.get("model_name", ckpt["file_name"]),
            }
            for ckpt in available_checkpoints
        ]
