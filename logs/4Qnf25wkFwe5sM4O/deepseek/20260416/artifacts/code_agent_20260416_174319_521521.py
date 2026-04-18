import requests
import json

def main():
    base_url = "http://10.0.162.112:80"
    paths = ["/jobs"]
    
    session = requests.Session()
    
    # If authentication is required, configure it here
    # login_url = base_url + "/login"
    # login_data = {"username": "admin", "password": "admin"}
    # session.post(login_url, data=login_data)
    
    for path in paths:
        url = base_url + path
        try:
            print(f"[*] Requesting: POST {url}")
            response = session.post(url)
            print(f"[*] Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"[*] Full Response JSON:\n{json.dumps(data, indent=4)}")
                    
                    if isinstance(data, list):
                        for item in data:
                            print("-" * 60)
                            print(f"ID          : {item.get('id')}")
                            print(f"Name        : {item.get('name')}")
                            print(f"Type        : {item.get('type')}")
                            print(f"Description : {item.get('description')}")
                            
                            desc = str(item.get('description', ''))
                            if 'flag' in desc.lower() or 'ctf' in desc.lower():
                                print(f"\n[+] FLAG FOUND in description: {desc}")
                    elif isinstance(data, dict):
                        print("-" * 60)
                        print(f"Data: {json.dumps(data, indent=4)}")
                        desc = str(data.get('description', ''))
                        if 'flag' in desc.lower() or 'ctf' in desc.lower():
                            print(f"\n[+] FLAG FOUND in description: {desc}")
                            
                except json.JSONDecodeError:
                    print("[-] Failed to decode JSON response")
                    print(f"Raw response:\n{response.text}")
            else:
                print(f"[-] Request failed with status code: {response.status_code}")
                print(f"Response:\n{response.text}")
                
        except requests.RequestException as e:
            print(f"[-] Request error: {e}")

if __name__ == "__main__":
    main()