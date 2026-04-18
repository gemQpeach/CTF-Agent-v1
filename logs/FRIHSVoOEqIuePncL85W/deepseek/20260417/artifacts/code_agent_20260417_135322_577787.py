import requests

def main():
    target_url = "http://10.0.162.114:80/upload"
    session_cookie = "eyJyb2xlIjoidXNlciIsInVzZXJuYW1lIjoidmlld2VyIn0.aeHIGw.HpA_IUiNPjak9MQyWIJ5HygsQIA"
    
    files_to_upload = [
        ("test.txt", "test content")
    ]
    
    session = requests.Session()
    session.cookies.set("session", session_cookie)
    
    for filename, content in files_to_upload:
        try:
            files = {
                'file': (filename, content)
            }
            print(f"[*] Uploading {filename} to {target_url}...")
            response = session.post(target_url, files=files)
            
            print(f"[*] Status Code: {response.status_code}")
            print(f"[*] Response Length: {len(response.text)}")
            print(f"[*] Response Content:\n{response.text}")
            
            if "flag" in response.text.lower() or response.status_code == 200:
                print(f"[+] Successfully uploaded {filename}")
                
        except requests.exceptions.RequestException as e:
            print(f"[-] Error uploading {filename}: {e}")

if __name__ == "__main__":
    main()