from dataclasses import dataclass
from src.crypto_utils import verify, pk_from_hex, build_payload


@dataclass
class Coin:
    coin_id: str
    waarde: int
    pk_current: str        # hex-encoded public key of current owner
    pk_issuer: str         # hex-encoded public key of issuer
    issuer_signature: str  # hex-encoded signature
    state_engine_endpoint: str
    pk_engine: str         # hex-encoded public key of engine

    def signing_payload(self) -> bytes:
        return build_payload(self.coin_id, str(self.waarde), self.pk_current)

    def verify_issuer(self, pk_issuer_hex: str = None) -> bool:
        pk_hex = pk_issuer_hex or self.pk_issuer
        return verify(
            bytes.fromhex(pk_hex),
            self.signing_payload(),
            bytes.fromhex(self.issuer_signature),
        )

    def to_dict(self) -> dict:
        return {
            "coin_id": self.coin_id,
            "waarde": self.waarde,
            "pk_current": self.pk_current,
            "pk_issuer": self.pk_issuer,
            "issuer_signature": self.issuer_signature,
            "state_engine_endpoint": self.state_engine_endpoint,
            "pk_engine": self.pk_engine,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Coin":
        return cls(
            coin_id=data["coin_id"],
            waarde=int(data["waarde"]),
            pk_current=data["pk_current"],
            pk_issuer=data["pk_issuer"],
            issuer_signature=data["issuer_signature"],
            state_engine_endpoint=data["state_engine_endpoint"],
            pk_engine=data["pk_engine"],
        )
