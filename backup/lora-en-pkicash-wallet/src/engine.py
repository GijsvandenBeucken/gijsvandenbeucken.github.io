import json
import sqlite3
from pathlib import Path

from src.crypto_utils import (
    generate_keypair, sign, verify, sk_to_hex, pk_to_hex,
    sk_from_hex, build_payload,
)
from src.coin import Coin


class InvalidSignatureError(Exception):
    pass


class DoubleSpendError(Exception):
    pass


class UnknownCoinError(Exception):
    pass


class UntrustedIssuerError(Exception):
    pass


class StateEngine:
    def __init__(self, db_path: str = ":memory:", sk=None):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

        if sk:
            self._sk = sk
        else:
            self._sk, _ = generate_keypair()
        self._pk = self._sk.verify_key

    @property
    def pk_hex(self) -> str:
        return pk_to_hex(self._pk)

    def _init_db(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS coins (
                coin_id TEXT PRIMARY KEY,
                pk_current TEXT NOT NULL,
                coin_data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trusted_issuers (
                pk_issuer TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS pending_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_address TEXT NOT NULL,
                coin_json TEXT NOT NULL,
                confirmation TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0
            );
        """)
        self._conn.commit()

    def register_issuer(self, pk_issuer_hex: str):
        self._conn.execute(
            "INSERT OR IGNORE INTO trusted_issuers (pk_issuer) VALUES (?)",
            (pk_issuer_hex,),
        )
        self._conn.commit()

    def is_trusted_issuer(self, pk_issuer_hex: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM trusted_issuers WHERE pk_issuer = ?",
            (pk_issuer_hex,),
        ).fetchone()
        return row is not None

    def list_issuers(self) -> list[str]:
        rows = self._conn.execute("SELECT pk_issuer FROM trusted_issuers").fetchall()
        return [r["pk_issuer"] for r in rows]

    def register_coin(self, coin: Coin, recipient_address: str):
        if not self.is_trusted_issuer(coin.pk_issuer):
            raise UntrustedIssuerError(f"Issuer {coin.pk_issuer[:16]}... is niet vertrouwd")

        if not coin.verify_issuer():
            raise InvalidSignatureError("Ongeldige issuer signature")

        coin_data = coin.to_dict()

        self._conn.execute(
            "INSERT INTO coins (coin_id, pk_current, coin_data) VALUES (?, ?, ?)",
            (coin.coin_id, coin.pk_current, json.dumps(coin_data)),
        )

        confirmation_payload = build_payload(coin.coin_id, coin.pk_current, "issued")
        confirmation_sig = sign(self._sk, confirmation_payload)
        confirmation = {
            "coin_id": coin.coin_id,
            "pk_next": coin.pk_current,
            "status": "issued",
            "engine_signature": confirmation_sig.hex(),
            "pk_engine": self.pk_hex,
        }

        self._conn.execute(
            "INSERT INTO pending_deliveries (recipient_address, coin_json, confirmation) VALUES (?, ?, ?)",
            (recipient_address, json.dumps(coin_data), json.dumps(confirmation)),
        )
        self._conn.commit()

    def get_coin_state(self, coin_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT coin_id, pk_current FROM coins WHERE coin_id = ?",
            (coin_id,),
        ).fetchone()
        if row is None:
            return None
        return {"coin_id": row["coin_id"], "pk_current": row["pk_current"]}

    def list_coins(self) -> list[dict]:
        rows = self._conn.execute("SELECT coin_id, pk_current, coin_data FROM coins").fetchall()
        result = []
        for r in rows:
            entry = {"coin_id": r["coin_id"], "pk_current": r["pk_current"]}
            try:
                entry["coin_data"] = json.loads(r["coin_data"])
            except (json.JSONDecodeError, TypeError):
                pass
            result.append(entry)
        return result

    def process_transaction(self, tx: dict) -> dict:
        """
        tx must contain: coin_id, pk_next, recipient_address, signature (hex)
        Returns signed confirmation dict.
        """
        coin_id = tx["coin_id"]
        pk_next = tx["pk_next"]
        recipient_address = tx["recipient_address"]
        sig_hex = tx["signature"]

        state = self.get_coin_state(coin_id)
        if state is None:
            raise UnknownCoinError(f"Coin {coin_id} niet gevonden")

        pk_current_hex = state["pk_current"]

        payload = build_payload(coin_id, pk_next)
        if not verify(bytes.fromhex(pk_current_hex), payload, bytes.fromhex(sig_hex)):
            raise InvalidSignatureError("Ongeldige transactie signature")

        # Retrieve full coin data before updating
        row = self._conn.execute(
            "SELECT coin_data FROM coins WHERE coin_id = ?", (coin_id,)
        ).fetchone()
        coin_data = json.loads(row["coin_data"])
        coin_data["pk_current"] = pk_next

        self._conn.execute(
            "UPDATE coins SET pk_current = ?, coin_data = ? WHERE coin_id = ?",
            (pk_next, json.dumps(coin_data), coin_id),
        )

        confirmation_payload = build_payload(coin_id, pk_next, "confirmed")
        confirmation_sig = sign(self._sk, confirmation_payload)
        confirmation = {
            "coin_id": coin_id,
            "pk_next": pk_next,
            "status": "confirmed",
            "engine_signature": confirmation_sig.hex(),
            "pk_engine": self.pk_hex,
        }

        self._conn.execute(
            "INSERT INTO pending_deliveries (recipient_address, coin_json, confirmation) VALUES (?, ?, ?)",
            (recipient_address, json.dumps(coin_data), json.dumps(confirmation)),
        )
        self._conn.commit()

        return confirmation

    def get_pending_deliveries(self, wallet_address: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, coin_json, confirmation FROM pending_deliveries WHERE recipient_address = ? AND delivered = 0",
            (wallet_address,),
        ).fetchall()

        results = []
        ids = []
        for row in rows:
            results.append({
                "coin": json.loads(row["coin_json"]),
                "confirmation": json.loads(row["confirmation"]),
            })
            ids.append(row["id"])

        if ids:
            placeholders = ",".join("?" * len(ids))
            self._conn.execute(
                f"UPDATE pending_deliveries SET delivered = 1 WHERE id IN ({placeholders})",
                ids,
            )
            self._conn.commit()

        return results

    def save_key(self, path: str):
        Path(path).write_text(sk_to_hex(self._sk))

    @classmethod
    def load_key(cls, path: str, db_path: str = ":memory:") -> "StateEngine":
        hex_str = Path(path).read_text().strip()
        sk = sk_from_hex(hex_str)
        return cls(db_path=db_path, sk=sk)
