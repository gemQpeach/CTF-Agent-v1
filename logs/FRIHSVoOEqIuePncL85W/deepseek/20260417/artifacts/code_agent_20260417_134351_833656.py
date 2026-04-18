import requests
import os

TARGET_URL = "http://10.0.162.114:80/upload"
SESSION_COOKIE = "eyJyb2xlIjoidXNlciIsInVzZXJuYW1lIjoidmlld2VyIn0.aeHIGw.HpA_IUiNPjak9MQyWIJ5HygsQIA"
TEST_FILENAME = "test.txt"
TEST_CONTENT = "test content"

def main():
    try:
        with open(TEST_FILENAME, "w", encoding="utf-8") as f:
            f.write(TEST_CONTENT)
        print(f"[*] Created test file: {TEST_FILENAME}")

        session = requests.Session()
        session.cookies.set("session", SESSION_COOKIE)
        print(f"[*] Session cookie set")

        with open(TEST_FILENAME, "rb") as f:
            files = {"file": (TEST_FILENAME, f, "text/plain")}
            print(f"[*] Uploading {TEST_FILENAME} to {TARGET_URL}...")
            response = session.post(TARGET_URL, files=files)

        print(f"[*] Status Code: {response.status_code}")
        print(f"[*] Response Length: {len(response.text)}")
        print(f"[*] Response Content:\n{response.text}")

    except requests.exceptions.RequestException as e:
        print(f"[!] Request failed: {e}")
    except IOError as e:
        print(f"[!] File operation failed: {e}")
    finally:
        if os.path.exists(TEST_FILENAME):
            os.remove(TEST_FILENAME)
            print(f"[*] Cleaned up test file: {TEST_FILENAME}")

if __name__ == "__main__":
    main()