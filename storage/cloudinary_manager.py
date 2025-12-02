"""
Cloudinary integration for organized image storage.

Automatically uploads generated images to Cloudinary with proper organization,
tagging, and metadata.
"""

import os
import logging
import hashlib
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path

try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

logger = logging.getLogger(__name__)


class CloudinaryManager:
    """
    Manage image uploads to Cloudinary with organization.
    
    Features:
    - Automatic folder organization by date/type
    - Tagging with prompt keywords
    - Metadata storage
    - Duplicate detection
    - Batch operations
    """
    
    def __init__(
        self,
        cloud_name: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        enabled: bool = True
    ):
        """
        Initialize Cloudinary manager.
        
        Args:
            cloud_name: Cloudinary cloud name
            api_key: Cloudinary API key
            api_secret: Cloudinary API secret
            enabled: Whether Cloudinary is enabled
        """
        self.enabled = enabled and CLOUDINARY_AVAILABLE
        
        if not CLOUDINARY_AVAILABLE:
            logger.warning("Cloudinary library not installed. Run: pip install cloudinary")
            self.enabled = False
            return
        
        # Get credentials from args or environment
        self.cloud_name = cloud_name or os.getenv("CLOUDINARY_CLOUD_NAME")
        self.api_key = api_key or os.getenv("CLOUDINARY_API_KEY")
        self.api_secret = api_secret or os.getenv("CLOUDINARY_API_SECRET")
        
        if not all([self.cloud_name, self.api_key, self.api_secret]):
            logger.warning("Cloudinary credentials not configured. Set CLOUDINARY_* env vars.")
            self.enabled = False
            return
        
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=self.cloud_name,
            api_key=self.api_key,
            api_secret=self.api_secret,
            secure=True
        )
        
        logger.info(f"✓ Cloudinary configured: {self.cloud_name}")
    
    def upload_image(
        self,
        image_path: str,
        prompt: str,
        folder: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        public_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Upload image to Cloudinary.
        
        Args:
            image_path: Path to image file or URL
            prompt: Generation prompt
            folder: Cloudinary folder (auto-generated if None)
            tags: List of tags
            metadata: Additional metadata
            public_id: Custom public ID
        
        Returns:
            Upload result dict or None if failed
        """
        if not self.enabled:
            logger.debug("Cloudinary not enabled, skipping upload")
            return None
        
        try:
            # Generate folder structure: grokproxy/YYYY/MM/DD/type
            if not folder:
                now = datetime.now()
                folder = f"grokproxy/{now.year}/{now.month:02d}/{now.day:02d}/images"
            
            # Generate tags from prompt
            if not tags:
                tags = self._extract_tags(prompt)
            
            # Add standard tags
            tags.extend(["grokproxy", "ai-generated"])
            
            # Prepare metadata
            context = {
                "prompt": prompt[:500],  # Cloudinary has limits
                "generated_at": datetime.now().isoformat(),
                "source": "grokproxy"
            }
            if metadata:
                context.update({k: str(v)[:500] for k, v in metadata.items()})
            
            # Generate public_id if not provided
            if not public_id:
                # Use hash of prompt + timestamp for uniqueness
                hash_input = f"{prompt}{datetime.now().isoformat()}"
                hash_id = hashlib.md5(hash_input.encode()).hexdigest()[:12]
                public_id = f"img_{hash_id}"
            
            # Upload
            logger.info(f"Uploading to Cloudinary: {folder}/{public_id}")
            
            result = cloudinary.uploader.upload(
                image_path,
                folder=folder,
                public_id=public_id,
                tags=tags,
                context=context,
                resource_type="image",
                overwrite=False,  # Don't overwrite existing
                unique_filename=True,
                use_filename=False
            )
            
            logger.info(
                f"✓ Uploaded to Cloudinary: {result['public_id']} "
                f"({result['bytes']} bytes, {result['format']})"
            )
            
            return {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "format": result["format"],
                "width": result["width"],
                "height": result["height"],
                "bytes": result["bytes"],
                "created_at": result["created_at"],
                "folder": folder,
                "tags": tags
            }
            
        except Exception as e:
            logger.error(f"Failed to upload to Cloudinary: {e}")
            return None
    
    def upload_video(
        self,
        video_path: str,
        prompt: str,
        folder: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Upload video to Cloudinary."""
        if not self.enabled:
            return None
        
        try:
            # Generate folder
            if not folder:
                now = datetime.now()
                folder = f"grokproxy/{now.year}/{now.month:02d}/{now.day:02d}/videos"
            
            # Tags
            if not tags:
                tags = self._extract_tags(prompt)
            tags.extend(["grokproxy", "ai-generated", "video"])
            
            # Context
            context = {
                "prompt": prompt[:500],
                "generated_at": datetime.now().isoformat(),
                "source": "grokproxy"
            }
            if metadata:
                context.update({k: str(v)[:500] for k, v in metadata.items()})
            
            # Upload
            logger.info(f"Uploading video to Cloudinary: {folder}")
            
            result = cloudinary.uploader.upload(
                video_path,
                folder=folder,
                tags=tags,
                context=context,
                resource_type="video",
                overwrite=False
            )
            
            logger.info(f"✓ Video uploaded: {result['public_id']}")
            
            return {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "format": result["format"],
                "duration": result.get("duration"),
                "bytes": result["bytes"],
                "created_at": result["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Failed to upload video: {e}")
            return None
    
    def batch_upload(
        self,
        files: List[Dict[str, Any]],
        folder: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Upload multiple files.
        
        Args:
            files: List of dicts with 'path', 'prompt', 'type' keys
            folder: Base folder
        
        Returns:
            List of upload results
        """
        results = []
        
        for file_info in files:
            path = file_info["path"]
            prompt = file_info["prompt"]
            file_type = file_info.get("type", "image")
            
            if file_type == "video":
                result = self.upload_video(path, prompt, folder)
            else:
                result = self.upload_image(path, prompt, folder)
            
            if result:
                results.append(result)
        
        logger.info(f"✓ Batch upload complete: {len(results)}/{len(files)} successful")
        return results
    
    def get_image(self, public_id: str) -> Optional[Dict[str, Any]]:
        """Get image details from Cloudinary."""
        if not self.enabled:
            return None
        
        try:
            result = cloudinary.api.resource(public_id, resource_type="image")
            return result
        except Exception as e:
            logger.error(f"Failed to get image {public_id}: {e}")
            return None
    
    def delete_image(self, public_id: str) -> bool:
        """Delete image from Cloudinary."""
        if not self.enabled:
            return False
        
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type="image")
            success = result.get("result") == "ok"
            if success:
                logger.info(f"✓ Deleted from Cloudinary: {public_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to delete {public_id}: {e}")
            return False
    
    def search_images(
        self,
        query: str,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search images by tags or metadata.
        
        Args:
            query: Search query (e.g., "tags:dragon AND folder:grokproxy/*")
            max_results: Maximum results to return
        
        Returns:
            List of matching images
        """
        if not self.enabled:
            return []
        
        try:
            result = cloudinary.Search().expression(query).max_results(max_results).execute()
            return result.get("resources", [])
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_usage_stats(self) -> Optional[Dict[str, Any]]:
        """Get Cloudinary usage statistics."""
        if not self.enabled:
            return None
        
        try:
            result = cloudinary.api.usage()
            return {
                "images": result.get("resources", {}).get("image", {}),
                "videos": result.get("resources", {}).get("video", {}),
                "storage": result.get("storage", {}),
                "bandwidth": result.get("bandwidth", {}),
                "transformations": result.get("transformations", {})
            }
        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return None
    
    def _extract_tags(self, prompt: str, max_tags: int = 10) -> List[str]:
        """Extract relevant tags from prompt."""
        # Simple keyword extraction
        # Remove common words
        stop_words = {
            "a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
            "by", "from", "as", "is", "was", "are", "were", "be", "been"
        }
        
        # Split and clean
        words = prompt.lower().split()
        tags = []
        
        for word in words:
            # Remove punctuation
            word = "".join(c for c in word if c.isalnum() or c == "-")
            
            # Skip if too short or stop word
            if len(word) < 3 or word in stop_words:
                continue
            
            tags.append(word)
            
            if len(tags) >= max_tags:
                break
        
        return tags
    
    def organize_by_date(self, year: int, month: int, day: int) -> str:
        """Generate date-based folder path."""
        return f"grokproxy/{year}/{month:02d}/{day:02d}"
    
    def organize_by_type(self, content_type: str) -> str:
        """Generate type-based folder path."""
        now = datetime.now()
        return f"grokproxy/{now.year}/{now.month:02d}/{content_type}"


# Singleton instance
_cloudinary_manager: Optional[CloudinaryManager] = None


def get_cloudinary_manager() -> CloudinaryManager:
    """Get or create Cloudinary manager singleton."""
    global _cloudinary_manager
    
    if _cloudinary_manager is None:
        _cloudinary_manager = CloudinaryManager()
    
    return _cloudinary_manager
