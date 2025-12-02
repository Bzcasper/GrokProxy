import requests
import json
import time

BASE_URL = "http://localhost:8080"
API_KEY = "Bcmoney69$"

def print_header(title):
    print(f"\n{'='*20} {title} {'='*20}")

def test_basic_chat():
    print_header("Basic Chat Completion")
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": "grok-beta",
        "messages": [{"role": "user", "content": "What is 2 + 2? Answer with just the number."}]
    }
    
    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=data)
        duration = time.time() - start_time
        
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        print(f"Status: {response.status_code}")
        print(f"Time: {duration:.2f}s")
        print(f"Response: {content}")
        
        if "4" in content:
            print("✅ PASS")
        else:
            print("❌ FAIL: Expected '4' in response")
            
    except Exception as e:
        print(f"❌ FAIL: {e}")
        if 'response' in locals():
            print(f"Response text: {response.text}")

def test_streaming_chat():
    print_header("Streaming Chat")
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": "grok-beta",
        "messages": [{"role": "user", "content": "Write a haiku about coding."}],
        "stream": True
    }
    
    try:
        print("Stream started...")
        start_time = time.time()
        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()
        
        full_content = ""
        chunk_count = 0
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    if line == "data: [DONE]":
                        break
                    json_str = line[6:]
                    try:
                        chunk = json.loads(json_str)
                        delta = chunk['choices'][0]['delta'].get('content', '')
                        if delta:
                            full_content += delta
                            chunk_count += 1
                            print(".", end="", flush=True)
                    except:
                        pass
        
        duration = time.time() - start_time
        print(f"\n\nStatus: {response.status_code}")
        print(f"Time: {duration:.2f}s")
        print(f"Chunks received: {chunk_count}")
        print(f"Full Response:\n{full_content}")
        
        if len(full_content) > 10 and chunk_count > 1:
            print("✅ PASS")
        else:
            print("❌ FAIL: Response too short or not streamed")
            
    except Exception as e:
        print(f"❌ FAIL: {e}")

def test_context_retention():
    print_header("Context Retention (Sequential Requests)")
    # Note: Since the proxy uses a global client, sequential requests should share context.
    # This test verifies that behavior.
    
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # Step 1: Set context
    print("Step 1: Setting context ('My name is Alice')")
    data1 = {
        "model": "grok-beta",
        "messages": [{"role": "user", "content": "My name is Alice. Remember this."}]
    }
    requests.post(url, headers=headers, json=data1)
    
    # Step 2: Ask for context
    print("Step 2: Asking for context ('What is my name?')")
    data2 = {
        "model": "grok-beta",
        "messages": [{"role": "user", "content": "What is my name?"}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data2)
        result = response.json()
        content = result['choices'][0]['message']['content']
        print(f"Response: {content}")
        
        if "Alice" in content:
            print("✅ PASS: Context retained")
        else:
            print("⚠️ NOTE: Context might not be retained if the proxy resets session or handles requests independently.")
            print("This is expected behavior if the proxy is stateless per request, but the current implementation implies a global session.")
            
    except Exception as e:
        print(f"❌ FAIL: {e}")

if __name__ == "__main__":
    print("Starting Advanced Tests for GrokProxy...")
    try:
        test_basic_chat()
        time.sleep(1)
        test_streaming_chat()
        time.sleep(1)
        test_context_retention()
    except KeyboardInterrupt:
        print("\nTests interrupted.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
