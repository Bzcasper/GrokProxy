import asyncio
import logging
import sys
from grok_client import GrokClient
from changecookie import ChangeCookie

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def main():
    print("Initializing GrokClient...")
    cookie_manager = ChangeCookie()
    client = GrokClient(cookie_manager=cookie_manager)
    
    print("Sending request...")
    try:
        async for token in client.chat(prompt="Hello", model="grok-3"):
            print(token, end="", flush=True)
        print("\nDone.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
