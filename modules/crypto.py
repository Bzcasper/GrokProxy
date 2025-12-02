from base64    import b64encode, b64decode
from secrets   import token_bytes
from coincurve import PrivateKey
from hashlib   import sha256


def public_key_create(private_bytes):
    priv_key = PrivateKey(bytes(private_bytes))
    pub_key = priv_key.public_key.format(compressed=True)
    return list(pub_key)


def xor(data_bytes):
    result = ""
    for i in range(len(data_bytes)):
        result += chr(data_bytes[i])
    return b64encode(result.encode('latin-1')).decode()


def generate_keys():
    raw_key = token_bytes(32)
    pub_key = public_key_create(raw_key)
    encoded_key = xor(raw_key)
    
    return {
        "privateKey": encoded_key,
        "userPublicKey": pub_key
    }

def sign_challenge(challenge_data, encoded_key):
    key_raw = b64decode(encoded_key)
    priv_key = PrivateKey(key_raw)
    sig = priv_key.sign_recoverable(sha256(challenge_data).digest(), hasher=None)[:64]
    return {
        "challenge": b64encode(challenge_data).decode(),
        "signature": b64encode(sig).decode()
    }
