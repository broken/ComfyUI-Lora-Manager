import asyncio
import logging
from aiohttp import web
from typing import Dict
from server import PromptServer  # type: ignore

from .base_model_routes import BaseModelRoutes
from .model_route_registrar import ModelRouteRegistrar
from ..services.lora_service import LoraService
from ..services.service_registry import ServiceRegistry
from ..utils.utils import get_lora_info

logger = logging.getLogger(__name__)


class LoraRoutes(BaseModelRoutes):
    """LoRA-specific route controller"""

    def __init__(self):
        """Initialize LoRA routes with LoRA service"""
        super().__init__()
        self.template_name = "loras.html"

    async def initialize_services(self):
        """Initialize services from ServiceRegistry"""
        lora_scanner = await ServiceRegistry.get_lora_scanner()
        update_service = await ServiceRegistry.get_model_update_service()
        self.service = LoraService(lora_scanner, update_service=update_service)
        self.set_model_update_service(update_service)

        # Attach service dependencies
        self.attach_service(self.service)

    def setup_routes(self, app: web.Application):
        """Setup LoRA routes"""
        # Schedule service initialization on app startup
        app.on_startup.append(lambda _: self.initialize_services())

        # Setup common routes with 'loras' prefix (includes page route)
        super().setup_routes(app, "loras")

    def setup_specific_routes(self, registrar: ModelRouteRegistrar, prefix: str):
        """Setup LoRA-specific routes"""
        # LoRA-specific query routes
        registrar.add_prefixed_route(
            "GET", "/api/lm/{prefix}/letter-counts", prefix, self.get_letter_counts
        )
        registrar.add_prefixed_route(
            "GET",
            "/api/lm/{prefix}/get-trigger-words",
            prefix,
            self.get_lora_trigger_words,
        )
        registrar.add_prefixed_route(
            "GET",
            "/api/lm/{prefix}/usage-tips-by-path",
            prefix,
            self.get_lora_usage_tips_by_path,
        )

        # Views routes
        registrar.add_prefixed_route(
            "GET", "/api/lm/{prefix}/views/list", prefix, self.get_views_list
        )
        registrar.add_prefixed_route(
            "GET", "/api/lm/{prefix}/views/image", prefix, self.get_view_image
        )

        # Randomizer routes
        registrar.add_prefixed_route(
            "POST", "/api/lm/{prefix}/random-sample", prefix, self.get_random_loras
        )

        # Cycler routes
        registrar.add_prefixed_route(
            "POST", "/api/lm/{prefix}/cycler-list", prefix, self.get_cycler_list
        )

        # ComfyUI integration
        registrar.add_prefixed_route(
            "POST", "/api/lm/{prefix}/get_trigger_words", prefix, self.get_trigger_words
        )

    def _parse_specific_params(self, request: web.Request) -> Dict:
        """Parse LoRA-specific parameters"""
        params = {}

        # LoRA-specific parameters
        if "first_letter" in request.query:
            params["first_letter"] = request.query.get("first_letter")

        # Handle fuzzy search parameter name variation
        if request.query.get("fuzzy") == "true":
            params["fuzzy_search"] = True

        # Handle additional filter parameters for LoRAs
        if "lora_hash" in request.query:
            if not params.get("hash_filters"):
                params["hash_filters"] = {}
            params["hash_filters"]["single_hash"] = request.query["lora_hash"].lower()
        elif "lora_hashes" in request.query:
            if not params.get("hash_filters"):
                params["hash_filters"] = {}
            params["hash_filters"]["multiple_hashes"] = [
                h.lower() for h in request.query["lora_hashes"].split(",")
            ]

        return params

    def _validate_civitai_model_type(self, model_type: str) -> bool:
        """Validate CivitAI model type for LoRA"""
        from ..utils.constants import VALID_LORA_TYPES

        return model_type.lower() in VALID_LORA_TYPES

    def _get_expected_model_types(self) -> str:
        """Get expected model types string for error messages"""
        return "LORA, LoCon, or DORA"

    # LoRA-specific route handlers
    async def get_letter_counts(self, request: web.Request) -> web.Response:
        """Get count of LoRAs for each letter of the alphabet"""
        try:
            letter_counts = await self.service.get_letter_counts()
            return web.json_response({"success": True, "letter_counts": letter_counts})
        except Exception as e:
            logger.error(f"Error getting letter counts: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_lora_notes(self, request: web.Request) -> web.Response:
        """Get notes for a specific LoRA file"""
        try:
            lora_name = request.query.get("name")
            if not lora_name:
                return web.Response(text="Lora file name is required", status=400)

            notes = await self.service.get_lora_notes(lora_name)
            if notes is not None:
                return web.json_response({"success": True, "notes": notes})
            else:
                return web.json_response(
                    {"success": False, "error": "LoRA not found in cache"}, status=404
                )

        except Exception as e:
            logger.error(f"Error getting lora notes: {e}", exc_info=True)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_lora_trigger_words(self, request: web.Request) -> web.Response:
        """Get trigger words for a specific LoRA file"""
        try:
            lora_name = request.query.get("name")
            if not lora_name:
                return web.Response(text="Lora file name is required", status=400)

            trigger_words = await self.service.get_lora_trigger_words(lora_name)
            return web.json_response({"success": True, "trigger_words": trigger_words})

        except Exception as e:
            logger.error(f"Error getting lora trigger words: {e}", exc_info=True)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_lora_usage_tips_by_path(self, request: web.Request) -> web.Response:
        """Get usage tips for a LoRA by its relative path"""
        try:
            relative_path = request.query.get("relative_path")
            if not relative_path:
                return web.Response(text="Relative path is required", status=400)

            usage_tips = await self.service.get_lora_usage_tips_by_relative_path(
                relative_path
            )
            return web.json_response({"success": True, "usage_tips": usage_tips or ""})

        except Exception as e:
            logger.error(f"Error getting lora usage tips by path: {e}", exc_info=True)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_lora_preview_url(self, request: web.Request) -> web.Response:
        """Get the static preview URL for a LoRA file"""
        try:
            lora_name = request.query.get("name")
            if not lora_name:
                return web.Response(text="Lora file name is required", status=400)

            preview_url = await self.service.get_lora_preview_url(lora_name)
            if preview_url:
                return web.json_response({"success": True, "preview_url": preview_url})
            else:
                return web.json_response(
                    {
                        "success": False,
                        "error": "No preview URL found for the specified lora",
                    },
                    status=404,
                )

        except Exception as e:
            logger.error(f"Error getting lora preview URL: {e}", exc_info=True)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_lora_civitai_url(self, request: web.Request) -> web.Response:
        """Get the Civitai URL for a LoRA file"""
        try:
            lora_name = request.query.get("name")
            if not lora_name:
                return web.Response(text="Lora file name is required", status=400)

            result = await self.service.get_lora_civitai_url(lora_name)
            if result["civitai_url"]:
                return web.json_response({"success": True, **result})
            else:
                return web.json_response(
                    {
                        "success": False,
                        "error": "No Civitai data found for the specified lora",
                    },
                    status=404,
                )

        except Exception as e:
            logger.error(f"Error getting lora Civitai URL: {e}", exc_info=True)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_views_list(self, request: web.Request) -> web.Response:
        """Get list of available alternative views for LoRAs"""
        import os
        import folder_paths
        try:
            views_dir = os.path.join(folder_paths.get_output_directory(), "views")
            if not os.path.exists(views_dir):
                return web.json_response({"success": True, "views": []})
                
            views = []
            for root, dirs, files in os.walk(views_dir):
                for d in dirs:
                    # Get the full path of the directory
                    full_dir_path = os.path.join(root, d)
                    # Get relative path from the base views directory
                    rel_path = os.path.relpath(full_dir_path, views_dir)
                    # Using forward slashes for consistency in the frontend
                    rel_path = rel_path.replace(os.sep, '/')
                    views.append(rel_path)
                    
            views.sort()
            return web.json_response({"success": True, "views": views})
        except Exception as e:
            logger.error(f"Error getting views list: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_view_image(self, request: web.Request) -> web.Response:
        """Get an alternative view image for a LoRA"""
        import os
        import mimetypes
        import folder_paths
        try:
            view_name = request.query.get("view")
            lora_name = request.query.get("lora")
            
            if not view_name or not lora_name:
                return web.Response(text="View and lora parameters are required", status=400)
                
            # Safely resolve path to avoid directory traversal
            views_dir = os.path.join(folder_paths.get_output_directory(), "views")
            target_view_dir = os.path.normpath(os.path.join(views_dir, view_name))
            
            if not target_view_dir.startswith(os.path.normpath(views_dir)):
                return web.Response(text="Invalid view parameter", status=400)
                
            if not os.path.exists(target_view_dir):
                return web.Response(text="View not found", status=404)
                
            # Extract base name without extension from lora_name
            base_name_full = os.path.splitext(lora_name)[0]
            base_name_flat = os.path.basename(base_name_full)
            
            # Look for common image extensions
            extensions = ['.png', '.jpg', '.jpeg', '.webp', '.gif']
            
            # We'll try to find the image in two ways:
            # 1. Matching the exact path structure (e.g. views/ViewName/subfolder/my_lora.png)
            # 2. Stripping the path and just looking in the root of the view (e.g. views/ViewName/my_lora.png)
            search_names = [(base_name_full, os.path.dirname(os.path.join(target_view_dir, base_name_full)))]
            if base_name_flat != base_name_full:
                search_names.append((base_name_flat, target_view_dir))
                
            # First, try to find an exact match
            for search_name, _ in search_names:
                for ext in extensions:
                    image_path = os.path.join(target_view_dir, f"{search_name}{ext}")
                    if os.path.exists(image_path):
                        content_type, _ = mimetypes.guess_type(image_path)
                        return web.FileResponse(image_path, headers={'Content-Type': content_type or 'application/octet-stream'})
            
            # Second, if no exact match is found, try to find a prefix match
            # This handles cases where ComfyUI appends suffixes like _0001 to generated images
            for search_name, search_dir in search_names:
                if not os.path.exists(search_dir):
                    continue
                    
                target_prefix = os.path.basename(search_name) + "_"
                target_prefix_alt = os.path.basename(search_name) + " " # Sometimes spaces instead of underscores
                
                try:
                    for filename in os.listdir(search_dir):
                        if filename.startswith(target_prefix) or filename.startswith(target_prefix_alt) or filename.startswith(os.path.basename(search_name) + "."):
                            # Check if it has a valid image extension
                            if any(filename.lower().endswith(ext) for ext in extensions):
                                image_path = os.path.join(search_dir, filename)
                                content_type, _ = mimetypes.guess_type(image_path)
                                return web.FileResponse(image_path, headers={'Content-Type': content_type or 'application/octet-stream'})
                except OSError:
                    pass
                    
            return web.Response(text="Image not found for this LoRA in the selected view", status=404)
            
        except Exception as e:
            logger.error(f"Error getting view image: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_random_loras(self, request: web.Request) -> web.Response:
        """Get random LoRAs based on filters and strength ranges"""
        try:
            json_data = await request.json()

            # Parse parameters
            count = json_data.get("count", 5)
            count_min = json_data.get("count_min")
            count_max = json_data.get("count_max")
            model_strength_min = float(json_data.get("model_strength_min", 0.0))
            model_strength_max = float(json_data.get("model_strength_max", 1.0))
            use_same_clip_strength = json_data.get("use_same_clip_strength", True)
            clip_strength_min = float(json_data.get("clip_strength_min", 0.0))
            clip_strength_max = float(json_data.get("clip_strength_max", 1.0))
            locked_loras = json_data.get("locked_loras", [])
            pool_config = json_data.get("pool_config")
            use_recommended_strength = json_data.get("use_recommended_strength", False)
            recommended_strength_scale_min = float(
                json_data.get("recommended_strength_scale_min", 0.5)
            )
            recommended_strength_scale_max = float(
                json_data.get("recommended_strength_scale_max", 1.0)
            )

            # Determine target count
            if count_min is not None and count_max is not None:
                import random

                target_count = random.randint(count_min, count_max)
            else:
                target_count = count

            # Validate parameters
            if target_count < 1 or target_count > 100:
                return web.json_response(
                    {"success": False, "error": "Count must be between 1 and 100"},
                    status=400,
                )

            if model_strength_min < -10 or model_strength_max > 10:
                return web.json_response(
                    {
                        "success": False,
                        "error": "Model strength must be between -10 and 10",
                    },
                    status=400,
                )

            # Get random LoRAs from service
            result_loras = await self.service.get_random_loras(
                count=target_count,
                model_strength_min=model_strength_min,
                model_strength_max=model_strength_max,
                use_same_clip_strength=use_same_clip_strength,
                clip_strength_min=clip_strength_min,
                clip_strength_max=clip_strength_max,
                locked_loras=locked_loras,
                pool_config=pool_config,
                use_recommended_strength=use_recommended_strength,
                recommended_strength_scale_min=recommended_strength_scale_min,
                recommended_strength_scale_max=recommended_strength_scale_max,
            )

            return web.json_response(
                {"success": True, "loras": result_loras, "count": len(result_loras)}
            )

        except ValueError as e:
            logger.error(f"Invalid parameter for random LoRAs: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=400)
        except Exception as e:
            logger.error(f"Error getting random LoRAs: {e}", exc_info=True)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_cycler_list(self, request: web.Request) -> web.Response:
        """Get filtered and sorted LoRA list for cycler widget"""
        try:
            json_data = await request.json()

            # Parse parameters
            pool_config = json_data.get("pool_config")
            sort_by = json_data.get("sort_by", "filename")

            # Get cycler list from service
            lora_list = await self.service.get_cycler_list(
                pool_config=pool_config,
                sort_by=sort_by
            )

            return web.json_response(
                {"success": True, "loras": lora_list, "count": len(lora_list)}
            )

        except Exception as e:
            logger.error(f"Error getting cycler list: {e}", exc_info=True)
            return web.json_response({"success": False, "error": str(e)}, status=500)

    async def get_trigger_words(self, request: web.Request) -> web.Response:
        """Get trigger words for specified LoRA models"""
        try:
            json_data = await request.json()
            lora_names = json_data.get("lora_names", [])
            node_ids = json_data.get("node_ids", [])

            all_trigger_words = []
            for lora_name in lora_names:
                _, trigger_words = get_lora_info(lora_name)
                all_trigger_words.extend(trigger_words)

            # Format the trigger words
            trigger_words_text = (
                ",, ".join(all_trigger_words) if all_trigger_words else ""
            )

            # Send update to all connected trigger word toggle nodes
            for entry in node_ids:
                node_identifier = entry
                graph_identifier = None
                if isinstance(entry, dict):
                    node_identifier = entry.get("node_id")
                    graph_identifier = entry.get("graph_id")

                try:
                    parsed_node_id = int(node_identifier)
                except (TypeError, ValueError):
                    parsed_node_id = node_identifier

                payload = {"id": parsed_node_id, "message": trigger_words_text}

                if graph_identifier is not None:
                    payload["graph_id"] = str(graph_identifier)

                PromptServer.instance.send_sync("trigger_word_update", payload)

            return web.json_response({"success": True})

        except Exception as e:
            logger.error(f"Error getting trigger words: {e}")
            return web.json_response({"success": False, "error": str(e)}, status=500)
