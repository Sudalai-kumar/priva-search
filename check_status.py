import httpx
import json

def check_status():
    scan_id = "24d2fb2b-7a83-4ab6-bb51-26f132b1e295"
    url = f"http://localhost:8000/scan/{scan_id}/status"
    
    try:
        resp = httpx.get(url, timeout=10.0)
        print(f"Status: {resp.status_code}")
        print(json.dumps(resp.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_status()
