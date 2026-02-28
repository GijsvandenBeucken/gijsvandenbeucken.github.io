import json
from datetime import datetime
from pathlib import Path

from src.crypto_utils import (
    generate_keypair, sign, verify, sk_to_hex, pk_to_hex,
    sk_from_hex, pk_from_hex, build_payload,
)
from src.coin import Coin


class Wallet:
    def __init__(self, wallet_path: str):
        self._path = Path(wallet_path)
        self._data = {"coins": {}, "pending_keypairs": {}, "transaction_log": [], "contacts": [], "address": ""}
        if self._path.exists():
            stored = json.loads(self._path.read_text())
            self._data.update(stored)
            for key in ("transaction_log", "contacts"):
                if key not in self._data:
                    self._data[key] = []
            if "address" not in self._data:
                self._data["address"] = ""
        self.address = self._data["address"]

    def get_address(self):
        return self._data.get("address", "")

    def set_address(self, addr: str):
        self._data["address"] = addr
        self.address = addr
        self._save()

    def _save(self):
        self._path.write_text(json.dumps(self._data, indent=2))

    def _log(self, action: str, coin_id: str, waarde=None, counterparty: str = None, coin_data: dict = None, description: str = None):
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "coin_id": coin_id,
            "waarde": waarde,
            "counterparty": counterparty,
        }
        if coin_data:
            entry["coin_data"] = coin_data
        if description:
            entry["description"] = description
        self._data["transaction_log"].append(entry)

    def generate_receive_keypair(self) -> str:
        sk, pk = generate_keypair()
        pk_hex = pk_to_hex(pk)
        self._data["pending_keypairs"][pk_hex] = sk_to_hex(sk)
        self._save()
        return pk_hex

    def add_coin(self, coin: Coin):
        sk_hex = self._data["pending_keypairs"].pop(coin.pk_current, None)
        if sk_hex is None:
            raise ValueError(f"Geen pending keypair gevonden voor pk {coin.pk_current[:16]}...")

        self._data["coins"][coin.coin_id] = {
            "coin": coin.to_dict(),
            "sk_current": sk_hex,
        }
        self._save()

    def add_coin_with_sk(self, coin: Coin, sk_hex: str):
        self._data["coins"][coin.coin_id] = {
            "coin": coin.to_dict(),
            "sk_current": sk_hex,
        }
        self._save()

    def list_coins(self) -> list[dict]:
        result = []
        for coin_id, entry in self._data["coins"].items():
            c = entry["coin"]
            result.append({"coin_id": coin_id, "waarde": c["waarde"]})
        return result

    def get_balance(self) -> int:
        return sum(e["coin"]["waarde"] for e in self._data["coins"].values())

    def get_coin(self, coin_id: str) -> Coin | None:
        entry = self._data["coins"].get(coin_id)
        if entry is None:
            return None
        return Coin.from_dict(entry["coin"])

    def create_transaction(self, coin_id: str, pk_next_hex: str, recipient_address: str) -> dict:
        entry = self._data["coins"].get(coin_id)
        if entry is None:
            raise ValueError(f"Coin {coin_id} niet in wallet")

        sk_hex = entry["sk_current"]
        sk = sk_from_hex(sk_hex)

        payload = build_payload(coin_id, pk_next_hex)
        signature = sign(sk, payload)

        return {
            "coin_id": coin_id,
            "pk_next": pk_next_hex,
            "recipient_address": recipient_address,
            "signature": signature.hex(),
        }

    def confirm_send(self, coin_id: str, recipient_address: str = None, description: str = None):
        entry = self._data["coins"].get(coin_id)
        waarde = entry["coin"]["waarde"] if entry else None
        coin_data = entry["coin"] if entry else None
        if coin_id in self._data["coins"]:
            del self._data["coins"][coin_id]
        self._log("verstuurd", coin_id, waarde=waarde,
                  counterparty=recipient_address, coin_data=coin_data,
                  description=description)
        self._save()

    def receive_from_engine(self, delivery: dict):
        confirmation = delivery["confirmation"]
        coin_data = delivery["coin"]
        coin_id = coin_data["coin_id"]
        pk_current = coin_data["pk_current"]
        status = confirmation["status"]

        engine_payload = build_payload(coin_id, pk_current, status)
        pk_engine_hex = confirmation["pk_engine"]
        engine_sig_hex = confirmation["engine_signature"]

        if not verify(bytes.fromhex(pk_engine_hex), engine_payload, bytes.fromhex(engine_sig_hex)):
            raise ValueError("Ongeldige engine signature op bevestiging")

        sk_hex = self._data["pending_keypairs"].pop(pk_current, None)
        if sk_hex is None:
            raise ValueError(f"Geen pending keypair voor pk {pk_current[:16]}...")

        self._data["coins"][coin_id] = {
            "coin": coin_data,
            "sk_current": sk_hex,
        }

        action = "ontvangen van bank" if status == "issued" else "betaling ontvangen"
        counterparty = delivery.get("sender_dest", "")
        description = delivery.get("description")
        self._log(action, coin_id, waarde=coin_data.get("waarde"),
                  counterparty=counterparty, coin_data=coin_data,
                  description=description)
        self._save()

    def validate_coin(self, coin: Coin, trusted_issuers: list[str]) -> bool:
        if coin.pk_issuer not in trusted_issuers:
            return False
        return coin.verify_issuer()

    def get_transaction_log(self) -> list[dict]:
        return list(reversed(self._data.get("transaction_log", [])))

    # --- Contacts ---

    def get_contacts(self) -> list[dict]:
        return self._data.get("contacts", [])

    def add_contact(self, name: str, address: str, pk: str):
        self._data.setdefault("contacts", []).append({"name": name, "address": address, "pk": pk})
        self._save()

    def update_contact(self, idx: int, name: str, address: str, pk: str):
        contacts = self._data.get("contacts", [])
        if 0 <= idx < len(contacts):
            contacts[idx] = {"name": name, "address": address, "pk": pk}
            self._save()

    def delete_contact(self, idx: int):
        contacts = self._data.get("contacts", [])
        if 0 <= idx < len(contacts):
            contacts.pop(idx)
            self._save()
