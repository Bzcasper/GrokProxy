import requests
import json
import time
import re

BASE_URL = "http://localhost:8080"
API_KEY = "Bcmoney69$"

def chat(messages, model="grok-beta"):
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": model,
        "messages": messages,
        "stream": False 
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Error: {response.text}")
        response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def main():
    messages = []
    
    # 1. Generate Story
    print("\n=== 1. Generating DIY Story ===")
    prompt1 = "Create a short, engaging storyline for a DIY project video about building a 'Smart Mirror'. Include 3 distinct scenes."
    print(f"Prompt: {prompt1}")
    messages.append({"role": "user", "content": prompt1})
    story = chat(messages)
    messages.append({"role": "assistant", "content": story})
    print(f"\nStory:\n{story}\n")
    
    # 2. Chunk into prompts
    print("\n=== 2. Generating Image Prompts ===")
    prompt2 = "Based on this story, create 3 detailed image generation prompts, one for each scene. Return ONLY the prompts, separated by '---'."
    print(f"Prompt: {prompt2}")
    messages.append({"role": "user", "content": prompt2})
    prompts_text = chat(messages)
    messages.append({"role": "assistant", "content": prompts_text})
    print(f"\nPrompts Text:\n{prompts_text}\n")
    
    prompts = [p.strip() for p in prompts_text.split('---') if p.strip()]
    print(f"Found {len(prompts)} prompts.")
    
    # 3. Generate Images
    print("\n=== 3. Generating Images ===")
    for i, prompt in enumerate(prompts):
        print(f"\nGenerating image for scene {i+1}...")
        print(f"Prompt: {prompt}")
        
        img_prompt = f"Generate an image for this scene: {prompt}"
        messages.append({"role": "user", "content": img_prompt})
        
        try:
            response_content = chat(messages)
            messages.append({"role": "assistant", "content": response_content})
            
            print(f"Response snippet: {response_content[:200]}...")
            
            if "![" in response_content or "[Image Attachment" in response_content:
                print("✅ Image generated successfully")
                # Extract URL if possible
                match = re.search(r'!\[.*?\]\((.*?)\)', response_content)
                if match:
                    img_path = match.group(1)
                    print(f"Image Path: {img_path}")
                    
                    # Construct full URL
                    full_img_url = f"https://assets.grok.com/{img_path}"
                    print(f"Full Image URL: {full_img_url}")
                    
                    proxy_img_url = f"{BASE_URL}/v1/images/proxy?url={full_img_url}"
                    print(f"Downloading via Proxy: {proxy_img_url}")
                    
                    try:
                        img_resp = requests.get(proxy_img_url, stream=True)
                        if img_resp.status_code == 200:
                            filename = f"scene_{i+1}.jpg"
                            with open(filename, 'wb') as f:
                                for chunk in img_resp.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            print(f"✅ Saved image to {filename}")
                        else:
                            print(f"❌ Failed to download image: {img_resp.status_code}")
                    except Exception as e:
                        print(f"❌ Error downloading: {e}")
            else:
                print("❌ No image found in response")
                print(f"Full response content: {response_content}")
                
        except Exception as e:
            print(f"❌ Error generating image: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    main()
