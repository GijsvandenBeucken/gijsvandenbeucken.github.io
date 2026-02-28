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

    def issue_coin(self, waarde: int, pk_recipient_hex: str, engine_endpoint: str, pk_engine_hex: str) -> tuple:
        """Returns (coin, transfer_info) where coin has pk_current=pk_issuer
        and transfer_info contains pk_next + transfer_signature for the
        initial ownership transfer from issuer to recipient."""
        coin_id = str(uuid.uuid4())

        issuer_payload = build_payload(coin_id, str(waarde), self.pk_hex)
        issuer_sig = sign(self._sk, issuer_payload)

        transfer_payload = build_payload(coin_id, pk_recipient_hex)
        transfer_sig = sign(self._sk, transfer_payload)

        coin = Coin(
            coin_id=coin_id,
            waarde=waarde,
            pk_current=self.pk_hex,
            pk_issuer=self.pk_hex,
            issuer_signature=issuer_sig.hex(),
            state_engine_endpoint=engine_endpoint,
            pk_engine=pk_engine_hex,
        )

        transfer_info = {
            "pk_next": pk_recipient_hex,
            "transfer_signature": transfer_sig.hex(),
        }

        return coin, transfer_info

    def save_key(self, path: str):
        Path(path).write_text(sk_to_hex(self._sk))

    @classmethod
    def load_key(cls, path: str) -> "Issuer":
        hex_str = Path(path).read_text().strip()
        sk = sk_from_hex(hex_str)
        return cls(sk=sk)
