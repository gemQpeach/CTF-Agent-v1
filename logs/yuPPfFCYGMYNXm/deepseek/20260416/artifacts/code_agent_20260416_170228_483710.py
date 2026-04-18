import base64
import zlib
import json

def decode_flask_session(cookie_value):
    parts = cookie_value.split('.')
    
    if parts[0] == '':
        payload = parts[1]
    else:
        payload = parts[0]
        
    payload += '=' * (-len(payload) % 4)
    
    decoded_bytes = base64.urlsafe_b64decode(payload)
    
    try:
        decompressed_bytes = zlib.decompress(decoded_bytes)
        return json.loads(decompressed_bytes.decode('utf-8'))
    except zlib.error:
        return json.loads(decoded_bytes.decode('utf-8'))

def main():
    cookie = ".eJwlzjsOwjAMANC7ZGaInTh2epkq_gnWlk6Iu1OJ_Q3vU_Y84nyW7X1c8Sj7y8tWwmvqWN4xpjeikWzYExcZUJW-xFRV0CYA4wKZ0o1btOqYjDJxTGxTvTcfqWxpEmCwkDVrQm-Q5HYjdHLi5qBAlDktRWGVO3Kdcfw3WL4_5hUv0A.aeClag.Xhga-ij1AbQRTYn-21LfAEqBdBA"
    
    decoded_data = decode_flask_session(cookie)
    print("Decoded Flask Session Data:")
    print(json.dumps(decoded_data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()