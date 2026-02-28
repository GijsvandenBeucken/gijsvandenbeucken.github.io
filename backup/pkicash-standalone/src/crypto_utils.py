from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


def generate_keypair():
    sk = SigningKey.generate()
    pk = sk.verify_key
    return sk, pk


def sign(sk: SigningKey, message: bytes) -> bytes:
    signed = sk.sign(message)
    return signed.signature


def verify(pk_bytes: bytes, message: bytes, signature: bytes) -> bool:
    try:
        pk = VerifyKey(pk_bytes)
        pk.verify(message, signature)
        return True
    except BadSignatureError:
        return False


def sk_to_hex(sk: SigningKey) -> str:
    return sk.encode().hex()


def pk_to_hex(pk: VerifyKey) -> str:
    return pk.encode().hex()


def sk_from_hex(hex_str: str) -> SigningKey:
    return SigningKey(bytes.fromhex(hex_str))


def pk_from_hex(hex_str: str) -> VerifyKey:
    return VerifyKey(bytes.fromhex(hex_str))


def build_payload(*parts: str) -> bytes:
    """Deterministic payload construction by joining string parts with '|' separator."""
    return "|".join(parts).encode("utf-8")
