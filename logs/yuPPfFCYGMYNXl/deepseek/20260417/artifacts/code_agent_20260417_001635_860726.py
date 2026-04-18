import base64
import json
import datetime

def decode_base64url(data):
    missing_padding = len(data) % 4
    if missing_padding:
        data += '=' * (4 - missing_padding)
    data = data.replace('-', '+').replace('_', '/')
    decoded_bytes = base64.b64decode(data)
    return json.loads(decoded_bytes.decode('utf-8'))

def main():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxNzc2MzU3OTIzfQ.Lim7ygUQrDvdfB-z446FkBQ7RHZh01MsiNMofKbNG3Y"
    
    parts = token.split('.')
    if len(parts) != 3:
        print("Invalid JWT token format")
        return
        
    header = decode_base64url(parts[0])
    payload = decode_base64url(parts[1])
    signature = parts[2]
    
    print(f"Header: {json.dumps(header, indent=2)}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"Signature: {signature}")
    
    print("\n--- Analysis ---")
    sub = payload.get('sub')
    exp = payload.get('exp')
    
    print(f"Subject (sub): {sub}")
    
    if exp:
        exp_time = datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc)
        print(f"Expiration Time (exp): {exp} (UTC: {exp_time.strftime('%Y-%m-%d %H:%M:%S')})")
        
        now = datetime.datetime.now(datetime.timezone.utc)
        if now > exp_time:
            print("Token status: EXPIRED")
        else:
            print("Token status: VALID (not expired)")

if __name__ == "__main__":
    main()