import requests

TARGET_URL = "http://10.0.162.112:80/jobs"

def print_full_response(desc, response):
    print(f"=== {desc} ===")
    print(f"Status Code: {response.status_code}")
    print("Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    print("Body:")
    print(response.text)
    print("=" * 60 + "\n")

def main():
    session = requests.Session()
    
    requests_to_make = [
        {
            "desc": '1. POST with JSON body {"job_type": "back-end"}',
            "method": "POST",
            "json": {"job_type": "back-end"}
        },
        {
            "desc": '2. POST with JSON body {"job_type": "front-end"}',
            "method": "POST",
            "json": {"job_type": "front-end"}
        },
        {
            "desc": '3. POST with JSON body {"job_type": "private"}',
            "method": "POST",
            "json": {"job_type": "private"}
        },
        {
            "desc": '4. POST with JSON body {"job_type": ""}',
            "method": "POST",
            "json": {"job_type": ""}
        },
        {
            "desc": "5. POST with no body and Content-Type: application/json",
            "method": "POST",
            "data": "",
            "headers": {"Content-Type": "application/json"}
        },
        {
            "desc": "6. GET with no parameters",
            "method": "GET"
        }
    ]

    for req in requests_to_make:
        try:
            method = req.get("method", "GET").upper()
            if method == "POST":
                if "json" in req:
                    res = session.post(TARGET_URL, json=req["json"])
                else:
                    res = session.post(TARGET_URL, data=req.get("data", ""), headers=req.get("headers", {}))
            elif method == "GET":
                res = session.get(TARGET_URL)
            else:
                continue
            
            print_full_response(req["desc"], res)
            
        except requests.exceptions.RequestException as e:
            print(f"Error making request '{req['desc']}': {e}\n")

if __name__ == "__main__":
    main()