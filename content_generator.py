#!/usr/bin/env python3
"""
Content Generator CLI for GrokProxy

Generate images and videos using Grok through the proxy.

Usage:
    python content_generator.py image "a beautiful sunset"
    python content_generator.py video "time-lapse of clouds" --duration 10
    python content_generator.py batch prompts.txt --type image
"""

import sys
import os
import time
import json
import argparse
import requests
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from observability.colored_logging import setup_colored_logging, get_colored_logger, log_success, log_error

setup_colored_logging(level="INFO")
logger = get_colored_logger(__name__)


class ContentGenerator:
    """CLI tool for generating content via GrokProxy."""
    
    def __init__(self, proxy_url: str = None, api_key: str = None):
        self.proxy_url = proxy_url or os.getenv("PROXY_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("API_KEY", "Bcmoney69$")
        self.output_dir = Path("generated_content")
        self.output_dir.mkdir(exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def generate_image(
        self,
        prompt: str,
        style: str = "photorealistic",
        save: bool = True
    ) -> Dict:
        """Generate a single image."""
        logger.info(f"Generating image: {prompt[:60]}...")
        
        enhanced_prompt = self._enhance_prompt(prompt, style)
        
        try:
            response = self.session.post(
                f"{self.proxy_url}/v1/chat/completions",
                json={
                    "model": "grok-3",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Generate an image: {enhanced_prompt}"
                        }
                    ],
                    "temperature": 0.7
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            
            if save:
                self._save_result(result, prompt, "image")
            
            log_success(logger, "Image generated", prompt=prompt[:40])
            return result
            
        except Exception as e:
            log_error(logger, "Image generation failed", error=e)
            return {"error": str(e)}
    
    def generate_video(
        self,
        prompt: str,
        duration: int = 5,
        save: bool = True
    ) -> Dict:
        """Generate a video from text."""
        logger.info(f"Generating {duration}s video: {prompt[:60]}...")
        
        try:
            response = self.session.post(
                f"{self.proxy_url}/v1/chat/completions",
                json={
                    "model": "grok-3",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Generate a {duration}-second video: {prompt}"
                        }
                    ],
                    "temperature": 0.8
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            
            if save:
                self._save_result(result, prompt, "video")
            
            log_success(logger, "Video generated", prompt=prompt[:40], duration=duration)
            return result
            
        except Exception as e:
            log_error(logger, "Video generation failed", error=e)
            return {"error": str(e)}
    
    def batch_generate(
        self,
        prompts: List[str],
        content_type: str = "image",
        delay: float = 2.0,
        **kwargs
    ) -> List[Dict]:
        """Generate multiple items."""
        logger.info(f"Batch generating {len(prompts)} {content_type}(s)...")
        
        results = []
        for i, prompt in enumerate(prompts, 1):
            logger.info(f"Processing {i}/{len(prompts)}: {prompt[:50]}...")
            
            if content_type == "image":
                result = self.generate_image(prompt, **kwargs)
            elif content_type == "video":
                result = self.generate_video(prompt, **kwargs)
            else:
                logger.error(f"Unknown content type: {content_type}")
                continue
            
            results.append({
                "prompt": prompt,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })
            
            if i < len(prompts):
                time.sleep(delay)
        
        # Save batch results
        batch_file = self.output_dir / f"batch_{content_type}_{int(time.time())}.json"
        with open(batch_file, "w") as f:
            json.dump(results, f, indent=2)
        
        log_success(logger, "Batch complete", count=len(results), file=str(batch_file))
        return results
    
    def _enhance_prompt(self, prompt: str, style: str) -> str:
        """Enhance prompt with style modifiers."""
        style_modifiers = {
            "photorealistic": "photorealistic, ultra detailed, professional photography, 8k",
            "cinematic": "cinematic lighting, dramatic composition, 8k, highly detailed",
            "artistic": "artistic, painterly, masterpiece, trending on artstation",
            "anime": "anime style, vibrant colors, detailed, high quality",
            "cartoon": "cartoon style, colorful, fun, high quality"
        }
        
        modifier = style_modifiers.get(style, "")
        if modifier:
            return f"{prompt}, {modifier}"
        return prompt
    
    def _save_result(self, result: Dict, prompt: str, content_type: str):
        """Save generation result to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prompt = "".join(c for c in prompt[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_prompt = safe_prompt.replace(' ', '_')
        
        filename = f"{content_type}_{timestamp}_{safe_prompt}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, "w") as f:
            json.dump({
                "prompt": prompt,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2)
        
        logger.debug(f"Saved to {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate images and videos using GrokProxy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s image "a beautiful sunset over mountains"
  %(prog)s image "futuristic city" --style cinematic
  %(prog)s video "time-lapse of clouds" --duration 10
  %(prog)s batch prompts.txt --type image --style photorealistic
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Image command
    image_parser = subparsers.add_parser("image", help="Generate an image")
    image_parser.add_argument("prompt", help="Image description")
    image_parser.add_argument("--style", default="photorealistic",
                             choices=["photorealistic", "cinematic", "artistic", "anime", "cartoon"],
                             help="Image style")
    
    # Video command
    video_parser = subparsers.add_parser("video", help="Generate a video")
    video_parser.add_argument("prompt", help="Video description")
    video_parser.add_argument("--duration", type=int, default=5,
                             help="Video duration in seconds")
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch generate from file")
    batch_parser.add_argument("file", help="File with prompts (one per line)")
    batch_parser.add_argument("--type", default="image", choices=["image", "video"],
                             help="Content type to generate")
    batch_parser.add_argument("--style", default="photorealistic",
                             help="Style for images")
    batch_parser.add_argument("--duration", type=int, default=5,
                             help="Duration for videos")
    batch_parser.add_argument("--delay", type=float, default=2.0,
                             help="Delay between requests (seconds)")
    
    # Global options
    parser.add_argument("--proxy-url", default="http://localhost:8000",
                       help="GrokProxy URL")
    parser.add_argument("--api-key", help="API key (or set API_KEY env var)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize generator
    generator = ContentGenerator(
        proxy_url=args.proxy_url,
        api_key=args.api_key
    )
    
    # Execute command
    if args.command == "image":
        result = generator.generate_image(args.prompt, style=args.style)
        print(json.dumps(result, indent=2))
    
    elif args.command == "video":
        result = generator.generate_video(args.prompt, duration=args.duration)
        print(json.dumps(result, indent=2))
    
    elif args.command == "batch":
        # Read prompts from file
        with open(args.file) as f:
            prompts = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Loaded {len(prompts)} prompts from {args.file}")
        
        kwargs = {}
        if args.type == "image":
            kwargs["style"] = args.style
        elif args.type == "video":
            kwargs["duration"] = args.duration
        
        results = generator.batch_generate(
            prompts,
            content_type=args.type,
            delay=args.delay,
            **kwargs
        )
        
        print(f"\nGenerated {len(results)} {args.type}(s)")
        print(f"Results saved to: {generator.output_dir}")


if __name__ == "__main__":
    main()
