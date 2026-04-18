import hashlib
import re

TARGET_HASH = "0e678703625362188185747119782643"

MAGIC_STRINGS = [
    "QNKCDZO", "240610708", "s878926199a", "s155964671a", 
    "s214587387a", "s1091221200a", "s1885207154a", 
    "s1502113478a", "s1836677006a", "s532378020a", "s1182984159a"
]

COMMON_PASSWORDS = [
    "123456", "password", "123456789", "12345678", "12345",
    "1234", "111111", "1234567", "dragon", "123123", "baseball",
    "abc123", "football", "monkey", "letmein", "shadow", "master",
    "696969", "michael", "654321", "qwerty", "password1", "admin",
    "root", "test", "guest", "welcome", "login", "123qwe", "zxcvbn",
    "passw0rd", "1234567890", "iloveyou", "trustno1", "sunshine",
    "princess", "football", "charlie", "root123", "admin123",
    "1q2w3e4r", "qwer1234", "pass123", "user", "supersecret"
]

def compute_md5(s):
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def is_magic_hash(h):
    return bool(re.match(r'^0e\d+$', h))

def main():
    print("[*] Verifying known PHP magic strings (MD5 starts with 0e and followed by digits):")
    for s in MAGIC_STRINGS:
        h = compute_md5(s)
        is_magic = is_magic_hash(h)
        print(f"String: {s:<15} MD5: {h:<35} Is Magic: {is_magic}")
    
    print(f"\n[*] Attempting to crack target hash: {TARGET_HASH}")
    found = False
    
    crack_list = list(set(MAGIC_STRINGS + COMMON_PASSWORDS))
    
    for p in crack_list:
        h = compute_md5(p)
        if h == TARGET_HASH:
            print(f"[+] SUCCESS! Cracked target hash!")
            print(f"    Plaintext: {p}")
            print(f"    MD5:       {h}")
            found = True
            break
            
    if not found:
        print("[-] Target hash not found in the provided common passwords and magic strings list.")

if __name__ == "__main__":
    main()