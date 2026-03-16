import asyncio
import httpx
import os
import sys

async def test_connectivity():
    print("--- Connectivity Test ---")
    
    # 1. Test Internet Connectivity (Google)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://www.google.com")
            print(f"✅ Internet (Google): Accessible ({resp.status_code})")
    except Exception as e:
        print(f"❌ Internet (Google): Failed ({e})")

    # 2. Test Discovery API (DuckDuckGo)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://api.duckduckgo.com/?q=test&format=json")
            print(f"✅ Discovery (DuckDuckGo): Accessible ({resp.status_code})")
    except Exception as e:
        print(f"❌ Discovery (DuckDuckGo): Failed ({e})")

    # 3. Test Ollama Accessibility
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    print(f"Testing Ollama at: {ollama_url}")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                print(f"✅ Ollama: Accessible ({resp.status_code})")
                data = resp.json()
                models = [m['name'] for m in data.get('models', [])]
                print(f"   Available models: {models}")
                if "qwen2.5:7b" in models:
                    print(f"   ✅ Model 'qwen2.5:7b' found.")
                else:
                    print(f"   ⚠️ Model 'qwen2.5:7b' NOT found in Ollama.")
            else:
                print(f"❌ Ollama: Accessible but returned error ({resp.status_code})")
    except Exception as e:
        print(f"❌ Ollama: Failed to connect ({e})")
        print("   If you are on Windows, ensure Ollama is running and OLLAMA_HOST is set to 0.0.0.0 if needed,")
        print("   or just ensure 'host.docker.internal' is resolvable.")

if __name__ == "__main__":
    asyncio.run(test_connectivity())
