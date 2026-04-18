import base64
import json

def base64url_decode(data):
    padding = 4 - len(data) % 4
    if padding != 4:
        data += '=' * padding
    decoded_bytes = base64.urlsafe_b64decode(data)
    return decoded_bytes.decode('utf-8')

def decode_jwt(token):
    parts = token.split('.')
    if len(parts) != 3:
        print("Invalid JWT token format")
        return
    
    header_enc = parts[0]
    payload_enc = parts[1]
    
    header_json = base64url_decode(header_enc)
    payload_json = base64url_decode(payload_enc)
    
    header = json.loads(header_json)
    payload = json.loads(payload_json)
    
    print("Header:")
    print(json.dumps(header, indent=2))
    print("\nPayload:")
    print(json.dumps(payload, indent=2))

def main():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzc2MzY0ODg4fQ.d9XXVxjlWcSANvTC57gx6yYKzm-5PN3FnHOXOQAB9C0"
    decode_jwt(token)

if __name__ == "__main__":
    main()