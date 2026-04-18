import requests
import json

BASE_URL = "http://10.0.162.112:80"

def main():
    session = requests.Session()
    openapi_url = f"{BASE_URL}/openapi.json"
    
    try:
        response = session.get(openapi_url, timeout=10)
        response.raise_for_status()
        
        openapi_spec = response.json()
        
        print("Full OpenAPI Specification:")
        print(json.dumps(openapi_spec, indent=4))
        
        if "paths" in openapi_spec and "/jobs" in openapi_spec["paths"]:
            print("\n[+] POST /jobs Request Body Schema:")
            post_jobs = openapi_spec["paths"]["/jobs"].get("post", {})
            request_body = post_jobs.get("requestBody", {})
            print(json.dumps(request_body, indent=4))
        else:
            print("\n[-] POST /jobs endpoint not found in the OpenAPI spec.")
            
    except requests.exceptions.RequestException as e:
        print(f"[-] Request Error: {e}")
    except json.JSONDecodeError as e:
        print(f"[-] JSON Decode Error: {e}")
    except Exception as e:
        print(f"[-] Unexpected Error: {e}")

if __name__ == "__main__":
    main()