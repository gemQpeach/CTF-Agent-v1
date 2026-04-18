import requests
import json

BASE_URL = "http://10.0.162.112:80"
OPENAPI_URL = f"{BASE_URL}/openapi.json"

# Paths to traverse to initialize session and maintain auth state
INIT_PATHS = ["/", "/login", "/docs", "/api", "/openapi.json"]

def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    # Traverse paths to maintain authentication state
    for path in INIT_PATHS:
        url = f"{BASE_URL}{path}"
        try:
            session.get(url, timeout=5, allow_redirects=True)
        except requests.RequestException:
            pass
            
    # Fetch the openapi.json
    try:
        response = session.get(OPENAPI_URL, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        
        print("Full OpenAPI JSON Response:")
        print(json.dumps(json_data, indent=2))
        
        # Extract and print the /jobs POST endpoint definition specifically
        if "paths" in json_data and "/jobs" in json_data["paths"]:
            jobs_post = json_data["paths"]["/jobs"].get("post")
            if jobs_post:
                print("\n--- /jobs POST Endpoint Request Body Definition ---")
                print(json.dumps(jobs_post, indent=2))
            else:
                print("\n/jobs path found, but POST method is missing.")
        else:
            print("\n/jobs path not found in the OpenAPI schema.")
            
    except requests.RequestException as e:
        print(f"Error fetching openapi.json: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")

if __name__ == "__main__":
    main()