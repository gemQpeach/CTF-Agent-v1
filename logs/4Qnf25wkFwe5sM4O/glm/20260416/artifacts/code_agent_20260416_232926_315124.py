import requests
import json

BASE_URL = "http://10.0.162.112:80"

def print_response(desc, response):
    print(f"=== {desc} ===")
    print(f"Status Code: {response.status_code}")
    print("Response Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    print("Response Body:")
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)
    print("\n" + "="*60 + "\n")

def main():
    session = requests.Session()
    
    requests_to_make = [
        {
            "desc": "1. POST /jobs with JSON body {\"job_type\": \"back-end\"}",
            "method": "POST",
            "url": f"{BASE_URL}/jobs",
            "json": {"job_type": "back-end"}
        },
        {
            "desc": "2. POST /jobs with JSON body {\"job_type\": \"private\"}",
            "method": "POST",
            "url": f"{BASE_URL}/jobs",
            "json": {"job_type": "private"}
        },
        {
            "desc": "3. POST /jobs with JSON body {\"job_type\": \"front-end\"}",
            "method": "POST",
            "url": f"{BASE_URL}/jobs",
            "json": {"job_type": "front-end"}
        },
        {
            "desc": "4. POST /jobs with empty JSON body {}",
            "method": "POST",
            "url": f"{BASE_URL}/jobs",
            "json": {}
        },
        {
            "desc": "5. GET /jobs",
            "method": "GET",
            "url": f"{BASE_URL}/jobs"
        },
        {
            "desc": "6. GET /ping",
            "method": "GET",
            "url": f"{BASE_URL}/ping"
        },
        {
            "desc": "7. GET /jobs?job_type=back-end",
            "method": "GET",
            "url": f"{BASE_URL}/jobs",
            "params": {"job_type": "back-end"}
        }
    ]

    for req in requests_to_make:
        try:
            if req["method"] == "POST":
                res = session.post(req["url"], json=req.get("json"))
            else:
                res = session.get(req["url"], params=req.get("params"))
            
            print_response(req["desc"], res)
        except requests.exceptions.RequestException as e:
            print(f"Error making request {req['desc']}: {e}\n")

if __name__ == "__main__":
    main()