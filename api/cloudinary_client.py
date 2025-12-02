"""
Cloudinary integration for image storage and CDN delivery.
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from typing import Dict, Any, Optional
from datetime import datetime
import os


class CloudinaryClient:
    """Client for Cloudinary image storage."""
    
    def __init__(
        self,
        cloud_name: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None
    ):
        """
        Initialize Cloudinary client.
        
        Args:
            cloud_name: Cloudinary cloud name
            api_key: Cloudinary API key
            api_secret: Cloudinary API secret
        """
        self.cloud_name = cloud_name or os.getenv("CLOUDINARY_CLOUD_NAME")
        self.api_key = api_key or os.getenv("CLOUDINARY_API_KEY")
        self.api_secret = api_secret or os.getenv("CLOUDINARY_API_SECRET")
        
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=self.cloud_name,
            api_key=self.api_key,
            api_secret=self.api_secret,
            secure=True
        )
    
    def upload_image(
        self,
        image_url: str,
        prompt: str,
        tags: Optional[list] = None,
        folder: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload image to Cloudinary.
        
        Args:
            image_url: URL of image to upload
            prompt: Generation prompt (for metadata)
            tags: List of tags
            folder: Folder path in Cloudinary
            
        Returns:
            Upload result with CDN URL
        """
        # Generate folder path if not provided
        if not folder:
            date_str = datetime.now().strftime("%Y/%m/%d")
            folder = f"grokproxy/images/{date_str}"
        
        # Prepare tags
        upload_tags = tags or []
        upload_tags.extend(["grokproxy", "ai-generated"])
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            image_url,
            folder=folder,
            tags=upload_tags,
            context=f"prompt={prompt}",
            resource_type="image"
        )
        
        return {
            "public_id": result["public_id"],
            "url": result["secure_url"],
            "width": result["width"],
            "height": result["height"],
            "format": result["format"],
            "created_at": result["created_at"]
        }
    
    def upload_video(
        self,
        video_url: str,
        prompt: str,
        tags: Optional[list] = None,
        folder: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload video to Cloudinary.
        
        Args:
            video_url: URL of video to upload
            prompt: Generation prompt (for metadata)
            tags: List of tags
            folder: Folder path in Cloudinary
            
        Returns:
            Upload result with CDN URL
        """
        # Generate folder path if not provided
        if not folder:
            date_str = datetime.now().strftime("%Y/%m/%d")
            folder = f"grokproxy/videos/{date_str}"
        
        # Prepare tags
        upload_tags = tags or []
        upload_tags.extend(["grokproxy", "ai-generated"])
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            video_url,
            folder=folder,
            tags=upload_tags,
            context=f"prompt={prompt}",
            resource_type="video"
        )
        
        return {
            "public_id": result["public_id"],
            "url": result["secure_url"],
            "duration": result.get("duration"),
            "format": result["format"],
            "created_at": result["created_at"]
        }
    
    def get_image_url(
        self,
        public_id: str,
        transformation: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get CDN URL for an image with optional transformations.
        
        Args:
            public_id: Cloudinary public ID
            transformation: Transformation parameters
            
        Returns:
            CDN URL
        """
        return cloudinary.CloudinaryImage(public_id).build_url(
            transformation=transformation,
            secure=True
        )
