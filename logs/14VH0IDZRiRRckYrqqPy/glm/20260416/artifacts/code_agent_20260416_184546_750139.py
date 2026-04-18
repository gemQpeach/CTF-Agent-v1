import requests
import base64
import pickle

TARGET_URL = "http://10.0.162.113:80"

def decode_pref_cookie(cookie_value):
    try:
        missing_padding = len(cookie_value) % 4
        if missing_padding:
            cookie_value += '=' * (4 - missing_padding)
        decoded_bytes = base64.b64decode(cookie_value)
        deserialized = pickle.loads(decoded_bytes)
        return deserialized
    except Exception as e:
        return f"Decode error: {e}"

def print_cookies(session):
    print("\n[+] Current Cookies:")
    if not session.cookies:
        print("  (No cookies)")
    for key, value in session.cookies.items():
        print(f"  {key} = {value}")
        if key.startswith('pref_'):
            decoded = decode_pref_cookie(value)
            print(f"    -> Decoded (Pickle): {decoded}")
    print()

def main():
    session = requests.Session()

    # Step 1: Login
    print("[*] Step 1: Logging in as rootadmin...")
    login_url = f"{TARGET_URL}/login"
    login_data = {"username": "rootadmin", "password": "docpass"}
    
    try:
        resp = session.post(login_url, data=login_data, allow_redirects=True)
        print(f"    Status Code: {resp.status_code}")
        print_cookies(session)
    except Exception as e:
        print(f"    Login request failed: {e}")

    # Step 2: Access /preferences
    print("[*] Step 2: Accessing /preferences...")
    pref_url = f"{TARGET_URL}/preferences"
    
    try:
        resp = session.get(pref_url)
        print(f"    Status Code: {resp.status_code}")
        print("    HTML Content:")
        print(resp.text)
        print_cookies(session)
    except Exception as e:
        print(f"    GET /preferences failed: {e}")

    # Step 3: POST /preferences
    print("[*] Step 3: POSTing to /preferences with theme and language...")
    pref_data = {"theme": "dark", "language": "en"}
    
    try:
        resp = session.post(pref_url, data=pref_data)
        print(f"    Status Code: {resp.status_code}")
        print("    HTML Content:")
        print(resp.text)
        print_cookies(session)
    except Exception as e:
        print(f"    POST /preferences failed: {e}")

if __name__ == "__main__":
    main()