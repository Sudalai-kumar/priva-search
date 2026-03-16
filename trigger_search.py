import httpx
import json

def trigger_search():
    url = "http://localhost:8000/search"
    params = {"q": "Netflix"}
    
    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    trigger_search()
