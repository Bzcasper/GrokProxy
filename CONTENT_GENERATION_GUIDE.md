22222222222222222222222# GrokProxy Content Generation Guide

## Image Generation & Image-to-Video Workflows

**Use Case**: Generate images and videos using Grok's capabilities through the proxy without official xAI API access.

---

## 🎨 Image Generation Workflow

### Method 1: Via Chat Completions (Recommended)

Grok can generate images directly through chat by requesting them in the conversation.

```python
import requests

PROXY_URL = "http://localhost:8000"
API_KEY = "Bcmoney69$"  # Your proxy API key

def generate_image(prompt: str, style: str = "photorealistic"):
    """
    Generate an image using Grok through chat.

    Args:
        prompt: Image description
        style: Style hint (photorealistic, artistic, cartoon, etc.)

    Returns:
        Response with image URL
    """
    response = requests.post(
        f"{PROXY_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "grok-3",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful AI that can generate images. When asked to create an image, generate it and provide the image URL."
                },
                {
                    "role": "user",
                    "content": f"Generate a {style} image: {prompt}"
                }
            ],
            "temperature": 0.7
        }
    )

    return response.json()

# Example usage
result = generate_image(
    prompt="A futuristic cityscape at sunset with flying cars",
    style="photorealistic"
)

print(result)
# Extract image URL from response
if "choices" in result:
    content = result["choices"][0]["message"]["content"]
    print(f"Response: {content}")
```

### Method 2: Direct Image Generation Endpoint

If Grok exposes image generation through their web interface, we can proxy it:

```python
def generate_image_direct(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    quality: str = "hd",
    style: str = "vivid"
):
    """
    Generate image using direct endpoint (if available).

    Args:
        prompt: Image description
        width: Image width
        height: Image height
        quality: 'standard' or 'hd'
        style: 'vivid' or 'natural'
    """
    response = requests.post(
        f"{PROXY_URL}/v1/images/generations",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "grok-2-image",
            "prompt": prompt,
            "n": 1,
            "size": f"{width}x{height}",
            "quality": quality,
            "style": style
        }
    )

    return response.json()

# Example
result = generate_image_direct(
    prompt="A majestic dragon flying over mountains",
    quality="hd",
    style="vivid"
)

# Download the image
if "data" in result:
    image_url = result["data"][0]["url"]
    print(f"Image URL: {image_url}")

    # Download
    img_response = requests.get(image_url)
    with open("generated_image.png", "wb") as f:
        f.write(img_response.content)
```

---

## 🎬 Image-to-Video Workflow

### Method 1: Via Chat with Image Input

```python
import base64
from pathlib import Path

def image_to_video(
    image_path: str,
    motion_prompt: str = "smooth camera pan",
    duration: int = 5
):
    """
    Convert image to video using Grok's image-to-video.

    Args:
        image_path: Path to input image
        motion_prompt: Description of desired motion
        duration: Video duration in seconds
    """
    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    response = requests.post(
        f"{PROXY_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "grok-3",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Convert this image to a {duration}-second video with the following motion: {motion_prompt}"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}"
                            }
                        }
                    ]
                }
            ]
        }
    )

    return response.json()

# Example
result = image_to_video(
    image_path="generated_image.png",
    motion_prompt="slow zoom in with slight rotation",
    duration=5
)

print(result)
```

### Method 2: Text-to-Video Direct

```python
def text_to_video(
    prompt: str,
    duration: int = 5,
    fps: int = 24,
    resolution: str = "1080p"
):
    """
    Generate video from text prompt.

    Args:
        prompt: Video description
        duration: Duration in seconds
        fps: Frames per second
        resolution: '720p', '1080p', or '4k'
    """
    response = requests.post(
        f"{PROXY_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "grok-3",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a video generation AI. Generate videos based on text descriptions."
                },
                {
                    "role": "user",
                    "content": f"Generate a {duration}-second {resolution} video at {fps}fps: {prompt}"
                }
            ],
            "temperature": 0.8
        }
    )

    return response.json()

# Example
result = text_to_video(
    prompt="A time-lapse of a flower blooming in a garden",
    duration=10,
    resolution="1080p"
)
```

---

## 🚀 Complete Content Generation Pipeline

### Automated Image + Video Generation

```python
import time
import json
from typing import List, Dict

class ContentGenerator:
    """Automated content generation pipeline using GrokProxy."""

    def __init__(self, proxy_url: str, api_key: str):
        self.proxy_url = proxy_url
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def generate_content_batch(
        self,
        prompts: List[str],
        content_type: str = "image",
        **kwargs
    ) -> List[Dict]:
        """
        Generate multiple pieces of content.

        Args:
            prompts: List of prompts
            content_type: 'image' or 'video'
            **kwargs: Additional parameters

        Returns:
            List of results
        """
        results = []

        for i, prompt in enumerate(prompts):
            print(f"Generating {content_type} {i+1}/{len(prompts)}: {prompt[:50]}...")

            if content_type == "image":
                result = self.generate_image(prompt, **kwargs)
            elif content_type == "video":
                result = self.text_to_video(prompt, **kwargs)
            else:
                raise ValueError(f"Unknown content type: {content_type}")

            results.append({
                "prompt": prompt,
                "result": result,
                "timestamp": time.time()
            })

            # Rate limiting
            time.sleep(2)

        return results

    def generate_image(self, prompt: str, **kwargs) -> Dict:
        """Generate single image."""
        response = self.session.post(
            f"{self.proxy_url}/v1/chat/completions",
            json={
                "model": "grok-3",
                "messages": [
                    {
                        "role": "user",
                        "content": f"Generate an image: {prompt}"
                    }
                ],
                **kwargs
            }
        )
        return response.json()

    def text_to_video(self, prompt: str, duration: int = 5, **kwargs) -> Dict:
        """Generate video from text."""
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
                **kwargs
            }
        )
        return response.json()

    def image_to_video_pipeline(
        self,
        image_prompts: List[str],
        motion_prompts: List[str],
        duration: int = 5
    ) -> List[Dict]:
        """
        Complete pipeline: Generate images, then convert to videos.

        Args:
            image_prompts: Prompts for image generation
            motion_prompts: Motion descriptions for each image
            duration: Video duration

        Returns:
            List of video results
        """
        results = []

        # Step 1: Generate images
        print("Step 1: Generating images...")
        images = self.generate_content_batch(image_prompts, content_type="image")

        # Step 2: Convert to videos
        print("\nStep 2: Converting images to videos...")
        for i, (img_result, motion) in enumerate(zip(images, motion_prompts)):
            print(f"Creating video {i+1}/{len(images)}...")

            # Extract image URL from result
            # (This depends on Grok's response format)
            image_url = self._extract_image_url(img_result["result"])

            if image_url:
                # Convert to video
                video_result = self.image_to_video(image_url, motion, duration)
                results.append({
                    "image_prompt": img_result["prompt"],
                    "motion_prompt": motion,
                    "image_url": image_url,
                    "video_result": video_result
                })

            time.sleep(2)

        return results

    def _extract_image_url(self, response: Dict) -> str:
        """Extract image URL from Grok response."""
        # Parse response to find image URL
        # This is a placeholder - adjust based on actual response format
        if "choices" in response:
            content = response["choices"][0]["message"]["content"]
            # Look for URL patterns
            import re
            urls = re.findall(r'https?://[^\s]+', content)
            if urls:
                return urls[0]
        return None

    def save_results(self, results: List[Dict], output_file: str):
        """Save results to JSON file."""
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {output_file}")

# Example usage
if __name__ == "__main__":
    generator = ContentGenerator(
        proxy_url="http://localhost:8000",
        api_key="Bcmoney69$"
    )

    # Generate batch of images
    image_prompts = [
        "A serene mountain landscape at dawn",
        "A bustling futuristic city street",
        "An underwater coral reef with colorful fish",
        "A cozy cabin in a snowy forest"
    ]

    results = generator.generate_content_batch(
        prompts=image_prompts,
        content_type="image"
    )

    generator.save_results(results, "generated_images.json")

    # Image-to-video pipeline
    motion_prompts = [
        "slow pan from left to right",
        "zoom in on the center",
        "gentle floating motion",
        "slow zoom out"
    ]

    video_results = generator.image_to_video_pipeline(
        image_prompts=image_prompts,
        motion_prompts=motion_prompts,
        duration=5
    )

    generator.save_results(video_results, "generated_videos.json")
```

---

## 💡 Tips & Tricks

### 1. Optimize Image Prompts

```python
def optimize_prompt(base_prompt: str, style: str = "cinematic") -> str:
    """
    Enhance prompts for better image quality.

    Style presets:
    - cinematic: Movie-like quality
    - photorealistic: Photo-like
    - artistic: Painterly style
    - anime: Anime/manga style
    """
    style_modifiers = {
        "cinematic": "cinematic lighting, dramatic composition, 8k, highly detailed",
        "photorealistic": "photorealistic, ultra detailed, professional photography, 8k",
        "artistic": "artistic, painterly, masterpiece, trending on artstation",
        "anime": "anime style, vibrant colors, detailed, high quality"
    }

    modifier = style_modifiers.get(style, "")
    return f"{base_prompt}, {modifier}"

# Example
prompt = optimize_prompt(
    "A dragon in a cave",
    style="cinematic"
)
# Result: "A dragon in a cave, cinematic lighting, dramatic composition, 8k, highly detailed"
```

### 2. Batch Processing with Progress Tracking

```python
from tqdm import tqdm

def batch_generate_with_progress(prompts: List[str]):
    """Generate content with progress bar."""
    results = []

    for prompt in tqdm(prompts, desc="Generating content"):
        result = generate_image(prompt)
        results.append(result)
        time.sleep(1)  # Rate limiting

    return results
```

### 3. Error Handling & Retries

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def generate_with_retry(prompt: str):
    """Generate with automatic retries on failure."""
    response = requests.post(
        f"{PROXY_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "grok-3",
            "messages": [{"role": "user", "content": f"Generate: {prompt}"}]
        },
        timeout=60
    )
    response.raise_for_status()
    return response.json()
```

### 4. Download and Save Media

```python
import os
from urllib.parse import urlparse

def download_media(url: str, output_dir: str = "output"):
    """Download image or video from URL."""
    os.makedirs(output_dir, exist_ok=True)

    # Get filename from URL
    filename = os.path.basename(urlparse(url).path)
    if not filename:
        filename = f"media_{int(time.time())}.png"

    output_path = os.path.join(output_dir, filename)

    response = requests.get(url, stream=True)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"Downloaded: {output_path}")
    return output_path
```

### 5. Parallel Generation

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def parallel_generate(prompts: List[str], max_workers: int = 3):
    """Generate multiple items in parallel."""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_prompt = {
            executor.submit(generate_image, prompt): prompt
            for prompt in prompts
        }

        for future in tqdm(as_completed(future_to_prompt), total=len(prompts)):
            prompt = future_to_prompt[future]
            try:
                result = future.result()
                results.append({"prompt": prompt, "result": result})
            except Exception as e:
                print(f"Error generating '{prompt}': {e}")

    return results
```

---

## 📊 Monitoring & Analytics

### Track Generation Costs

```python
def estimate_cost(num_images: int, num_videos: int):
    """
    Estimate generation costs.

    Note: Adjust prices based on actual xAI pricing
    """
    # Example pricing (adjust as needed)
    IMAGE_COST = 0.04  # per image
    VIDEO_COST = 0.10  # per second

    image_cost = num_images * IMAGE_COST
    video_cost = num_videos * VIDEO_COST
    total_cost = image_cost + video_cost

    print(f"Estimated costs:")
    print(f"  Images: {num_images} × ${IMAGE_COST} = ${image_cost:.2f}")
    print(f"  Videos: {num_videos}s × ${VIDEO_COST} = ${video_cost:.2f}")
    print(f"  Total: ${total_cost:.2f}")

    return total_cost
```

### Query Generation History

```python
import psycopg2

def get_generation_stats(database_url: str):
    """Get statistics from database."""
    conn = psycopg2.connect(database_url)
    cur = conn.cursor()

    # Image generations
    cur.execute("""
        SELECT COUNT(*), AVG(latency_ms)
        FROM image_generations
        WHERE created_at >= now() - interval '24 hours'
    """)
    img_count, img_avg_latency = cur.fetchone()

    # Total cost
    cur.execute("""
        SELECT SUM(total_cost_micro_usd) / 1000000.0
        FROM token_usage
        WHERE created_at >= now() - interval '24 hours'
    """)
    total_cost = cur.fetchone()[0] or 0

    print(f"Last 24 hours:")
    print(f"  Images generated: {img_count}")
    print(f"  Avg latency: {img_avg_latency:.0f}ms")
    print(f"  Total cost: ${total_cost:.2f}")

    conn.close()
```

---

## 🎯 Use Cases

### 1. Social Media Content

```python
def generate_social_media_content(topic: str):
    """Generate images for social media posts."""
    prompts = [
        f"{topic} - Instagram square format, vibrant colors",
        f"{topic} - Twitter header, wide format",
        f"{topic} - Facebook post, engaging composition"
    ]

    return batch_generate_with_progress(prompts)
```

### 2. Video Thumbnails

```python
def generate_thumbnail(video_title: str):
    """Generate eye-catching video thumbnail."""
    prompt = optimize_prompt(
        f"YouTube thumbnail for: {video_title}, bold text, high contrast, attention-grabbing",
        style="cinematic"
    )

    return generate_image(prompt)
```

### 3. Product Mockups

```python
def generate_product_mockup(product_name: str, setting: str):
    """Generate product in various settings."""
    prompt = f"{product_name} in {setting}, professional product photography, clean background, studio lighting"
    return generate_image(prompt)
```

---

## 📝 Best Practices

1. **Be Specific**: More detailed prompts = better results
2. **Use Style Keywords**: "cinematic", "photorealistic", "8k", "detailed"
3. **Rate Limit**: Add delays between requests to avoid overwhelming the proxy
4. **Error Handling**: Always use try/except and retries
5. **Save Results**: Store prompts and results for future reference
6. **Monitor Costs**: Track usage in the database
7. **Batch Processing**: Generate multiple items efficiently
8. **Quality Control**: Review and filter results

---

## 🚨 Troubleshooting

### Issue: Images not generating

- Check if Grok supports image generation in chat
- Verify prompt format
- Check proxy logs: `tail -f /tmp/grokproxy.log`

### Issue: Slow generation

- Reduce batch size
- Increase delays between requests
- Check session health: `curl http://localhost:8000/health`

### Issue: Poor quality results

- Enhance prompts with style keywords
- Try different temperature values (0.7-0.9)
- Use the `optimize_prompt()` function

---

**Your GrokProxy is ready for content generation!** 🎨🎬

Use these scripts and workflows to create images and videos at scale without needing direct xAI API access.
