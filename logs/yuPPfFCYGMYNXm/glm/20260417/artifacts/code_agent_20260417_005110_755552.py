import base64
import zlib
import json

COOKIE = ".eJwlzjsOwjAMANC7ZGaInTh2epkq_gnWlk6Iu1OJ_Q3vU_Y84nyW7X1c8Sj7y8tWwmvqWN4xpjeikWzYExcZUJW-xFRV0CYA4wKZ0o1btOqYjDJxTGxTvTcfqWxpEmCwkDVrQm-Q5HYjdHLi5qBAlDktRWGVO3Kdcfw3WL4_5hUv0A.aeEPbQ.rZBGPUZW0EUf_PiA-cMFvKWOzdk"

def main():
    try:
        # Remove leading dot if present
        if COOKIE.startswith('.'):
            cookie_val = COOKIE[1:]
        else:
            cookie_val = COOKIE
            
        # Split into parts: payload, timestamp, signature
        parts = cookie_val.split('.')
        if len(parts) != 3:
            print("Error: Invalid Flask session cookie format")
            return
            
        payload_b64 = parts[0]
        
        # Add back the base64 padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
            
        # Base64 decode (URL-safe)
        decoded_bytes = base64.urlsafe_b64decode(payload_b64)
        
        # Decompress with zlib
        decompressed_bytes = zlib.decompress(decoded_bytes)
        
        # Parse and show JSON contents
        data = json.loads(decompressed_bytes)
        print(json.dumps(data, indent=4))
        
    except Exception as e:
        print(f"Error decoding cookie: {e}")

if __name__ == "__main__":
    main()