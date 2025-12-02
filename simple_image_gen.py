#!/usr/bin/env python3
"""
Simple image generator using GrokProxy API.
No external dependencies required.
"""

import requests
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Configuration
API_BASE_URL = "https://videooo-8gpw.vercel.app"  # Deployed Vercel URL
OUTPUT_DIR = Path("generated_images")

def generate_image(prompt: str, style: str = "cinematic"):
    """Generate an image using the GrokProxy API."""
    
    print(f"\n🎨 Generating image...")
    print(f"📝 Prompt: {prompt}")
    print(f"🎭 Style: {style}")
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Prepare request
    url = f"{API_BASE_URL}/v1/chat/completions"
    
    # Enhanced prompt with style
    enhanced_prompt = f"{prompt}, {style} style, highly detailed, professional quality"
    
    payload = {
        "model": "grok-3",
        "messages": [
            {
                "role": "user",
                "content": f"Generate an image: {enhanced_prompt}"
            }
        ]
    }
    
    try:
        # Make request
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=30)
        latency = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            # Save result
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_prompt = prompt[:50].replace(" ", "_").replace("/", "_")
            filename = f"image_{timestamp}_{safe_prompt}.json"
            filepath = OUTPUT_DIR / filename
            
            with open(filepath, 'w') as f:
                json.dump({
                    "prompt": prompt,
                    "style": style,
                    "enhanced_prompt": enhanced_prompt,
                    "response": data,
                    "timestamp": timestamp,
                    "latency_ms": int(latency * 1000)
                }, f, indent=2)
            
            print(f"\n✅ Success!")
            print(f"⏱️  Latency: {latency:.2f}s")
            print(f"💾 Saved to: {filepath}")
            print(f"\n📄 Response:")
            print(json.dumps(data, indent=2))
            
            return filepath
            
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Request failed: {e}")
        return None
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return None


def main():
    """Main entry point."""
    
    if len(sys.argv) < 2:
        print("Usage: python simple_image_gen.py <prompt> [--style <style>]")
        print("\nExample:")
        print('  python simple_image_gen.py "A dark forest at midnight" --style cinematic')
        print("\nStyles: cinematic, photorealistic, artistic, anime, abstract")
        sys.exit(1)
    
    # Parse arguments
    prompt = sys.argv[1]
    style = "cinematic"
    
    if "--style" in sys.argv:
        style_index = sys.argv.index("--style")
        if style_index + 1 < len(sys.argv):
            style = sys.argv[style_index + 1]
    
    # Generate image
    result = generate_image(prompt, style)
    
    if result:
        print(f"\n🎉 Image generation complete!")
        sys.exit(0)
    else:
        print(f"\n😞 Image generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
