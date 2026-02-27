import json
import uuid
from pathlib import Path

from src.crypto_utils import generate_keypair, sign, sk_to_hex, pk_to_hex, sk_from_hex, build_payload
from src.coin import Coin


class Issuer:
    def __init__(self, sk=None):
        if sk:
            self._sk = sk
        else:
            self._sk, _ = generate_keypair()
        self._pk = self._sk.verify_key

    @property
    def pk_hex(self) -> str:
        return pk_to_hex(self._pk)

    def issue_coin(self, waarde: int, pk_owner_hex: str, engine_endpoint: str, pk_engine_hex: str) -> Coin:
        coin_id = str(uuid.uuid4())
        payload = build_payload(coin_id, str(waarde), pk_owner_hex)
        signature = sign(self._sk, payload)

        return Coin(
            coin_id=coin_id,
            waarde=waarde,
            pk_current=pk_owner_hex,
            pk_issuer=self.pk_hex,
            issuer_signature=signature.hex(),
            state_engine_endpoint=engine_endpoint,
            pk_engine=pk_engine_hex,
        )

    def save_key(self, path: str):
        Path(path).write_text(sk_to_hex(self._sk))

    @classmethod
    def load_key(cls, path: str) -> "Issuer":
        hex_str = Path(path).read_text().strip()
        sk = sk_from_hex(hex_str)
        return cls(sk=sk)
