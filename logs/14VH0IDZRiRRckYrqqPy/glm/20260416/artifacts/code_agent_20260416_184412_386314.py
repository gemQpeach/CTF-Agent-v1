import base64
import pickle
import pickletools
import json
import sys

def main():
    # Task 1: Base64 and Pickle Analysis
    b64_str = "gASVJwAAAAAAAAB9lCiMBXRoZW1llIwEZGFya5SMCGxhbmd1YWdllIwFemgtQ26UdS4="
    print("[*] Original Base64 String:", b64_str)
    
    try:
        # Step 1: Base64 decode
        decoded_bytes = base64.b64decode(b64_str)
        print("\n[+] Decoded Bytes:", decoded_bytes)
        
        # Step 2: Pickle loads
        print("\n[*] Pickle Deserialization (pickle.loads):")
        obj = pickle.loads(decoded_bytes)
        print("    Type:", type(obj))
        print("    Object:", obj)
        
        # Step 3: Pickletools disassemble
        print("\n[*] Pickle Disassembly (pickletools.dis):")
        pickletools.dis(decoded_bytes)
        
        # Step 4: Structure Analysis
        print("\n[*] Structure Analysis:")
        print("    The serialized data represents a Python dictionary with 2 key-value pairs.")
        print("    It uses pickle protocol 5 (or similar) with specific opcodes:")
        print("    - `}` (DICT): Marks the creation of a dictionary.")
        print("    - `(` (MARK): Pushes a mark onto the stack for tuple/dict construction.")
        print("    - `X` (BINUNICODE): Pushes a unicode string (the keys and values).")
        print("    - `u` (SETITEMS): Pops mark and alternating key-value pairs to add to the dict.")
        print("    - `. `(STOP): Stops execution.")
        print("    Extracted Data Structure:")
        for k, v in obj.items():
            print(f"      Key: '{k}' -> Value: '{v}'")
            
    except Exception as e:
        print(f"[-] Error during Pickle processing: {e}")

    print("\n" + "="*60 + "\n")

    # Task 2: JWT / Flask Session Cookie Decoding
    jwt_token = "eyJpc19hZG1pbiI6dHJ1ZSwidXNlcm5hbWUiOiJyb290YWRtaW4ifQ.aeC9GQ.gmkhY088XDEEIJpV-77DtAF3DhY"
    print("[*] Original JWT/Session Token:", jwt_token)
    
    try:
        # Split token and get the first part (Payload in Flask sessions, or Header in standard JWT)
        # Based on the content, the first part is the payload
        parts = jwt_token.split('.')
        if len(parts) < 2:
            raise ValueError("Invalid JWT/Session format")
            
        payload_b64 = parts[0]
        
        # Fix Base64 padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
            
        # Decode Base64
        decoded_payload_bytes = base64.b64decode(payload_b64)
        decoded_payload_str = decoded_payload_bytes.decode('utf-8')
        
        # Parse JSON
        payload_data = json.loads(decoded_payload_str)
        
        print("\n[+] Decoded JWT Payload:")
        print("    Raw JSON String:", decoded_payload_str)
        print("    Parsed Python Object:", payload_data)
        print("    Is Admin:", payload_data.get("is_admin"))
        print("    Username:", payload_data.get("username"))
        
    except Exception as e:
        print(f"[-] Error during JWT processing: {e}")

if __name__ == "__main__":
    main()